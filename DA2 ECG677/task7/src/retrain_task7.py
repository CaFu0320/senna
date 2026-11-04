#!/usr/bin/env python3
"""Train Task7 rotation-RELATIVE QUAT+FE model and export ISPU-compatible C.

Input CSV columns from AlgoBuilder: q1=x, q2=y, q3=z, q4=w. Labels come
EXCLUSIVELY from filename, NOT the stale 'Activity Number' output.

The 36 candidate features are window-relative quaternion statistics:
  24 = 6 stats * 4 quaternion components after q_rel = inverse(q[first])*q[i]
  6 = step squared norm statistics (q[i]-q[i-1])^2, i=1..41
  6 = anchor squared norm statistics (q[i]-q[first])^2, i=0..41
These representations are invariant under a fixed global quaternion rotation.
They require CHRONOLOGICAL windows, unlike previous var/p2p-only code.

Chronological train/validation/test per activity with 5%-window gaps.
A single recording per activity is available: THESE ARE NOT independent sessions.
"""
from __future__ import annotations
import json
import pathlib
from collections import Counter
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.tree import DecisionTreeClassifier, plot_tree, export_text
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = {'Curl':'curlTask7.csv', 'Lateral raise':'lateral_raisetask7.csv', 'Left punch':'leftpunchtask7.csv'}
CLASS_NAMES = ['Curl', 'Lateral raise', 'Left punch']
CLASS_IDS = {name:i for i,name in enumerate(CLASS_NAMES)}
WINDOW = 42
STRIDE = 21
STATS = ('mean','var','max','min','p2p','energy')
CHANNEL_NAMES = ['relq0','relq1','relq2','relq3','step_sq','anchor_sq']
FEATURES = [f'{name}__{stat}' for name in CHANNEL_NAMES for stat in STATS]
DATA_RATE_HZ = 120.48 # measured nominal export; window/stride are sample-based
NORM_TOLERANCE = 0.05

# Descriptive variant needed in the embedded code and the JSON.
FORMAT = 'task7_relative_quaternion_tree_v1'

def load_csv(path):
    d = pd.read_csv(path, comment='#')
    req = ['time[us]','q1','q2','q3','q4']
    if not all(s in d.columns for s in req):
        raise ValueError(f'{path}: missing columns; expected {req}; found {list(d.columns)}')
    t = d['time[us]'].to_numpy(np.int64)
    if not np.all(np.diff(t)>0):
        raise ValueError(f'{path}: non-increasing timestamps; split into individual sessions first')
    hz = (len(t)-1)*1e6/(t[-1]-t[0])
    if not (115.0 <= hz <= 125.0):
        raise ValueError(f'{path}: measured {hz:.2f} Hz; expected approx 120 Hz')
    q = d[['q4','q1','q2','q3']].to_numpy(np.float32)
    if not np.isfinite(q).all():
        raise ValueError(f'{path}: NaNs/infinities')
    norm = np.linalg.norm(q, axis=1)
    info = dict(raw_samples=int(len(q)), duration_sec=float((t[-1]-t[0])/1e6),
                measured_hz=float(hz), median_dt_us=float(np.median(np.diff(t))),
                corrupt_norm_samples=int(np.sum(np.abs(norm-1)>NORM_TOLERANCE)),
                stale_activity_number_counts={str(k):int(v) for k,v in d.get('Activity Number',pd.Series([],dtype=int)).value_counts().items()})
    return q, info

def relative_values(q):
    """Compute float32 matrix (42,6), step_sq first row unused (set to NaN).
    For any global quaternion R, inverse(R*q0)*(R*q_i)=inverse(q0)*q_i.
    """
    q=np.ascontiguousarray(q,dtype=np.float32)
    w,x,y,z=q[0]
    a,b,c,d=q.T
    r=np.stack([w*a+x*b+y*c+z*d,
                w*b-x*a-y*d+z*c,
                w*c+x*d-y*a-z*b,
                w*d-x*c+y*b-z*a],axis=1).astype(np.float32)
    step=np.full(len(q),np.nan,np.float32)
    step[1:]=np.sum(np.square(q[1:]-q[:-1]),axis=1,dtype=np.float32)
    anchor=np.sum(np.square(q-q[0]),axis=1,dtype=np.float32)
    return np.column_stack((r,step,anchor)).astype(np.float32)

