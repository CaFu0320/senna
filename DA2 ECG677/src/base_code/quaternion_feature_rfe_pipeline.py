#!/usr/bin/env python3
"""Quaternion window-feature decision tree with Recursive Feature Elimination.

Inputs: one or more MEMS Studio CSV logs for each class, with q0, q1, q2, q3.
The first copy of duplicate quaternion columns (e.g. q0.1) is retained.
Windows are made within each recording's train/validation/test segment, avoiding
windows crossing split boundaries. RFE is fit on training windows only.
Exports a JSON tree and matching C/H code that calculates selected features from
an input window, then performs tree inference.

Install: python -m pip install numpy pandas scikit-learn matplotlib
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path
from typing import Sequence
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_selection import RFE
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree, _tree

CHANNELS = ['q0', 'q1', 'q2', 'q3']
CLASSES = ['Horizontal', 'Static', 'Vertical']
STATS = ['mean', 'std', 'min', 'max', 'range', 'rms', 'median', 'iqr', 'mean_abs', 'zero_crossing_rate', 'waveform_length']
ALL_FEATURES = [f'{ch}__{stat}' for ch in CHANNELS for stat in STATS]

def read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file(): raise FileNotFoundError(f'CSV not found: {path}')
    last = None
    for sep in [None, ',', ';', '\t']:
        try:
            df = pd.read_csv(path, comment='#', skip_blank_lines=True, sep=sep, engine='python')
            df = df.dropna(axis=1, how='all')
            df.columns = [str(c).strip() for c in df.columns]
            if len(df.columns) >= 1: return df
        except Exception as e: last = e
    raise ValueError(f'Could not parse {path}: {last}')

def load_recording(path: Path, label: str):
    df = read_csv(path)
    found, keep = set(), []
    for col in df.columns:
        base = re.sub(r'\.\d+$', '', col).strip()
        if base in CHANNELS and base not in found:
            found.add(base); keep.append((col, base))
    missing = [c for c in CHANNELS if c not in found]
    if missing:
        raise ValueError(f'{path}: missing quaternion columns {missing}. Found headers: {list(df.columns)}')
    out = pd.DataFrame({base: pd.to_numeric(df[src], errors='coerce') for src, base in keep})
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=CHANNELS).reset_index(drop=True)
    if len(out) < 10: raise ValueError(f'{path} has only {len(out)} valid quaternion rows. This is probably an incomplete log.')
    out['label'] = label; out['source_file'] = path.name; out['source_path'] = str(path.resolve()); out['source_row'] = np.arange(len(out))
    print(f'Loaded {len(out):,} samples: {path} -> {label}; quaternion columns = {CHANNELS}')
    if len(out) < 100: print(f'WARNING: {path} has fewer than 100 usable rows; verify the recording is complete.')
    return out

def extract_features(w: np.ndarray) -> dict[str, float]:
    d = {}
    for i, ch in enumerate(CHANNELS):
        x = np.asarray(w[:, i], dtype=float); mean = float(np.mean(x)); centered = x - mean
        signs = np.sign(centered); nz = signs[signs != 0]
        crossings = int(np.sum(nz[1:] != nz[:-1])) if len(nz) > 1 else 0
        q1, q3 = np.percentile(x, [25, 75])
        vals = [mean, float(np.std(x)), float(np.min(x)), float(np.max(x)), float(np.ptp(x)),
                float(np.sqrt(np.mean(x*x))), float(np.median(x)), float(q3-q1),
                float(np.mean(np.abs(x))), float(crossings / max(1, len(x)-1)),
                float(np.sum(np.abs(np.diff(x))))]
        for stat, val in zip(STATS, vals): d[f'{ch}__{stat}'] = float(val)
    return d

def split_recording(df, train_fraction, val_fraction):
    n = len(df); a = int(n*train_fraction); b = int(n*(train_fraction+val_fraction))
    if a < 2 or b <= a or b >= n: raise ValueError(f'Recording {df.source_file.iloc[0]} too short for split.')
    return {'train': df.iloc[:a].copy(), 'validation': df.iloc[a:b].copy(), 'test': df.iloc[b:].copy()}

def window_segment(df, win, stride):
    rows=[]; raw=df[CHANNELS].to_numpy(float); label=str(df.label.iloc[0]); source=str(df.source_file.iloc[0]); rownums=df.source_row.to_numpy(int)
    for start in range(0, len(df)-win+1, stride):
        r=extract_features(raw[start:start+win]); r.update(label=label, source_file=source, window_start_row=int(rownums[start]), window_end_row=int(rownums[start+win-1])); rows.append(r)
    return pd.DataFrame(rows)

def cname(s):
    s=re.sub(r'[^A-Za-z0-9_]', '_', str(s).upper())
    return ('CLASS_' if not s or s[0].isdigit() else '')+s

def cf(x):
    s=format(float(x), '.9g')
    if '.' not in s and 'e' not in s.lower(): s += '.0'
    return s+'f'

def export_json(model, selected, selected_idx, ranking, path, args):
    t=model.tree_; classes=[str(c) for c in model.classes_]; nodes=[]
    for i in range(t.node_count):
        fi=int(t.feature[i]); leaf=fi == _tree.TREE_UNDEFINED; vals=[float(v) for v in t.value[i][0]]; pi=int(np.argmax(vals))
        nodes.append({'node_id':i,'feature_index':None if leaf else fi,'feature_name':None if leaf else selected[fi],
                      'threshold':None if leaf else float(t.threshold[i]),'left_child':None if leaf else int(t.children_left[i]),
                      'right_child':None if leaf else int(t.children_right[i]),'is_leaf':bool(leaf),
                      'predicted_class_index':pi,'predicted_class':classes[pi] if leaf else None,
                      'class_counts':{classes[j]:vals[j] for j in range(len(classes))},'samples':int(t.n_node_samples[i])})
    payload={'format':'quaternion_feature_rfe_decision_tree_v1','channels':CHANNELS,
             'window_size_samples':args.window_size,'recommended_stride_samples':args.stride,
             'statistic_order_per_channel':STATS,'all_engineered_features':ALL_FEATURES,
             'selected_feature_indices_in_all_features':selected_idx,'selected_features':selected,
             'rfe_ranking':ranking,'rfe_estimator':'DecisionTreeClassifier feature_importances_',
             'classes':classes,'tree_depth':int(model.get_depth()),'leaf_count':int(model.get_n_leaves()),
             'node_count':int(t.node_count),'criterion':args.criterion,'max_depth':args.max_depth,
             'min_samples_leaf':args.min_samples_leaf,'nodes':nodes,
             'note':'Quaternion features describe changes in q0-q3 over a window. Ensure logs are complete and quaternion convention/order matches deployment.'}
    path.write_text(json.dumps(payload,indent=2),encoding='utf-8'); return payload

def generate_c(json_path: Path, prefix: Path):
    p=json.loads(json_path.read_text(encoding='utf-8'))
    if p.get('format')!='quaternion_feature_rfe_decision_tree_v1': raise ValueError('Incompatible quaternion feature-RFE JSON.')
    win=int(p['window_size_samples']); allf=p['all_engineered_features']; selected=p['selected_features']; idxs=p['selected_feature_indices_in_all_features']; nodes=p['nodes']; classes=p['classes']
    if win<2: raise ValueError('Window size must be at least 2.')
    prefix.parent.mkdir(parents=True,exist_ok=True); hp=prefix.with_suffix('.h'); cp=prefix.with_suffix('.c'); guard=re.sub(r'\W','_',prefix.name.upper())+'_H'
    enums=',\n'.join(f'    QUAT_FEATURE_CLASS_{cname(c)} = {i}' for i,c in enumerate(classes))+' ,\n    QUAT_FEATURE_CLASS_UNKNOWN = 255'
    feat_comments='\n'.join(f' * {i}: {name}' for i,name in enumerate(selected))
    hp.write_text(f'''/* Auto-generated. Window={win}; input order q0,q1,q2,q3. */\n#ifndef {guard}\n#define {guard}\n#include <stdint.h>\n#define QUAT_TREE_WINDOW_SIZE {win}u\n#define QUAT_TREE_CHANNELS 4u\n#define QUAT_TREE_FEATURE_COUNT {len(selected)}u\n#define QUAT_TREE_NODE_COUNT {len(nodes)}u\ntypedef enum {{\n{enums}\n}} quat_feature_tree_class_t;\n/* samples[window_index][q0..q3]; quaternion units/convention must match training.\n{feat_comments}\n */\nquat_feature_tree_class_t quat_feature_tree_predict_window(const float samples[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS]);\n#endif\n''',encoding='utf-8')
    rows=[]
    for n in nodes:
        if n['is_leaf']: fi=-1; th='0.0f'; left=right=-1
        else: fi=int(n['feature_index']); th=cf(n['threshold']); left=int(n['left_child']); right=int(n['right_child'])
        rows.append(f"    {{{fi}, {th}, {left}, {right}, {int(n['predicted_class_index'])}u}},")
    # C computes exactly the feature set used by Python (percentile interpolation, population std).
    src=f'''/* Auto-generated from {json_path.name}; do not edit. */\n#include "{hp.name}"\n#include <math.h>\n#include <stddef.h>\ntypedef struct {{ int16_t feature; float threshold; int32_t left; int32_t right; uint8_t cls; }} quat_node_t;\nstatic const quat_node_t nodes[{len(nodes)}] = {{\n{chr(10).join(rows)}\n}};\nstatic float percentile(float *s, uint32_t n, float q) {{ float pos=(float)(n-1u)*q; uint32_t lo=(uint32_t)pos, hi=lo+1u; if(hi>=n) return s[n-1u]; return s[lo]+(pos-(float)lo)*(s[hi]-s[lo]); }}\nstatic void features(const float x[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS], float out[{len(allf)}]) {{\n uint32_t a,i,j; for(a=0;a<4u;++a) {{ float v[QUAT_TREE_WINDOW_SIZE],s[QUAT_TREE_WINDOW_SIZE]; float sum=0.0f,sq=0.0f,ab=0.0f,wave=0.0f,mn,mx,mean,var=0.0f; uint32_t cross=0u; int last=0;\n for(i=0;i<QUAT_TREE_WINDOW_SIZE;++i) {{ v[i]=x[i][a]; s[i]=v[i]; sum+=v[i]; sq+=v[i]*v[i]; ab+=fabsf(v[i]); if(i==0u) mn=mx=v[i]; else {{ if(v[i]<mn)mn=v[i]; if(v[i]>mx)mx=v[i]; wave+=fabsf(v[i]-v[i-1u]); }} }} mean=sum/(float)QUAT_TREE_WINDOW_SIZE; for(i=0;i<QUAT_TREE_WINDOW_SIZE;++i) {{ float d=v[i]-mean; var+=d*d; if(d>0.0f){{if(last<0)++cross;last=1;}} else if(d<0.0f){{if(last>0)++cross;last=-1;}} }} var/=(float)QUAT_TREE_WINDOW_SIZE; for(i=1u;i<QUAT_TREE_WINDOW_SIZE;++i) {{ float key=s[i]; j=i; while(j>0u && s[j-1u]>key){{s[j]=s[j-1u];--j;}} s[j]=key; }}\n {{ float med=percentile(s,QUAT_TREE_WINDOW_SIZE,0.5f),q1=percentile(s,QUAT_TREE_WINDOW_SIZE,0.25f),q3=percentile(s,QUAT_TREE_WINDOW_SIZE,0.75f); uint32_t b=a*{len(STATS)}u; out[b+0u]=mean;out[b+1u]=sqrtf(var);out[b+2u]=mn;out[b+3u]=mx;out[b+4u]=mx-mn;out[b+5u]=sqrtf(sq/(float)QUAT_TREE_WINDOW_SIZE);out[b+6u]=med;out[b+7u]=q3-q1;out[b+8u]=ab/(float)QUAT_TREE_WINDOW_SIZE;out[b+9u]=(float)cross/(float)(QUAT_TREE_WINDOW_SIZE-1u);out[b+10u]=wave; }} }} }}\nquat_feature_tree_class_t quat_feature_tree_predict_window(const float samples[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS]) {{ float f[{len(allf)}],sel[{len(selected)}]; int32_t ni=0; uint32_t step; if(samples==NULL)return QUAT_FEATURE_CLASS_UNKNOWN; features(samples,f);\n'''
    for pos, ix in enumerate(idxs): src += f' sel[{pos}u]=f[{int(ix)}u]; /* {selected[pos]} */\n'
    src += f''' for(step=0u;step<QUAT_TREE_NODE_COUNT;++step) {{ const quat_node_t *n; if(ni<0 || (uint32_t)ni>=QUAT_TREE_NODE_COUNT)return QUAT_FEATURE_CLASS_UNKNOWN; n=&nodes[ni]; if(n->feature<0)return (quat_feature_tree_class_t)n->cls; if((uint32_t)n->feature>=QUAT_TREE_FEATURE_COUNT)return QUAT_FEATURE_CLASS_UNKNOWN; ni=(sel[n->feature]<=n->threshold)?n->left:n->right; }} return QUAT_FEATURE_CLASS_UNKNOWN; }}\n'''
    cp.write_text(src,encoding='utf-8'); return cp,hp

def main():
    ap=argparse.ArgumentParser(description='Quaternion feature-engineered decision tree with RFE; exports JSON and STM32 C.')
    ap.add_argument('--horizontal',nargs='+',required=True,help='Horizontal quaternion CSV file(s)')
    ap.add_argument('--static',nargs='+',required=True,help='Static quaternion CSV file(s)')
    ap.add_argument('--vertical',nargs='+',required=True,help='Vertical quaternion CSV file(s)')
    ap.add_argument('--output-dir',default='quaternion_feature_rfe_results')
    ap.add_argument('--window-size',type=int,default=42); ap.add_argument('--stride',type=int,default=21)
    ap.add_argument('--n-features',type=int,default=12); ap.add_argument('--rfe-step',type=int,default=1)
    ap.add_argument('--train-fraction',type=float,default=.70); ap.add_argument('--validation-fraction',type=float,default=.15)
    ap.add_argument('--max-depth',type=int,default=None); ap.add_argument('--min-samples-leaf',type=int,default=1)
    ap.add_argument('--criterion',choices=['gini','entropy','log_loss'],default='gini'); ap.add_argument('--random-state',type=int,default=42)
    ap.add_argument('--convert-json',type=Path); ap.add_argument('--c-out-prefix',type=Path)
    args=ap.parse_args()
    try:
        if args.convert_json:
            cp,hp=generate_c(args.convert_json,args.c_out_prefix or args.convert_json.with_suffix('')); print(f'Generated C: {cp}\nGenerated header: {hp}'); return 0
        if args.window_size<2 or args.stride<1: ap.error('--window-size must be >=2 and --stride must be >=1')
        paths=[(Path(p),'Horizontal') for p in args.horizontal]+[(Path(p),'Static') for p in args.static]+[(Path(p),'Vertical') for p in args.vertical]
        recordings=[]
        for path,label in paths: recordings.append((label,load_recording(path,label)))
        counts={c:sum(1 for label,_ in recordings if label==c) for c in CLASSES}
        if args.n_features<1 or args.n_features>len(ALL_FEATURES): ap.error(f'--n-features must be 1..{len(ALL_FEATURES)}')
        split={'train':[],'validation':[],'test':[]}
        for label,df in recordings:
            parts=split_recording(df,args.train_fraction,args.validation_fraction)
            for k,part in parts.items():
                wf=window_segment(part,args.window_size,args.stride)
                if not wf.empty: split[k].append(wf)
        split={k:pd.concat(v,ignore_index=True) if v else pd.DataFrame() for k,v in split.items()}
        for k,df in split.items():
            if df.empty: raise ValueError(f'No {k} windows. Check recording length/window size.')
            print(f'{k.title():10}: {len(df):,} windows; classes={df.label.value_counts().to_dict()}')
        xcols=ALL_FEATURES; xtr=split['train'][xcols].to_numpy(float); ytr=split['train'].label.astype(str).to_numpy()
        if len(np.unique(ytr))<2: raise ValueError('Training split has fewer than two classes; check logs/splits.')
        selector=RFE(estimator=DecisionTreeClassifier(random_state=args.random_state),n_features_to_select=args.n_features,step=args.rfe_step)
        selector.fit(xtr,ytr); selected=[f for f,keep in zip(ALL_FEATURES,selector.support_) if keep]; idx=[ALL_FEATURES.index(f) for f in selected]
        model=DecisionTreeClassifier(criterion=args.criterion,max_depth=args.max_depth,min_samples_leaf=args.min_samples_leaf,random_state=args.random_state)
        model.fit(split['train'][selected].to_numpy(float),ytr)
        out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
        reports=[]; predrows=[]
        for name,df in split.items():
            X=df[selected].to_numpy(float); y=df.label.astype(str).to_numpy(); pred=model.predict(X); acc=accuracy_score(y,pred)
            print(f'\n{name.upper()} accuracy={acc:.4f}\n'+classification_report(y,pred,labels=CLASSES,zero_division=0))
            report=classification_report(y,pred,labels=CLASSES,output_dict=True,zero_division=0)
            for c in CLASSES:
                r=report[c]; reports.append({'split':name,'class':c,'precision':r['precision'],'recall':r['recall'],'f1_score':r['f1-score'],'support':r['support'],'accuracy_overall':acc})
            z=df[['label','source_file','window_start_row','window_end_row']].copy(); z['predicted_label']=pred; z['correct']=z.label.astype(str)==pred; z['split']=name; predrows.append(z)
        pd.DataFrame(reports).to_csv(out/'metrics_by_class.csv',index=False); allpred=pd.concat(predrows,ignore_index=True); allpred.to_csv(out/'predictions_all_splits.csv',index=False)
        allpred[(allpred.split=='test') & (~allpred.correct)].to_csv(out/'test_misclassifications.csv',index=False)
        rank=pd.DataFrame({'feature':ALL_FEATURES,'rfe_ranking':selector.ranking_,'selected_by_rfe':selector.support_}); im=dict(zip(selected,model.feature_importances_)); rank['final_tree_importance']=rank.feature.map(im).fillna(0); rank.sort_values(['selected_by_rfe','rfe_ranking','final_tree_importance'],ascending=[False,True,False]).to_csv(out/'rfe_feature_ranking.csv',index=False)
        (out/'decision_tree_features_rfe.txt').write_text(export_text(model,feature_names=selected,decimals=6),encoding='utf-8')
        test=split['test']; yp=model.predict(test[selected].to_numpy(float)); cm=confusion_matrix(test.label.astype(str),yp,labels=CLASSES); pd.DataFrame(cm,index=[f'Actual {c}' for c in CLASSES],columns=[f'Predicted {c}' for c in CLASSES]).to_csv(out/'confusion_matrix_test.csv')
        fig,ax=plt.subplots(figsize=(7,6)); ConfusionMatrixDisplay(cm,display_labels=CLASSES).plot(ax=ax,values_format='d',colorbar=False); fig.tight_layout(); fig.savefig(out/'confusion_matrix_test.png',dpi=150); plt.close(fig)
        fig,ax=plt.subplots(figsize=(11,6)); plot_tree(model,feature_names=selected,class_names=[str(c) for c in model.classes_],filled=False,rounded=True,max_depth=3,fontsize=7,ax=ax); fig.tight_layout(); fig.savefig(out/'tree_structure.png',dpi=150); plt.close(fig)
        jpath=out/'decision_tree_quaternion_features_rfe.json'; export_json(model,selected,idx,{n:int(r) for n,r in zip(ALL_FEATURES,selector.ranking_)},jpath,args); cp,hp=generate_c(jpath,out/'decision_tree_quaternion_features_rfe')
        t0=time.perf_counter(); model.predict(split['test'][selected].iloc[[0]].to_numpy(float)); latency=(time.perf_counter()-t0)*1e6
        summary={'classes':CLASSES,'channels':CHANNELS,'candidate_features':len(ALL_FEATURES),'selected_features':selected,'window_size_samples':args.window_size,'stride_samples':args.stride,'tree_depth':model.get_depth(),'leaf_count':model.get_n_leaves(),'node_count':model.tree_.node_count,'json_size_bytes':jpath.stat().st_size,'c_and_header_bytes':cp.stat().st_size+hp.stat().st_size,'single_python_prediction_us_rough':latency,'evaluation_note':'Chronological blocks within each file; not session-independent. Use multiple independently recorded logs per class for a reliable generalization test.','data_note':'Quaternion input columns must be complete, numeric q0-q3 columns in consistent component order and convention.'}
        (out/'model_summary.json').write_text(json.dumps(summary,indent=2,default=lambda v: int(v) if isinstance(v, np.integer) else float(v) if isinstance(v, np.floating) else str(v)),encoding='utf-8')
        print(f'\nSelected {len(selected)}/{len(ALL_FEATURES)} features: {selected}\nTree depth={model.get_depth()}, leaves={model.get_n_leaves()}, nodes={model.tree_.node_count}')
        print(f'Outputs: {out.resolve()}\nJSON: {jpath}\nC: {cp}\nHeader: {hp}')
        if any(n<3 for n in counts.values()): print('WARNING: fewer than 3 separate recording files for at least one class; session-independent evaluation is not possible.')
        return 0
    except Exception as e: print(f'ERROR: {e}',file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
