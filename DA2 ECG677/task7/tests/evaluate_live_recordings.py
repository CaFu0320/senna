#!/usr/bin/env python3
"""Evaluate NEW, labeled, independent live MEMS Studio recordings.
Usage:
 python tests/evaluate_live_recordings.py --curl path/to/curl_live.csv \
   --lateral path/to/lateral_live.csv --punch path/to/punch_live.csv

Ground truth is given by the CLI arguments / recorded exercise, not by
previous-model prediction fields from the training files.
"""
import argparse
import pathlib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix,classification_report,accuracy_score

p=argparse.ArgumentParser()
p.add_argument('--curl',type=pathlib.Path,required=True,help='Independent new CURL recording')
p.add_argument('--lateral',type=pathlib.Path,required=True,help='Independent new LATERAL RAISE recording')
p.add_argument('--punch',type=pathlib.Path,required=True,help='Independent new LEFT PUNCH recording')
p.add_argument('--discard-first-sec',type=float,default=2.5,help='Ignore first seconds (startup/transitions), default 2.5')
args=p.parse_args()
names=['Curl','Lateral raise','Left punch'];ytrue=[];ypred=[]
for classid,path in enumerate([args.curl,args.lateral,args.punch]):
    d=pd.read_csv(path,comment='#')
    col=next((c for c in d.columns if c.strip().lower() in ('activity number','activity class id','activity_id','activity')),None)
    if col is None:raise ValueError(f'{path}: no activity prediction column in {list(d.columns)}')
    tcol='time[us]' if 'time[us]' in d.columns else None
    if tcol:
        t=pd.to_numeric(d[tcol],errors='coerce')
        d=d.loc[(t-t.iloc[0])/1e6>=args.discard_first_sec]
    pred=pd.to_numeric(d[col],errors='coerce')
    pred=pred[pred.isin([0,1,2])].astype(int).to_numpy()
    if not len(pred):
        raise ValueError(f'{path}: no valid 0/1/2 predictions; check calibration status and new firmware')
    ytrue.extend([classid]*len(pred));ypred.extend(pred)
    print(f'{names[classid]}: {len(pred)} predictions; most common class: {names[np.bincount(pred,minlength=3).argmax()]}')
cm=confusion_matrix(ytrue,ypred,labels=[0,1,2]);print('\nNEW LIVE DATA ONLY:')
print('Rows=real exercise, columns=predicted; order:',names)
print(cm)
print('Sample-level accuracy:',accuracy_score(ytrue,ypred))
print(classification_report(ytrue,ypred,labels=[0,1,2],target_names=names,zero_division=0))
print('Warning: successive predictions are correlated (overlapping windows).')
