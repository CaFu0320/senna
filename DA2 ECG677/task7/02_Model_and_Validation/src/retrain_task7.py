#!/usr/bin/env python3
"""Reproduce Task 7 120-Hz QUAT+FE model training from the provided CSVs.

Notice: the supplied files contain earlier 100 Hz sessions appended to newer
120 Hz sessions. We keep only the latest long session, without crossing gaps.
Data source: quaternion x,y,z,w = q1,q2,q3,q4, mapped to q0=w,q1=x,q2=y,q3=z.
The experiment is a same-session chronological split, NOT independent trials.
"""
from __future__ import annotations
import json, pathlib, shutil, csv
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree
from sklearn.feature_selection import RFE, f_classif
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC={ 'Horizontal':'ispuHmotion120hz(1).csv',
      'Static':'ispuStatic120hz(1).csv',
      'Vertical':'ispuVmotion120hz(1).csv'}
CLASSES=['Horizontal','Static','Vertical']
QCH=['q0','q1','q2','q3']
STATS=['mean','var','max','min','p2p','energy']
FEATURES=[f'{q}__{f}' for q in QCH for f in STATS]
MOTION=[i for i,n in enumerate(FEATURES) if n.endswith('__var') or n.endswith('__p2p')]
SELECTED=[FEATURES[i] for i in MOTION]
WINDOW,STRIDE=42,21

def latest_120hz(fname):
    d=pd.read_csv(fname,comment='#')
    required=['time[us]','q1','q2','q3','q4']
    if list(d.columns)!=required:raise ValueError(f'Unexpected CSV header {d.columns.to_list()}')
    t=d['time[us]'].to_numpy(np.int64)
    cut=np.where(np.diff(t)>250000)[0]+1
    segments=np.split(np.arange(len(d)),cut)
    good=[]
    for ids in segments:
        if len(ids)<100:continue
        ss=d.iloc[ids]
        tt=ss['time[us]'].to_numpy()
        dt=np.diff(tt)
        hz=(len(ids)-1)*1e6/(tt[-1]-tt[0])
        if 115<=hz<=125 and np.median(dt)<9000:good.append((ss.copy(),hz))
    if not good:raise ValueError('No valid 120 Hz segment found!')
    ss,hz=good[-1]
    ss=ss.reset_index(drop=True)
    return ss,hz,[(len(ids),float((t[ids[-1]]-t[ids[0]])/1e6)) for ids in segments]

def extract_window(q):
    # q columns already ordered [w,x,y,z], float values from CSV.
    feat=[]
    a32=np.ascontiguousarray(q,dtype=np.float32)
    # Motion features match ISPU's two-pass float32 arithmetic, to prevent
    # edge cases where Python double precision and C float take different branches.
    for i in range(4):
        a=q[:,i]
        xf=a32[:,i]
        total=np.float32(0.0)
        lo=xf[0];hi=xf[0]
        for v in xf:
            if v<lo:lo=v
            if v>hi:hi=v
            total=np.float32(total+v)
        mean32=np.float32(total/np.float32(WINDOW))
        var32=np.float32(0.)
        for v in xf:
            dv=np.float32(v-mean32)
            var32=np.float32(var32+np.float32(dv*dv))
        var32=np.float32(var32/np.float32(WINDOW))
        p2p32=np.float32(hi-lo)
        feat += [float(a.mean()),float(var32),float(a.max()),float(a.min()),float(p2p32),float(np.mean(a*a))]
    return feat

