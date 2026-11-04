#!/usr/bin/env python3
"""Desktop checks: C feature calculations and decisions match Python + model JSON.
Test also exercises the circular-window wrap-around and quaternion reorientation.
No STRED compiler / physical ISPU is tested here.
"""
from __future__ import annotations
import ctypes, json, pathlib, subprocess, sys
import numpy as np
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from retrain_task7 import FILES, FEATURES, WINDOW, STRIDE, extract_window
libpath=ROOT/'tests'/'libquatfe_host.so'
src=ROOT/'ISPU_208hz'/'src'
subprocess.run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',
                '-I'+str(src),str(src/'quat_fe_tree.c'),'-o',str(libpath)],check=True)
class Prediction(ctypes.Structure):
    _fields_=[('predicted_class',ctypes.c_uint32),('leaf_training_purity',ctypes.c_float)]
lib=ctypes.CDLL(str(libpath))
lib.quatfe_predict_features.argtypes=[ctypes.POINTER(ctypes.c_float)]
lib.quatfe_predict_features.restype=Prediction
lib.quatfe_window_features.argtypes=[ctypes.POINTER(ctypes.c_float),ctypes.c_uint32,ctypes.POINTER(ctypes.c_float)]
lib.quatfe_window_features.restype=None
model=json.loads((ROOT/'models'/'decision_tree_task7_curl_lat_raise_punch.json').read_text());nodes=model['nodes'];feat_order=model['feature_names']

def json_predict(x):
    idx=0
    for _ in range(40):
        n=nodes[idx]
        if n['is_leaf']:return n['predicted_class_index']
        idx=n['left_child'] if float(x[n['feature_index']]) <= n['threshold'] else n['right_child']
    raise RuntimeError('loop in model tree')

def c_features(q,offset=0):
    # Build ring buffer where chronological first is at 'offset'.
    offset=int(offset)%WINDOW
    buf=np.empty((WINDOW,4),np.float32)
    for i in range(WINDOW):buf[(offset+i)%WINDOW]=q[i]
    out=np.empty(len(FEATURES),np.float32)
    lib.quatfe_window_features(buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),offset,
                               out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
    return out

def c_pred(features):
    x=np.ascontiguousarray(features,dtype=np.float32)
    return lib.quatfe_predict_features(x.ctypes.data_as(ctypes.POINTER(ctypes.c_float))).predicted_class

def left_multiply(rot,q):
    a,b,c,d=np.array(rot,np.float32)
    w,x,y,z=q.T
    return np.stack([a*w-b*x-c*y-d*z,a*x+b*w+c*z-d*y,
                     a*y-b*z+c*w+d*x,a*z+b*y-c*x+d*w],axis=1).astype(np.float32)

features_df=pd.read_csv(ROOT/'docs'/'all_window_features.csv')
raw={lab:pd.read_csv(ROOT/'data'/fn,comment='#')[['q4','q1','q2','q3']].to_numpy(np.float32) for lab,fn in FILES.items()}
incorrect=[];ring_bad=[];shape_bad=[];max_abs=0.0;max_rel=0.0;offset_test=0
# A fixed global rotation applied to every quat (orientation change) should not affect
# the relative-feature model except float precision near thresholds.
rot=np.array([.8,.2,-.4,.4],np.float32);rot/=np.linalg.norm(rot)
changed=0; total_rot=0
for index,row in features_df.iterrows():
    q=np.ascontiguousarray(raw[row['activity']][int(row['window_id'])*STRIDE:][:WINDOW])
    for offset in ([0,21,41] if index%11==0 else [int(index)%WINDOW]):
        feats=c_features(q,offset)
        if offset!=0:offset_test+=1
        py=np.array([row[f] for f in FEATURES],float)
        abs_err=np.max(np.abs(feats-py))
        max_abs=max(max_abs,float(abs_err))
        max_rel=max(max_rel,float(np.max(np.abs(feats-py)/np.maximum(np.abs(py),1e-4))))
        # Tolerance accounts for float32 accumulation, not model disagreement.
        if not np.allclose(feats,py,atol=3e-6,rtol=3e-3):
            shape_bad.append((index,offset,float(abs_err)))
        if int(c_pred(feats))!=int(json_predict(py)):
            incorrect.append((index,offset,int(c_pred(feats)),int(json_predict(py))))
    if index%5==0:
        base=c_pred(c_features(q,0));shifted=c_pred(c_features(left_multiply(rot,q),0))
        changed+=int(base!=shifted);total_rot+=1
print(f'Raw windows: {len(features_df)}; wrapped-window checks: {offset_test}')
print(f'C vs saved Python features: max_abs_diff={max_abs:.3g}, max_scaled_diff={max_rel:.3g}; out-of-tolerance windows={len(shape_bad)}')
print(f'Full C pipeline vs JSON model predictions: mismatches={len(incorrect)} / {len(features_df)}')
print(f'Global orientation stress test: changed predictions={changed} / {total_rot}')
if shape_bad:print('Feature mismatch examples',shape_bad[:6])
if incorrect:print('Prediction mismatch examples',incorrect[:6])
assert len(shape_bad)==0, 'C and Python features differed more than tolerated'
assert len(incorrect)==0, 'C and JSON predictions disagreed'
assert changed<=3, 'Unexpected dependence on global rotation'
print('PASS: desktop feature extraction, ring wrapping, C/JSON prediction agreement')