def extract_window(q):
    if len(q)!=WINDOW:raise ValueError('Expected a 42-sample window')
    v=relative_values(q); out=[]
    for ch in range(6):
        x=v[1:,ch] if ch==4 else v[:,ch]
        avg=np.mean(x,dtype=np.float32)
        dev=x-avg
        var=np.mean(dev*dev,dtype=np.float32)
        energy=np.mean(x*x,dtype=np.float32)
        out.extend([float(avg),float(var),float(np.max(x)),float(np.min(x)),float(np.max(x)-np.min(x)),float(energy)])
    return out

def make_dataset():
    rows=[];metadata={};quats={}
    for activity,fn in FILES.items():
        q,info=load_csv(ROOT/'data'/fn)
        quats[activity]=q
        n_windows=(len(q)-WINDOW)//STRIDE+1
        part_counts=Counter();discarded=[];splits=[]
        for k in range(n_windows):
            a=q[k*STRIDE:k*STRIDE+WINDOW]
            bad=np.flatnonzero(np.abs(np.linalg.norm(a,axis=1)-1.0)>NORM_TOLERANCE)
            if len(bad):
                discarded.append(int(k));continue
            # 60% train, 5% purge, 15% validation, 5% purge, 15% test.
            if k<int(n_windows*.60): split='train'
            elif int(n_windows*.65)<=k<int(n_windows*.80):split='validation'
            elif k>=int(n_windows*.85):split='test'
            else:continue
            rows.append(dict(activity=activity,class_id=CLASS_IDS[activity],split=split,window_id=k,
                             **dict(zip(FEATURES,extract_window(a)))))
            part_counts[split]+=1
        info.update(window_count=int(n_windows),rejected_windows_corrupt_norm=len(discarded),
                    rejected_window_indices=discarded,usable_counts=dict(part_counts))
        metadata[activity]=info
    return pd.DataFrame(rows),metadata,quats

def train_model(df):
    X=df[FEATURES].to_numpy(np.float64);y=df['class_id'].to_numpy(int)
    S={key:(df.split==key).to_numpy() for key in ('train','validation','test')}
    # Model selection uses validation data ONLY; test remains held out.
    candidates=[]
    for depth in (2,3,4,5,6,8):
        for leaf in (2,4,8,12,20):
            model=DecisionTreeClassifier(criterion='gini',max_depth=depth,
                         min_samples_leaf=leaf,random_state=42).fit(X[S['train']],y[S['train']])
            val=float(accuracy_score(y[S['validation']],model.predict(X[S['validation']])))
            candidates.append((val,int(model.tree_.node_count),depth,leaf,model))
    # highest validation accuracy; fewest nodes, then shallowest.
    val,nodes,depth,leaf,model=sorted(candidates,key=lambda x:(-x[0],x[1],x[2],x[3]))[0]
    scores={}
    for name,mask in S.items():
        yt=y[mask];yp=model.predict(X[mask]);scores[name]={
            'windows':int(len(yt)),'correct':int(np.sum(yt==yp)),
            'accuracy':float(accuracy_score(yt,yp)),
            'confusion_matrix':confusion_matrix(yt,yp,labels=[0,1,2]).tolist(),
            'classification_report':classification_report(yt,yp,labels=[0,1,2],target_names=CLASS_NAMES,output_dict=True,zero_division=0)
        }
    return model,{'max_depth_parameter':depth,'min_samples_leaf':leaf,'chosen_validation_accuracy':val,
                  'nodes':nodes,'actual_depth':int(model.get_depth()),'leaves':int(model.get_n_leaves()),
                  'splits':scores},S