def dataset():
    rows=[];info={}
    for activity,base in SRC.items():
        d,rate,segments=latest_120hz(ROOT/'data'/base)
        q=d[['q4','q1','q2','q3']].to_numpy(float)
        norm=np.linalg.norm(q,axis=1)
        nwin=(len(q)-WINDOW)//STRIDE+1
        skipped=[]
        for i in range(nwin):
            a=q[i*STRIDE:i*STRIDE+WINDOW]
            if np.any(abs(np.linalg.norm(a,axis=1)-1.0)>.02):
                skipped.append(i);continue
            # Purge neighboring windows between chronologically separate splits.
            if i<int(nwin*.60):part='train'
            elif int(nwin*.65)<=i<int(nwin*.80):part='validation'
            elif i>=int(nwin*.85):part='test'
            else:continue
            rows.append(dict(activity=activity,split=part,window_id=i,**dict(zip(FEATURES,extract_window(a)))))
        info[activity]={
            'samples_120hz':len(d),'duration_seconds':float((d['time[us]'].iloc[-1]-d['time[us]'].iloc[0])/1e6),
            'rate_hz':rate,'old_and_new_segments_n_duration':segments,'window_count':nwin,
            'excluded_windows_norm_outliers':skipped,'norm_median':float(np.median(norm)),
            'norm_min':float(norm.min()),'norm_max':float(norm.max()),
        }
    return pd.DataFrame(rows),info

def export_json(tree,selected_features,info,path,model_note):
    t=tree.tree_;nodes=[]
    for i in range(t.node_count):
        counts=t.value[i,0,:].astype(float)
        prob=(counts/counts.sum()).tolist() if counts.sum() else [0.,0.,0.]
        leaf=t.children_left[i]<0
        nodes.append({'node_id':i,'feature_index':None if leaf else int(t.feature[i]),
          'feature_name':None if leaf else selected_features[int(t.feature[i])],
          'threshold':None if leaf else float(t.threshold[i]),
          'left_child':None if leaf else int(t.children_left[i]),
          'right_child':None if leaf else int(t.children_right[i]),
          'is_leaf':bool(leaf),'predicted_class_index':int(np.argmax(counts)),
          'class_fraction_training':dict(zip(CLASSES,prob)),
          'leaf_purity_training':float(max(prob)),'weighted_training_samples':float(t.weighted_n_node_samples[i])})
    data={'format':'task7_quaternion_feature_decision_tree_120hz_v1',
         'source':'stable Madgwick ISPU 208 Hz, STM32/AlgoBuilder recording ~120.5 Hz',
         'quaternion_order_input_csv':'q1=x,q2=y,q3=z,q4=w',
         'quaternion_order_features':'q0=w,q1=x,q2=y,q3=z',
         'window_size_samples':WINDOW,'stride_samples':STRIDE,
         'candidate_features':FEATURES,'selected_features':selected_features,
         'classes':CLASSES,'tree_depth':int(t.max_depth),'node_count':int(t.node_count),
         'leaf_count':int(tree.get_n_leaves()),'notes':model_note,
         'nodes':nodes}
    path.write_text(json.dumps(data,indent=2))
    return data

