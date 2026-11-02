"""Check compiled C model's predictions against JSON traversal for every saved window."""
import ctypes, subprocess, pathlib, json, numpy as np, pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
feat=pd.read_csv(ROOT/'docs'/'all_window_features.csv')
model=json.loads((ROOT/'models'/'decision_tree_task7_120hz_motion_fe.json').read_text())
cols=model['selected_features'];features=feat[cols].to_numpy(np.float64)
nodes=model['nodes']
def predict(x):
    i=0
    while not nodes[i]['is_leaf']:
        nd=nodes[i];i=nd['left_child'] if x[nd['feature_index']]<=nd['threshold'] else nd['right_child']
    return nodes[i]['predicted_class_index']
ref=np.array([predict(x) for x in features]);
src=ROOT/'ISPU_208hz'/'src';lib=ROOT/'tests'/'libquatfe.so'
subprocess.run(['gcc','-std=c11','-O2','-shared','-fPIC',str(src/'quat_fe_tree.c'),'-I'+str(src),'-o',str(lib)],check=True)
class Prediction(ctypes.Structure):
    _fields_=[('predicted_class',ctypes.c_uint32),('leaf_training_purity',ctypes.c_float)]
C=ctypes.CDLL(str(lib));C.quatfe_predict_features.argtypes=[ctypes.POINTER(ctypes.c_float)];C.quatfe_predict_features.restype=Prediction
p=np.array([C.quatfe_predict_features(np.asarray(x,dtype=np.float32).ctypes.data_as(ctypes.POINTER(ctypes.c_float))).predicted_class for x in features]);bad=np.flatnonzero(p!=ref)
print('C vs JSON prediction checks:',len(ref),'mismatches:',len(bad));print([(int(i),features[i].tolist(),int(ref[i]),int(p[i])) for i in bad[:10]]);assert len(bad)==0
# Compare the C feature extractor against Python for the first 42-sample window
C.quatfe_window_features.argtypes=[ctypes.POINTER(ctypes.c_float),ctypes.POINTER(ctypes.c_float)]
for c in ['Horizontal','Static','Vertical']:
    fn={'Horizontal':'ispuHmotion120hz(1).csv','Static':'ispuStatic120hz(1).csv','Vertical':'ispuVmotion120hz(1).csv'}[c]
    d=pd.read_csv(ROOT/'data'/fn,comment='#');i=np.where(np.diff(d['time[us]'])>250000)[0][-1]+1
    a=np.ascontiguousarray(d.iloc[i:i+42][['q4','q1','q2','q3']].to_numpy(dtype=np.float32))
    out=np.zeros(8,dtype=np.float32)
    C.quatfe_window_features(a.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
    r=np.array([z for ch in a.T for z in [np.var(ch),np.ptp(ch)]],dtype=np.float32)
    print(c,'max feature abs diff C vs Python',np.max(abs(out-r)))
    assert np.allclose(out,r,rtol=1e-3,atol=1e-8)
# End-to-end raw CSV windows -> C feature computation -> C tree -> JSON prediction.
records={}
for cl,f in [('Horizontal','ispuHmotion120hz(1).csv'),('Static','ispuStatic120hz(1).csv'),('Vertical','ispuVmotion120hz(1).csv')]:
    d=pd.read_csv(ROOT/'data'/f,comment='#');k=np.where(np.diff(d['time[us]'])>250000)[0][-1]+1
    records[cl]=np.ascontiguousarray(d.iloc[k:][['q4','q1','q2','q3']].to_numpy(np.float32))
wrong=[]
for idx,row in feat.iterrows():
    start=int(row['window_id'])*21
    raw=np.ascontiguousarray(records[row['activity']][start:start+42])
    x=np.zeros(8,np.float32)
    C.quatfe_window_features(raw.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
    c_id=C.quatfe_predict_features(x.ctypes.data_as(ctypes.POINTER(ctypes.c_float))).predicted_class
    if c_id!=ref[idx]:wrong.append((int(idx),int(c_id),int(ref[idx]),float(x[7]),float(row['q3__p2p'])))
print('End-to-end C feature+tree vs JSON feature+tree:',len(ref),'windows; mismatches:',len(wrong),wrong[:10])
assert not wrong
print('PASS')