def export_json(model,metrics,meta):
    t=model.tree_;arr=[]
    for i in range(t.node_count):
        counts=t.value[i,0].astype(float)
        proportions=(counts/counts.sum()) if counts.sum()>0 else counts
        leaf=int(t.children_left[i])<0
        idx=None if leaf else int(t.feature[i])
        arr.append(dict(node_id=i,feature_index=idx,feature_name=None if leaf else FEATURES[idx],
                        threshold=None if leaf else float(t.threshold[i]),
                        left_child=None if leaf else int(t.children_left[i]),
                        right_child=None if leaf else int(t.children_right[i]),
                        predicted_class_index=int(np.argmax(counts)),
                        leaf_training_purity=float(np.max(proportions)),
                        training_class_distribution={CLASS_NAMES[j]:float(proportions[j]) for j in range(3)},
                        is_leaf=leaf))
    obj=dict(format=FORMAT,model_type='DecisionTreeClassifier',classes=CLASS_NAMES,
             labels={'Curl':0,'Lateral raise':1,'Left punch':2},
             q_csv_order=['q1=x','q2=y','q3=z','q4=w'],q_model_order=['w','x','y','z'],
             window=WINDOW,stride=STRIDE,feature_names=FEATURES,notes=(
             'Relative quaternion features; holdout is from the SAME session per class; '
             'training leaf purity is not probability confidence. Quaternion sign must be continuous.'),
             tree_depth=int(model.get_depth()),leaves=int(model.get_n_leaves()),
             node_count=int(t.node_count),nodes=arr)
    (ROOT/'models'/'decision_tree_task7_curl_lat_raise_punch.json').write_text(json.dumps(obj,indent=2))
    return obj