def export_c(model,meta):
    # Model tree nodes are compact C structs (the ISPU Makefile compiles .c alongside main).
    t=model.tree_;p=ROOT/'ISPU_208hz'/'src'
    h='''#ifndef TASK7_QUAT_FE_TREE_H
#define TASK7_QUAT_FE_TREE_H
#include <stdint.h>
#define QUATFE_WINDOW 42u
#define QUATFE_STRIDE 21u
#define QUATFE_FEATURES 8u
#define QUATFE_NOT_READY 255u
/* Input order: q0=scalar(w), q1=x, q2=y, q3=z.
   Eight selected features (var, p2p) for each component in that order.
   Population variance (divide by 42), not sample variance.
   Model labels: 0 Horizontal; 1 Static; 2 Vertical. */
typedef struct {int16_t feature; int16_t left; int16_t right; float threshold; uint8_t predicted; float leaf_training_purity;} QuatFeNode;
typedef struct {uint32_t predicted_class;float leaf_training_purity;} QuatFePrediction;
QuatFePrediction quatfe_predict_features(const float x[QUATFE_FEATURES]);
void quatfe_window_features(const float buffer[QUATFE_WINDOW][4],float out[QUATFE_FEATURES]);
#endif
'''
    rows=[]
    for i in range(t.node_count):
        counts=t.value[i,0,:]; purity=float(counts.max()/counts.sum());leaf=t.feature[i]<0
        f=-1 if leaf else int(t.feature[i]); left=-1 if leaf else int(t.children_left[i]);right=-1 if leaf else int(t.children_right[i]); threshold=0.0 if leaf else float(t.threshold[i]);
        if not leaf and float(np.float32(threshold)) > threshold:
            threshold=float(np.nextafter(np.float32(threshold),np.float32(-np.inf)))
        pred=int(np.argmax(counts))
        rows.append('  {%d,%d,%d,%.12ef,%d,%.9ef}, /* node %d */'%(f,left,right,threshold,pred,purity,i))
    c='''#include "quat_fe_tree.h"
/* GENERATED from decision_tree_task7_120hz_motion_fe.json */
static const QuatFeNode kNodes[%d]={
%s
};
QuatFePrediction quatfe_predict_features(const float x[QUATFE_FEATURES]){
    uint16_t node=0;
    while(kNodes[node].feature>=0){
        const QuatFeNode *n=&kNodes[node];
        node=(uint16_t)(x[n->feature]<=n->threshold?n->left:n->right);
    }
    QuatFePrediction p={(uint32_t)kNodes[node].predicted,kNodes[node].leaf_training_purity};
    return p;
}
/* For simplicity the 42-sample caller passes a *chronological* or unordered
   window. Var and peak-to-peak are order-invariant; no sorting needed. */
void quatfe_window_features(const float b[QUATFE_WINDOW][4],float out[QUATFE_FEATURES]){
    for(unsigned j=0;j<4;j++){
        float min=b[0][j],max=b[0][j],sum=0.0f,var=0.0f;
        for(unsigned i=0;i<QUATFE_WINDOW;i++){
            float v=b[i][j]; if(v<min)min=v; if(v>max)max=v; sum+=v;
        }
        float mu=sum/(float)QUATFE_WINDOW;
        for(unsigned i=0;i<QUATFE_WINDOW;i++){
            float d=b[i][j]-mu;var+=d*d;
        }
        out[2*j]=var/(float)QUATFE_WINDOW;
        out[2*j+1]=max-min;
    }
}
'''%(t.node_count,'\n'.join(rows))
    (p/'quat_fe_tree.h').write_text(h)
    (p/'quat_fe_tree.c').write_text(c)

