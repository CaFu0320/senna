#!/usr/bin/env python3
"""How redundant are the 36 engineered features? For each feature, a depth-2 decision tree
trained on that single feature (training windows) is scored on the validation+test windows.
Uses the same windows and split as model_raw_fe.py.
Usage: python supplementary_single_feature_check.py --horizontal H.csv --static S.csv --vertical V.csv"""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score
import model_raw_fe as m

ap = argparse.ArgumentParser()
ap.add_argument("--horizontal", nargs="+", required=True); ap.add_argument("--static", nargs="+", required=True)
ap.add_argument("--vertical", nargs="+", required=True); ap.add_argument("--window-size", type=int, default=42)
ap.add_argument("--stride", type=int, default=21); ap.add_argument("--out", default="extras/single_feature_accuracy.csv")
a = ap.parse_args()
recs = [(l, m.load_recording(Path(f), l, None)) for l, fs in [("Horizontal", a.horizontal), ("Static", a.static), ("Vertical", a.vertical)] for f in fs]
pieces, _ = m.assign_splits(recs, "auto", 0.70, 0.15, 42)
win = {s: pd.concat([m.windows_from_segment(f, a.window_size, a.stride) for f in fr], ignore_index=True) for s, fr in pieces.items()}
tr, ev = win["train"], pd.concat([win["validation"], win["test"]], ignore_index=True)
res = {}
for f in m.ALL_FEATURE_NAMES:
    st = DecisionTreeClassifier(max_depth=2, random_state=42).fit(tr[[f]].to_numpy(), tr["label"])
    res[f] = accuracy_score(ev["label"], st.predict(ev[[f]].to_numpy()))
s = pd.Series(res).sort_values(ascending=False)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
s.rename("val_test_accuracy").to_csv(a.out)
print(f"{int((s >= 0.95).sum())} of {len(s)} features reach >= 95 % accuracy on their own (val+test windows: {len(ev)})")
print(s.head(10).round(3).to_string())