def export_c(tree):
    t=tree.tree_;n=t.node_count
    P=ROOT/'ISPU_208hz'/'src'
    h='''#ifndef TASK7_QUAT_FE_TREE_H
#define TASK7_QUAT_FE_TREE_H
#include <stdint.h>
#define QUATFE_WINDOW 42u
#define QUATFE_STRIDE 21u
#define QUATFE_FEATURES 36u
#define QUATFE_NOT_READY 255u
/* Class mapping: 0=Curl, 1=Lateral raise, 2=Left punch; 255=not ready.
   Quaternion input order is [w,x,y,z]. All 36 features are computed on
   RELATIVE quaternions / squared quaternion steps, never absolute angle.
   Sample order is required; 'oldest' is ring index of earliest sample. */
typedef struct {int16_t feature, left, right; float threshold; uint8_t predicted; float leaf_training_purity;} QuatFeNode;
typedef struct {uint32_t predicted_class; float leaf_training_purity;} QuatFePrediction;
void quatfe_window_features(const float ring[QUATFE_WINDOW][4], uint32_t oldest, float out[QUATFE_FEATURES]);
QuatFePrediction quatfe_predict_features(const float x[QUATFE_FEATURES]);
#endif
'''
    (P/'quat_fe_tree.h').write_text(h)
    rows=[]
    for i in range(n):
        counts=t.value[i,0];leaf=int(t.feature[i])<0
        fi=-1 if leaf else int(t.feature[i]);l=-1 if leaf else int(t.children_left[i]);r=-1 if leaf else int(t.children_right[i]);th=0.0 if leaf else float(t.threshold[i]);purity=float(counts.max()/counts.sum());pred=int(np.argmax(counts))
        # Conservative rounding of threshold to float32 avoids some boundary divergence.
        th32=np.float32(th)
        if not leaf and float(th32)>th:th32=np.nextafter(th32,np.float32(-np.inf))
        rows.append(f'    {{{fi}, {l}, {r}, {float(th32):.12e}f, {pred}u, {purity:.9e}f}}, /* node {i} */')
    top='''#include "quat_fe_tree.h"
/* This file is auto-generated by src/retrain_task7.py.
   Feature order: for [relq0..relq3, step_sq, anchor_sq], each channel has
   [mean,var,max,min,p2p,energy], with population variance.
   Importantly, the *chronological* first quaternion anchors the relative
   quaternion calculation, so a ring-buffer index must be supplied.
 */
static const QuatFeNode kNodes[%d]={
%s
};
QuatFePrediction quatfe_predict_features(const float features[QUATFE_FEATURES]) {
    uint16_t current=0u;
    for (unsigned depth=0u;depth<32u;depth++) {
        const QuatFeNode *p=&kNodes[current];
        if (p->feature<0) {
            QuatFePrediction ans={(uint32_t)p->predicted,p->leaf_training_purity};
            return ans;
        }
        current=(uint16_t)((features[p->feature]<=p->threshold)?p->left:p->right);
    }
    QuatFePrediction fail={QUATFE_NOT_READY,0.0f};return fail;
}
/* Compute six rotation-relative signal channels at one chronological index.
   relq = conj(anchor) * q, step_sq = squared 4D displacement from previous
   sample (undefined for index 0), anchor_sq = squared displacement from anchor.
   Conjugation assumes ~unit quaternions, checked in training CSVs.
   Input to this function is the ring array, so wrap-around is handled here. */
static void get_values(const float b[QUATFE_WINDOW][4],unsigned oldest,unsigned i,float v[6]) {
    const float *a=b[oldest];
    const float *q=b[(oldest+i)%%QUATFE_WINDOW];
    v[0]=a[0]*q[0]+a[1]*q[1]+a[2]*q[2]+a[3]*q[3];
    v[1]=a[0]*q[1]-a[1]*q[0]-a[2]*q[3]+a[3]*q[2];
    v[2]=a[0]*q[2]+a[1]*q[3]-a[2]*q[0]-a[3]*q[1];
    v[3]=a[0]*q[3]-a[1]*q[2]+a[2]*q[1]-a[3]*q[0];
    float sq=0.0f, dsq=0.0f;
    const float *prev=b[(oldest+i+QUATFE_WINDOW-1u)%%QUATFE_WINDOW];
    for(unsigned k=0u;k<4u;k++){
        float diff=q[k]-a[k];sq+=diff*diff;
        if(i>0u){float d=q[k]-prev[k];dsq+=d*d;}
    }
    v[4]=dsq; v[5]=sq;
}
void quatfe_window_features(const float b[QUATFE_WINDOW][4],uint32_t oldest,float out[QUATFE_FEATURES]) {
    oldest%%=QUATFE_WINDOW;
    float lo[6]={0},hi[6]={0},sum[6]={0},mu[6]={0},var[6]={0},energy[6]={0};
    float v[6];
    get_values(b,oldest,0u,v);
    for(unsigned k=0u;k<6u;k++){lo[k]=v[k];hi[k]=v[k];}
    /* Step channel starts at t1; its t0 statistic must not affect min/max. */
    get_values(b,oldest,1u,v);
    lo[4]=hi[4]=v[4];
    for(unsigned i=0u;i<QUATFE_WINDOW;i++){
        get_values(b,oldest,i,v);
        for(unsigned k=0u;k<6u;k++){
            if(k==4u && i==0u) continue;
            if(v[k]<lo[k])lo[k]=v[k];
            if(v[k]>hi[k])hi[k]=v[k];
            sum[k]+=v[k];
        }
    }
    for(unsigned k=0u;k<6u;k++)mu[k]=sum[k]/(k==4u?41.0f:42.0f);
    for(unsigned i=0u;i<QUATFE_WINDOW;i++){
        get_values(b,oldest,i,v);
        for(unsigned k=0u;k<6u;k++){
            if(k==4u && i==0u)continue;
            float diff=v[k]-mu[k];var[k]+=diff*diff;energy[k]+=v[k]*v[k];
        }
    }
    for(unsigned k=0u;k<6u;k++){
        const float N=k==4u?41.0f:42.0f;
        out[6u*k+0u]=mu[k];out[6u*k+1u]=var[k]/N;
        out[6u*k+2u]=hi[k];out[6u*k+3u]=lo[k];
        out[6u*k+4u]=hi[k]-lo[k];out[6u*k+5u]=energy[k]/N;
    }
}
'''%(n,'\n'.join(rows))
    (P/'quat_fe_tree.c').write_text(top)