def main():
    df,info=dataset(); y=np.array([CLASSES.index(c) for c in df.activity]);
    X=df[FEATURES].to_numpy(float);S={k:(df.split==k).to_numpy() for k in ['train','validation','test']}
    # Standard Task5-style RFE comparison only; select on training portion.
    rf=RandomForestClassifier(n_estimators=100,random_state=42,n_jobs=-1)
    rfe=RFE(estimator=rf,n_features_to_select=8,step=1).fit(X[S['train']],y[S['train']])
    rfe_idx=np.flatnonzero(rfe.support_)
    base=DecisionTreeClassifier(max_depth=2,min_samples_leaf=2,random_state=42).fit(X[S['train']][:,rfe_idx],y[S['train']])
    # Motion-sensitive subset: a priori feature selection: 4x variance & p2p.
    # Tuning max_depth/min_samples_leaf evaluated on validation only.
    XX=X[:,MOTION];choices=[]
    for depth in [2,3,4,5]:
        for leaf in [2,4,8]:
            m=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=leaf,random_state=42).fit(XX[S['train']],y[S['train']])
            sc=accuracy_score(y[S['validation']],m.predict(XX[S['validation']]))
            choices.append((sc,-m.get_n_leaves(),depth,leaf,m))
    choices.sort(key=lambda z:(z[0],z[1]),reverse=True)
    val_score,_,depth,leaf,model=choices[0]
    print('SELECTED parameters',depth,leaf,'depth actual',model.get_depth())
    metrics={}
    for name,m,Z in [('standard_rfe',base,X[:,rfe_idx]),('motion_8features',model,XX)]:
        ms={'tree_nodes':int(m.tree_.node_count),'tree_depth':int(m.get_depth()),'leaves':int(m.get_n_leaves())}
        for split in S:
            yi=y[S[split]];yp=m.predict(Z[S[split]])
            ms[split]={'correct':int((yi==yp).sum()),'windows':int(len(yi)),'accuracy':float(accuracy_score(yi,yp)),
                'confusion_matrix':confusion_matrix(yi,yp,labels=[0,1,2]).tolist()}
        metrics[name]=ms
    metrics['candidate_features']=FEATURES
    metrics['motion_features_selected']=SELECTED
    metrics['standard_rfe_selected']=[FEATURES[i] for i in rfe_idx]
    metrics['model_selection']={'feature_method':'motion-sensitive variance and peak-to-peak from the same 24 QUAT+FE features', 'hyperparameter_choice':'validation accuracy, then fewest leaves','chosen_max_depth':depth,'chosen_min_samples_leaf':leaf}
    metrics['recordings']=info
    metrics['split_design']='Per-recording chronological 60% train / 15% validation / 15% test, with two 5% time gaps and no windows spanning gaps; same-session, not independent trials'
    (ROOT/'docs'/'evaluation_results.json').write_text(json.dumps(metrics,indent=2))
    export_json(model,SELECTED,info,ROOT/'models'/'decision_tree_task7_120hz_motion_fe.json',
                'Motion-only feature selection from 24 candidates; experiment evaluated on held-out time portions of SAME recordings. Not independent testing. Do not interpret leaf purity as calibrated confidence.')
    export_json(base,[FEATURES[i] for i in rfe_idx],info,ROOT/'models'/'decision_tree_task7_120hz_rfe_baseline.json',
                'Conventional RFE baseline retained for audit, not recommended for deployment due to poorer temporal holdout.')
    export_c(model,metrics)
    df.to_csv(ROOT/'docs'/'all_window_features.csv',index=False)
    (ROOT/'docs'/'test_predictions.csv').write_text(pd.DataFrame({
        'true_class':[CLASSES[i] for i in y[S['test']]],
        'predicted_class':[CLASSES[i] for i in model.predict(XX[S['test']])],
        'recording_window_id':df.loc[S['test'],'window_id'].to_numpy()}).to_csv(index=False))
    for nm,m,Z in [('baseline_RFE',base,X[:,rfe_idx]),('motion_tree',model,XX)]:
        yt=y[S['test']];yp=m.predict(Z[S['test']]);cm=confusion_matrix(yt,yp,labels=[0,1,2]);
        fig,ax=plt.subplots(figsize=(5.3,4.6));im=ax.imshow(cm,cmap='Blues')
        ax.set_xticks(range(3),CLASSES,rotation=20);ax.set_yticks(range(3),CLASSES)
        ax.set_xlabel('Predicted');ax.set_ylabel('Actual');ax.set_title(nm.replace('_',' ')+' — temporal test')
        for i in range(3):
            for j in range(3):ax.text(j,i,str(cm[i,j]),ha='center',va='center',color=('white' if cm[i,j]>cm.max()/2 else 'black'),fontsize=13)
        fig.colorbar(im,ax=ax,fraction=.046,pad=.04);fig.tight_layout()
        fig.savefig(ROOT/'docs'/f'{nm}_confusion.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(17,8));plot_tree(model,feature_names=SELECTED,class_names=CLASSES,filled=False,rounded=True,fontsize=8,ax=ax,impurity=False,proportion=False)
    fig.tight_layout();fig.savefig(ROOT/'docs'/'decision_tree_motion_features.png',dpi=180);plt.close(fig)
    with (ROOT/'docs'/'summary.txt').open('w') as o:
        o.write('Task 7 120-Hz new recordings, MOTION FEATURE (var+p2p) experiment\n')
        o.write('IMPORTANT: single run per activity; test is within the same recordings.\n')
        o.write(json.dumps(metrics,indent=2)+'\n')
        o.write('\nTree:\n'+export_text(model,feature_names=SELECTED,decimals=9))
    print('Data split',pd.crosstab(df.activity,df.split).to_string())
    for k,v in metrics.items():
        if k in ('motion_8features','standard_rfe'):
            print(k,[(spl,round(v[spl]['accuracy'],4),v[spl]['correct']) for spl in S],v['tree_nodes'])
    print('model tree:\n'+export_text(model,feature_names=SELECTED,decimals=9))
if __name__=='__main__':main()
