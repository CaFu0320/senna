#!/usr/bin/env python3
"""Raw quaternion decision-tree pipeline for MEMS Studio q0-q3 CSV logs.

TASK 4 (QUAT).  Changes made to the original script (everything else is unchanged):
  * JSON/C file names follow the assignment: decision_tree_quaternion.json (+ .c/.h)
  * extra outputs the assignment asks for: train/validation/test accuracy and the
    generalisation gap (accuracy_and_complexity_summary.csv), a feature-importance plot,
    model size in KB, and latency figures (host timing of the exported tree and an MCU estimate)
  * hyperparameters: the defaults are identical to model_raw.py (Task 2) and
    model_raw_fe.py (Task 3); keep them identical in every task.
  * the input CSV may be any log that contains q0,q1,q2,q3 columns, e.g. the Task 1 recordings.


Uses one row's q0,q1,q2,q3 values directly (no engineered features), creates
chronological train/validation/test splits within each recording, and exports
metrics, plots, a complete JSON tree, and matching C/H code for STM32 inference.

Install: python -m pip install numpy pandas scikit-learn matplotlib
Example (Windows):
 python .\\model_quaternion.py --horizontal Horizontal_Q.csv --static Static_Q.csv --vertical Vertical_Q.csv --output-dir quaternion_raw_results
For multiple independent sessions, pass multiple filenames after each class flag.
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree, _tree

FEATURES=['q0','q1','q2','q3']; CLASSES=['Horizontal','Static','Vertical']
def load_recording(path,label):
    if not path.is_file(): raise FileNotFoundError(f'CSV not found: {path}')
    df=pd.read_csv(path,comment='#',skip_blank_lines=True,engine='python').dropna(axis=1,how='all')
    df.columns=[str(c).strip() for c in df.columns]
    found=set(); chosen=[]
    for col in df.columns:
        base=re.sub(r'\.\d+$','',col).strip()
        if base in FEATURES and base not in found: found.add(base); chosen.append((col,base))
    missing=[f for f in FEATURES if f not in found]
    if missing: raise ValueError(f'{path}: missing {missing}. Headers found: {list(df.columns)}')
    out=pd.DataFrame({base:pd.to_numeric(df[src],errors='coerce') for src,base in chosen})
    out=out.replace([np.inf,-np.inf],np.nan).dropna(subset=FEATURES).reset_index(drop=True)
    if len(out)<30: raise ValueError(f'{path} has only {len(out)} usable q0-q3 rows; log is too short or incomplete.')
    out['label']=label; out['source_file']=path.name; out['source_row']=np.arange(len(out))
    print(f'Loaded {len(out):,} samples: {path} -> {label}')
    return out

def cident(s):
    s=re.sub(r'[^A-Za-z0-9_]','_',str(s).upper()); return ('CLASS_' if not s or s[0].isdigit() else '')+s
def cf(v):
    s=format(float(v),'.9g')
    if '.' not in s and 'e' not in s.lower(): s += '.0'
    return s+'f'
def export_json(model,path,args):
    t=model.tree_; classes=[str(c) for c in model.classes_]; nodes=[]
    for i in range(t.node_count):
        fi=int(t.feature[i]); leaf=fi==_tree.TREE_UNDEFINED; counts=[float(x) for x in t.value[i][0]]; pred=int(np.argmax(counts))
        nodes.append({'node_id':i,'feature_index':None if leaf else fi,'feature_name':None if leaf else FEATURES[fi],
            'threshold':None if leaf else float(t.threshold[i]),'left_child':None if leaf else int(t.children_left[i]),
            'right_child':None if leaf else int(t.children_right[i]),'is_leaf':bool(leaf),
            'predicted_class_index':pred,'predicted_class':classes[pred] if leaf else None,
            'class_counts':{classes[j]:counts[j] for j in range(len(classes))},'samples':int(t.n_node_samples[i])})
    payload={'format':'quaternion_raw_decision_tree_v1','features':FEATURES,'classes':classes,
        'tree_depth':int(model.get_depth()),'leaf_count':int(model.get_n_leaves()),'node_count':int(t.node_count),
        'criterion':args.criterion,'max_depth_setting':args.max_depth,'min_samples_leaf':args.min_samples_leaf,
        'nodes':nodes,'note':'One quaternion sample per prediction; q0-q3 order and convention must match the training CSV.'}
    path.write_text(json.dumps(payload,indent=2),encoding='utf-8')
def generate_c(json_path,prefix):
    p=json.loads(json_path.read_text(encoding='utf-8'))
    if p.get('format')!='quaternion_raw_decision_tree_v1': raise ValueError('Unsupported JSON tree format')
    nodes=p['nodes']; classes=p['classes']; prefix.parent.mkdir(parents=True,exist_ok=True)
    hp=prefix.with_suffix('.h'); cp=prefix.with_suffix('.c'); guard=re.sub(r'\W','_',prefix.name.upper())+'_H'
    enums=',\n'.join(f' QUAT_RAW_CLASS_{cident(c)} = {i}' for i,c in enumerate(classes))+',\n QUAT_RAW_CLASS_UNKNOWN = 255'
    hp.write_text(f'''/* Auto-generated raw quaternion tree; input order q0,q1,q2,q3. */\n#ifndef {guard}\n#define {guard}\n#include <stdint.h>\ntypedef enum {{\n{enums}\n}} quat_raw_tree_class_t;\nquat_raw_tree_class_t quat_raw_tree_predict(const float q[4]);\n#endif\n''',encoding='utf-8')
    rows=[]
    for n in nodes:
        if n['is_leaf']: fi=-1; th='0.0f'; left=right=-1
        else: fi=int(n['feature_index']); th=cf(n['threshold']); left=int(n['left_child']); right=int(n['right_child'])
        rows.append(f" {{{fi}, {th}, {left}, {right}, {int(n['predicted_class_index'])}u}},")
    cp.write_text(f'''/* Auto-generated from {json_path.name}; do not edit. */\n#include "{hp.name}"\n#include <stddef.h>\ntypedef struct {{ int8_t feature; float threshold; int32_t left,right; uint8_t cls; }} node_t;\nstatic const node_t nodes[{len(nodes)}]={{\n{chr(10).join(rows)}\n}};\nquat_raw_tree_class_t quat_raw_tree_predict(const float q[4]) {{ int32_t n=0; uint32_t steps; if(q==NULL)return QUAT_RAW_CLASS_UNKNOWN; for(steps=0;steps<{len(nodes)}u;++steps){{ const node_t *p; if(n<0||(uint32_t)n>={len(nodes)}u)return QUAT_RAW_CLASS_UNKNOWN; p=&nodes[n]; if(p->feature<0)return (quat_raw_tree_class_t)p->cls; if((uint32_t)p->feature>=4u)return QUAT_RAW_CLASS_UNKNOWN; n=(q[p->feature]<=p->threshold)?p->left:p->right; }} return QUAT_RAW_CLASS_UNKNOWN; }}\n''',encoding='utf-8')
    return cp,hp


MCU_CLOCK_HZ=84e6; CYCLES_PER_NODE=12   # NUCLEO-F401RE; rough cost of one tree level (load, compare, branch)
def add_report_outputs(model,splits,accs,out,jp,cp,hp,summary,args):
    """Accuracy/gap table, importance plot, depth profile, latency estimates (added for the report)."""
    train_acc,val_acc,test_acc=accs['train'],accs['validation'],accs['test']
    t=model.tree_; depth=np.zeros(t.node_count,dtype=int)
    for i in range(t.node_count):
        for ch in (t.children_left[i],t.children_right[i]):
            if ch!=-1: depth[ch]=depth[i]+1
    leaf=t.children_left==t.children_right
    pd.DataFrame([{'depth':d,'nodes':int((depth==d).sum()),'leaves':int(((depth==d)&leaf).sum())} for d in range(depth.max()+1)]).to_csv(out/'depth_profile.csv',index=False)
    pd.DataFrame([{'train_accuracy':train_acc,'validation_accuracy':val_acc,'test_accuracy':test_acc,
        'generalization_gap_train_minus_test':train_acc-test_acc,'tree_depth':int(model.get_depth()),
        'leaf_count':int(model.get_n_leaves()),'node_count':int(t.node_count)}]).to_csv(out/'accuracy_and_complexity_summary.csv',index=False)
    imp=pd.DataFrame({'feature':FEATURES,'importance':model.feature_importances_}).sort_values('importance',ascending=True)
    fig,ax=plt.subplots(figsize=(7,3.8)); bars=ax.barh(imp.feature,imp.importance,color='steelblue'); ax.bar_label(bars,fmt='%.3f')
    ax.set_xlabel('Gini importance'); ax.set_title('Quaternion component importance'); ax.grid(axis='x',alpha=.3); fig.tight_layout()
    fig.savefig(out/'feature_importance.png',dpi=160); plt.close(fig)
    nodes={n['node_id']:n for n in json.loads(jp.read_text())['nodes']}
    X=splits['test'][FEATURES].to_numpy(float); reps=max(1,5000//len(X)); t0=time.perf_counter()
    for _ in range(reps):
        for x in X:
            n=nodes[0]
            while not n['is_leaf']: n=nodes[n['left_child']] if x[n['feature_index']]<=n['threshold'] else nodes[n['right_child']]
    walk_us=(time.perf_counter()-t0)/(reps*len(X))*1e6
    t0=time.perf_counter()
    for _ in range(300): model.predict(X[:1])
    single_us=(time.perf_counter()-t0)/300*1e6
    summary.update({'task':'Task 4 - QUAT (q0,q1,q2,q3)','features':FEATURES,'classes':[str(c) for c in model.classes_],
        'train_samples':int(len(splits['train'])),'validation_samples':int(len(splits['validation'])),'test_samples':int(len(splits['test'])),
        'split_mode':'chronological','criterion':args.criterion,'max_depth_setting':args.max_depth,'min_samples_leaf':args.min_samples_leaf,
        'train_accuracy':float(train_acc),'validation_accuracy':float(val_acc),'test_accuracy':float(test_acc),
        'generalization_gap_train_minus_test':float(train_acc-test_acc),
        'json_size_kb':round(jp.stat().st_size/1024,3),'c_source_and_header_combined_bytes':int(cp.stat().st_size+hp.stat().st_size),
        'tree_depth':int(model.get_depth()),'leaf_count':int(model.get_n_leaves()),'node_count':int(t.node_count),
        'embedded_tree_size_bytes_est':int(t.node_count*9),'importance':dict(zip(FEATURES,[float(v) for v in model.feature_importances_])),
        'json_walk_us':float(walk_us),'sklearn_single_call_us':float(single_us),
        'mcu_tree_worst_case_us_est':float(model.get_depth()*CYCLES_PER_NODE/MCU_CLOCK_HZ*1e6),
        'latency_note':'Host timings show relative cost only; the MCU figure is an estimate (12 cycles per tree level at 84 MHz).'})

def main():
    ap=argparse.ArgumentParser(description='Raw q0-q3 decision tree, chronological evaluation, JSON and C export')
    ap.add_argument('--horizontal',nargs='+',required=True); ap.add_argument('--static',nargs='+',required=True); ap.add_argument('--vertical',nargs='+',required=True)
    ap.add_argument('--output-dir',default='quaternion_raw_results'); ap.add_argument('--train-fraction',type=float,default=.7); ap.add_argument('--validation-fraction',type=float,default=.15)
    ap.add_argument('--max-depth',type=int,default=None); ap.add_argument('--min-samples-leaf',type=int,default=1); ap.add_argument('--criterion',choices=['gini','entropy','log_loss'],default='gini'); ap.add_argument('--random-state',type=int,default=42)
    ap.add_argument('--convert-json',type=Path); ap.add_argument('--c-out-prefix',type=Path)
    args=ap.parse_args()
    try:
        if args.convert_json:
            cp,hp=generate_c(args.convert_json,args.c_out_prefix or args.convert_json.with_suffix('')); print(f'C: {cp}\nHeader: {hp}'); return 0
        if args.train_fraction<=0 or args.validation_fraction<=0 or args.train_fraction+args.validation_fraction>=1: ap.error('train and validation fractions must be positive and sum to less than 1')
        splits={'train':[],'validation':[],'test':[]}; nfiles={c:0 for c in CLASSES}
        for label,files in [('Horizontal',args.horizontal),('Static',args.static),('Vertical',args.vertical)]:
            for file in files:
                df=load_recording(Path(file),label); n=len(df); a=int(n*args.train_fraction); b=int(n*(args.train_fraction+args.validation_fraction))
                if a<1 or b<=a or b>=n: raise ValueError(f'{file}: too short for chronological split')
                for k,part in [('train',df.iloc[:a]),('validation',df.iloc[a:b]),('test',df.iloc[b:])]: splits[k].append(part.copy())
                nfiles[label]+=1
        splits={k:pd.concat(v,ignore_index=True) for k,v in splits.items()}
        model=DecisionTreeClassifier(criterion=args.criterion,max_depth=args.max_depth,min_samples_leaf=args.min_samples_leaf,random_state=args.random_state)
        model.fit(splits['train'][FEATURES],splits['train']['label'])
        out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True); rows=[]; preds=[]; accs={}
        for k,df in splits.items():
            y=df.label.astype(str); pred=model.predict(df[FEATURES]); acc=accuracy_score(y,pred); accs[k]=acc
            print(f'\n{k.upper()} accuracy={acc:.4f}\n'+classification_report(y,pred,labels=CLASSES,zero_division=0))
            rep=classification_report(y,pred,labels=CLASSES,output_dict=True,zero_division=0)
            for c in CLASSES: rows.append({'split':k,'class':c,'precision':rep[c]['precision'],'recall':rep[c]['recall'],'f1_score':rep[c]['f1-score'],'support':rep[c]['support'],'accuracy_overall':acc})
            z=df[['label','source_file','source_row']].copy(); z['predicted_label']=pred; z['correct']=z.label.astype(str)==z.predicted_label; z['split']=k; preds.append(z)
        pd.DataFrame(rows).to_csv(out/'metrics_by_class.csv',index=False); allp=pd.concat(preds,ignore_index=True); allp.to_csv(out/'predictions_all_splits.csv',index=False); allp[(allp.split=='test')&(~allp.correct)].to_csv(out/'test_misclassifications.csv',index=False)
        cm=confusion_matrix(splits['test'].label,splits['test'].assign(pred=model.predict(splits['test'][FEATURES])).pred,labels=CLASSES)
        pd.DataFrame(cm,index=[f'Actual {c}' for c in CLASSES],columns=[f'Predicted {c}' for c in CLASSES]).to_csv(out/'confusion_matrix_test.csv')
        fig,ax=plt.subplots(figsize=(7,6)); ConfusionMatrixDisplay(cm,display_labels=CLASSES).plot(ax=ax,values_format='d',colorbar=False); fig.tight_layout(); fig.savefig(out/'confusion_matrix_test.png',dpi=150); plt.close(fig)
        fig,ax=plt.subplots(figsize=(10,6)); plot_tree(model,feature_names=FEATURES,class_names=[str(c) for c in model.classes_],max_depth=4,rounded=True,filled=False,fontsize=8,ax=ax); fig.tight_layout(); fig.savefig(out/'tree_structure.png',dpi=150); plt.close(fig)
        (out/'decision_tree_rules.txt').write_text(export_text(model,feature_names=FEATURES),encoding='utf-8')
        (out/'feature_importance.csv') if False else None
        pd.DataFrame({'feature':FEATURES,'importance':model.feature_importances_}).sort_values('importance',ascending=False).to_csv(out/'feature_importance.csv',index=False)
        jp=out/'decision_tree_quaternion.json'; export_json(model,jp,args); cp,hp=generate_c(jp,out/'decision_tree_quaternion')
        summary={'samples':{k:int(len(v)) for k,v in splits.items()},'recording_files_per_class':nfiles,'tree_depth':int(model.get_depth()),'leaf_count':int(model.get_n_leaves()),'node_count':int(model.tree_.node_count),'json_size_bytes':int(jp.stat().st_size),'evaluation_note':'Chronological blocks within each recording. Adjacent time samples are correlated; use multiple sessions per class for stronger evaluation.'}
        add_report_outputs(model,splits,accs,out,jp,cp,hp,summary,args)
        (out/'model_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print(f'\nTree depth={model.get_depth()}, leaves={model.get_n_leaves()}, nodes={model.tree_.node_count}\nOutputs: {out.resolve()}\nJSON: {jp}\nC: {cp}\nHeader: {hp}')
        if any(v<3 for v in nfiles.values()): print('WARNING: fewer than 3 independent recordings for at least one class; test results do not measure generalization to unseen sessions.')
        return 0
    except Exception as e: print(f'ERROR: {e}',file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