def plots(df,model,S):
    X=df[FEATURES].to_numpy(float);y=df['class_id'].to_numpy(int);yp=model.predict(X[S['test']]);yt=y[S['test']]
    cm=confusion_matrix(yt,yp,labels=[0,1,2]);fig,ax=plt.subplots(figsize=(6.7,5.5));im=ax.imshow(cm,cmap='Blues')
    ax.set_xticks(range(3),CLASS_NAMES,rotation=12);ax.set_yticks(range(3),CLASS_NAMES)
    ax.set_xlabel('Predicted activity');ax.set_ylabel('Recorded activity');ax.set_title('Same-session chronological holdout — NOT independent testing')
    for r in range(3):
        for c in range(3):
            v=cm[r,c];ax.text(c,r,str(v),ha='center',va='center',color='white' if v>cm.max()/2 else 'black',fontsize=13)
    fig.colorbar(im,ax=ax,fraction=.046,pad=.04);fig.tight_layout()
    fig.savefig(ROOT/'docs'/'task7_confusion_matrix.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(22,10));plot_tree(model,feature_names=FEATURES,class_names=CLASS_NAMES,filled=False,rounded=True,impurity=False,ax=ax,fontsize=9)
    fig.tight_layout();fig.savefig(ROOT/'docs'/'task7_decision_tree.png',dpi=140);plt.close(fig)


def main():
    df,recordings,qs=make_dataset()
    model,selection,S=train_model(df)
    metrics=dict(note='Only one recording per class: all splits are from SAME recordings, not independent trials.',
                 classes=CLASS_IDS,recordings=recordings,settings=dict(window_samples=WINDOW,stride_samples=STRIDE,
                 sampling_rate_hz_nominal=DATA_RATE_HZ,invalid_norm_tolerance=NORM_TOLERANCE,
                 features=FEATURES,split='chronological: 60% train, 5% gap, 15% validation, 5% gap, 15% test'),
                 model=selection,feature_importances={FEATURES[i]:float(v) for i,v in enumerate(model.feature_importances_) if v>0.0})
    (ROOT/'docs'/'evaluation_results.json').write_text(json.dumps(metrics,indent=2))
    df.to_csv(ROOT/'docs'/'all_window_features.csv',index=False)
    xx=df[FEATURES].to_numpy(float)
    test=df.loc[S['test'],['activity','class_id','window_id']].copy()
    test['prediction']=model.predict(xx[S['test']]);test.to_csv(ROOT/'docs'/'test_predictions.csv',index=False)
    export_json(model,metrics,recordings);export_c(model);plots(df,model,S)
    summary=['Task 7: Curl (0), Lateral raise (1), Left punch (2)',
             'WARNING: single recording per class; chronological holdout from same session, not independent validation.',
             f'Model: nodes={model.tree_.node_count}, leaves={model.get_n_leaves()}, depth={model.get_depth()}, tuning={selection["max_depth_parameter"]}/{selection["min_samples_leaf"]}',
             'Splits: '+str({k:(v['correct'],v['windows'],v['accuracy']) for k,v in selection['splits'].items()}),
             'Test confusion matrix: '+str(selection['splits']['test']['confusion_matrix']),
             'Tree:\n'+export_text(model,feature_names=FEATURES,decimals=8)]
    (ROOT/'docs'/'summary.txt').write_text('\n'.join(summary))
    print('\n'.join(summary))

if __name__=='__main__':main()
