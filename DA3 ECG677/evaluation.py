#!/usr/bin/env python3
"""DA3 required script #5: evaluate models on HELD-OUT recordings.

Uses saved, reproducible test/validation tensors and actual trained networks.
Reports precision, recall, F1, classification accuracy, prediction CSVs, and
side-by-side confusion plots for each Task 1 and Task 2 Float32/Int8 pair.

Usage (TensorFlow needed): python evaluation.py --task both
Artifact-only inspection: python evaluation.py --verify-only
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score
from data_prep import ROOT


def saved_paths(task: str, source: str) -> tuple[Path, Path, Path]:
    if source == 'original':
        folder = ROOT / f'models/{task}'
    else:
        folder = ROOT / f'results/retrained/{task}'
    a,b=(('quaternion_float32.h5','quaternion_int8.tflite') if task=='task1'
         else ('quaternion_tfr_float32.h5','quaternion_tfr_int8.tflite'))
    return folder/a, folder/b, ROOT/f'data/derived/{task}_evaluation.npz'


def verify_artifacts(task: str, source: str, int8_source: str) -> None:
    """No TensorFlow needed: verify test tensors, labels, model paths, metadata."""
    float_path, int8_path, data_path = saved_paths(task, source)
    if int8_source == "requantized":
        int8_path = ROOT / f"results/requantized/{source}/{task}/{task}_requantized_int8.tflite"
    print(f'[{task.upper()}] Float32 model: {float_path} ({"present" if float_path.is_file() else "MISSING"})')
    print(f'[{task.upper()}] Int8 model: {int8_path} ({"present" if int8_path.is_file() else "MISSING"})')
    if not data_path.exists():
        raise FileNotFoundError(data_path)
    with np.load(data_path) as npz:
        for split in ['train','val','test']:
            X=npz[f'X_{split}']; y=npz[f'y_{split}']
            groups=npz[f'{split}_groups']
            print(f'    {split}: {len(X)} windows, shape {X.shape[1:]}, groups={sorted(set(groups.tolist()))}')
            assert len(X)==len(y)==len(groups)
        assert not (set(npz['train_groups']) & set(npz['val_groups']))
        assert not (set(npz['train_groups']) & set(npz['test_groups']))
        assert not (set(npz['val_groups']) & set(npz['test_groups']))
    print(f'    Confirmed: no recordings overlap between train/validation/test within {task}')


def run_float32(model, X: np.ndarray) -> np.ndarray:
    return np.asarray(model.predict(X.astype(np.float32), verbose=0)).argmax(axis=1)


def run_int8(tf, model_path: Path, X: np.ndarray) -> np.ndarray:
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    quant = inp.get('quantization', (0., 0))
    results=[]
    for sample in X:
        array=sample[np.newaxis,...].astype(np.float32)
        if np.issubdtype(inp['dtype'], np.integer):
            scale,zero=quant
            if scale <= 0: raise ValueError(f'Invalid TFLite input scale {scale}')
            lim=np.iinfo(inp['dtype'])
            array=np.clip(np.rint(array / scale + zero),lim.min,lim.max).astype(inp['dtype'])
        else:
            array=array.astype(inp['dtype'])
        interpreter.set_tensor(inp['index'], array)
        interpreter.invoke()
        output=interpreter.get_tensor(out['index']).reshape(-1)
        results.append(int(np.argmax(output)))
    return np.asarray(results,dtype=np.int64)


def plot_side_by_side(results: list[tuple[str,np.ndarray,np.ndarray]], names: list[str], target: Path) -> None:
    """Create side-by-side confusion matrices with consistent class order."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes=plt.subplots(1,len(results),figsize=(11,4.6),squeeze=False)
    for ax,(name,true,pred) in zip(axes[0],results):
        cm=confusion_matrix(true,pred,labels=np.arange(len(names)))
        ax.imshow(cm,cmap='Blues')
        ax.set_xticks(np.arange(len(names)),names,rotation=30,ha='right')
        ax.set_yticks(np.arange(len(names)),names)
        ax.set_xlabel('Predicted');ax.set_ylabel('Actual');ax.set_title(name)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):ax.text(j,i,str(cm[i,j]),ha='center',va='center')
    fig.tight_layout();fig.savefig(target,dpi=160);plt.close(fig)


def evaluate(task: str, source: str, int8_source: str) -> None:
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise SystemExit('TensorFlow is needed for actual model inference: python -m pip install -r requirements.txt') from exc
    float_path,int8_path,data_path=saved_paths(task,source)
    if int8_source == "requantized":
        int8_path=ROOT / f"results/requantized/{source}/{task}/{task}_requantized_int8.tflite"
    if not float_path.exists() or not int8_path.exists():
        raise FileNotFoundError(f'Expected {float_path} and {int8_path}')
    model=tf.keras.models.load_model(str(float_path),compile=False)
    folder=ROOT/f'results/evaluation/{source}/{task}/{int8_source}';folder.mkdir(parents=True,exist_ok=True)
    results=[]; final=[]
    with np.load(data_path) as data:
        names=data['class_names'].astype(str).tolist()
        for split in ['val','test']:
            X=data[f'X_{split}'];y=data[f'y_{split}']
            float_pred=run_float32(model,X)
            int8_pred=run_int8(tf,int8_path,X)
            for modelname,pred in [('Float32',float_pred),('Int8',int8_pred)]:
                report=classification_report(y,pred,labels=list(range(len(names))),target_names=names,
                                             output_dict=True,zero_division=0)
                pd.DataFrame(report).transpose().to_csv(folder/f'{split}_{modelname.lower()}_per_class.csv')
                pd.DataFrame(confusion_matrix(y,pred,labels=list(range(len(names)))),index=names,columns=names).to_csv(folder/f'{split}_{modelname.lower()}_confusion.csv')
                results.append({'task':task,'model':modelname,'split':split,
                                'accuracy':float(accuracy_score(y,pred)),
                                'precision_macro':float(report['macro avg']['precision']),
                                'recall_macro':float(report['macro avg']['recall']),
                                'f1_macro':float(report['macro avg']['f1-score'])})
            if split=='test':
                final=[('Float32',y,float_pred),('Int8',y,int8_pred)]
                pd.DataFrame({'true':np.asarray(names)[y],'float32_pred':np.asarray(names)[float_pred],
                              'int8_pred':np.asarray(names)[int8_pred]}).to_csv(folder/'test_predictions.csv',index=False)
    pd.DataFrame(results).to_csv(folder/'evaluation_metrics.csv',index=False)
    plot_side_by_side(final,names,folder/'confusion_matrices_side_by_side.png')
    print(pd.DataFrame(results).to_string(index=False))
    print(f'[DONE] New evaluation results: {folder}')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',choices=['task1','task2','both'],default='both')
    parser.add_argument('--source',choices=['original','retrained'],default='original')
    parser.add_argument('--verify-only',action='store_true',help='Inspect model files and holdout splits without TensorFlow')
    parser.add_argument('--int8-source', choices=['original','requantized'], default='original', help='Use supplied or independently requantized Int8 network')
    args=parser.parse_args()
    for task in (['task1','task2'] if args.task=='both' else [args.task]):
        verify_artifacts(task,args.source,args.int8_source)
        if not args.verify_only:evaluate(task,args.source,args.int8_source)


if __name__=='__main__':
    main()
