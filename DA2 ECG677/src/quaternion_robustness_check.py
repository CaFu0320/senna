#!/usr/bin/env python3
"""quaternion_robustness_check.py - does a quaternion model recognise the MOTION or just the ORIENTATION?

A quaternion describes how the board is oriented. If every activity was recorded with a
slightly different orientation, a tree can reach a high accuracy from the orientation alone,
and fail when the orientation drifts. This script tests that with the same loaders, windows and
default hyperparameters as the Task 4 / Task 5 scripts:

  1. QUAT (single samples) and the window models on the chronological 70/15/15 split
     (the protocol of Tasks 2-5), for three groups of window features:
        all 24 features | motion features only (variance, peak-to-peak) | level features only (mean, max, min, energy)
  2. Leave-one-time-block-out cross-validation: every recording is cut into 5 consecutive blocks,
     each block is held out in turn.
  3. Transfer: train on one dataset, test on the other (needs --quatlogs).

Usage
  python quaternion_robustness_check.py --horizontal Horizontal.csv --static Static.csv --vertical Vertical.csv \
      --quatlogs quatlogs --out robustness
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.tree import DecisionTreeClassifier

import model_quaternion_fe as q5

CH, CLASSES = q5.CHANNELS, q5.CLASSES
SETS = {
    "all 24 features": q5.ALL_FEATURES,
    "motion only (var, p2p)": [f"{c}__{s}" for c in CH for s in ("var", "p2p")],
    "level only (mean, max, min, energy)": [f"{c}__{s}" for c in CH for s in ("mean", "max", "min", "energy")],
}
K = 5


def dt():
    return DecisionTreeClassifier(random_state=42)          # same defaults as Tasks 2-5


def load(paths):
    return [(lab, q5.load_recording(Path(p), lab)) for lab, p in paths]


def chrono_split(recs, win, stride):
    s = {"train": [], "validation": [], "test": []}
    w = {"train": [], "validation": [], "test": []}
    for _, df in recs:
        for k, part in q5.split_recording(df, 0.70, 0.15).items():
            s[k].append(part)
            w[k].append(q5.window_segment(part, win, stride))
    return ({k: pd.concat(v, ignore_index=True) for k, v in s.items()},
            {k: pd.concat(v, ignore_index=True) for k, v in w.items()})


def blocks(recs, win, stride):
    smp, wnd = [], []
    for _, df in recs:
        n = len(df)
        for j in range(K):
            part = df.iloc[j * n // K:(j + 1) * n // K].copy()
            part["block"] = j
            smp.append(part)
            w = q5.window_segment(part, win, stride)
            w["block"] = j
            wnd.append(w)
    return pd.concat(smp, ignore_index=True), pd.concat(wnd, ignore_index=True)


def analyse(recs, win, stride):
    res = {}
    smp, wnd = chrono_split(recs, win, stride)
    m = dt().fit(smp["train"][CH], smp["train"]["label"])
    res["quat_samples_chronological"] = {s: round(accuracy_score(smp[s]["label"], m.predict(smp[s][CH])), 4)
                                         for s in smp} | {"n_test": len(smp["test"])}
    res["windows_chronological"] = {}
    for name, cols in SETS.items():
        mm = dt().fit(wnd["train"][cols], wnd["train"]["label"])
        res["windows_chronological"][name] = {s: round(accuracy_score(wnd[s]["label"], mm.predict(wnd[s][cols])), 4)
                                              for s in wnd} | {"n_test": len(wnd["test"])}
    S, Wd = blocks(recs, win, stride)
    folds = []
    for j in range(K):
        tr, te = S[S.block != j], S[S.block == j]
        p = dt().fit(tr[CH], tr["label"]).predict(te[CH])
        folds.append({"fold": j, "accuracy": round(accuracy_score(te["label"], p), 4),
                      "errors": {c: int(((te.label == c) & (p != c)).sum()) for c in CLASSES}})
    res["quat_samples_block_cv"] = {"folds": folds, "mean": round(float(np.mean([f["accuracy"] for f in folds])), 4),
                                    "min": round(float(np.min([f["accuracy"] for f in folds])), 4)}
    res["windows_block_cv"] = {}
    for name, cols in SETS.items():
        accs = []
        for j in range(K):
            tr, te = Wd[Wd.block != j], Wd[Wd.block == j]
            accs.append(round(accuracy_score(te["label"], dt().fit(tr[cols], tr["label"]).predict(te[cols])), 4))
        res["windows_block_cv"][name] = {"folds": accs, "mean": round(float(np.mean(accs)), 4), "min": round(float(min(accs)), 4)}
    allq = pd.concat([d for _, d in recs], ignore_index=True)
    res["class_means"] = {c: g[CH].mean().round(3).to_dict() for c, g in allq.groupby("label")}
    return res, smp, wnd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horizontal", required=True); ap.add_argument("--static", required=True); ap.add_argument("--vertical", required=True)
    ap.add_argument("--quatlogs", default=None, help="folder with Quat_Horizontal.csv, Quat_Static.csv, Quat_Vertical.csv")
    ap.add_argument("--out", default="robustness"); ap.add_argument("--window-size", type=int, default=42); ap.add_argument("--stride", type=int, default=21)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    A = load([("Horizontal", a.horizontal), ("Static", a.static), ("Vertical", a.vertical)])
    resA, smpA, wndA = analyse(A, a.window_size, a.stride)
    summary = {"main_dataset": resA}
    if a.quatlogs:
        q = Path(a.quatlogs)
        B = load([("Horizontal", q / "Quat_Horizontal.csv"), ("Static", q / "Quat_Static.csv"), ("Vertical", q / "Quat_Vertical.csv")])
        resB, smpB, wndB = analyse(B, a.window_size, a.stride)
        summary["quaternion_logs"] = resB
        # transfer: train on all of one dataset, test on all of the other
        fullA = pd.concat([d for _, d in A], ignore_index=True); fullB = pd.concat([d for _, d in B], ignore_index=True)
        wA = pd.concat([pd.concat(w, ignore_index=True) for w in [[q5.window_segment(d, a.window_size, a.stride)] for _, d in A]], ignore_index=True)
        wB = pd.concat([pd.concat(w, ignore_index=True) for w in [[q5.window_segment(d, a.window_size, a.stride)] for _, d in B]], ignore_index=True)
        tr = {}
        for nm, (s, t_) in {"main_to_logs": (fullA, fullB), "logs_to_main": (fullB, fullA)}.items():
            p = dt().fit(s[CH], s["label"]).predict(t_[CH])
            tr[nm] = {"samples_accuracy": round(accuracy_score(t_["label"], p), 4), "predicted_classes": pd.Series(p).value_counts().to_dict()}
        for nm, (s, t_) in {"main_to_logs": (wA, wB), "logs_to_main": (wB, wA)}.items():
            for fs in ("all 24 features", "motion only (var, p2p)"):
                cols = SETS[fs]
                p = dt().fit(s[cols], s["label"]).predict(t_[cols])
                tr[nm][f"windows_{fs}"] = round(accuracy_score(t_["label"], p), 4)
        summary["transfer"] = tr
    (out / "robustness_summary.json").write_text(json.dumps(summary, indent=2))

    # figure: leave-one-block-out accuracy
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for a_, key, title in [(ax[0], "main_dataset", "Task 1 recordings"), (ax[1], "quaternion_logs", "Quaternion-only logs")]:
        if key not in summary:
            a_.axis("off"); continue
        r = summary[key]
        series = {"QUAT, single samples": [f["accuracy"] for f in r["quat_samples_block_cv"]["folds"]]}
        series.update({f"windows: {n}": r["windows_block_cv"][n]["folds"] for n in SETS})
        w = 0.8 / len(series)
        for i, (n, v) in enumerate(series.items()):
            a_.bar(np.arange(K) + i * w - 0.4 + w / 2, [x * 100 for x in v], w, label=n)
        a_.set_xticks(range(K), [f"block {j + 1}" for j in range(K)]); a_.set_title(title)
        a_.set_ylim(40, 101); a_.grid(axis="y", alpha=0.3)
    ax[0].set_ylabel("Accuracy of the held-out block [%]")
    h, l = ax[0].get_legend_handles_labels(); fig.legend(h, l, loc="lower center", ncol=4, fontsize=8)
    fig.suptitle("Leave-one-time-block-out accuracy")
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(out / "block_cv.png", dpi=160); plt.close(fig)

    def show(res):
        print(" chronological, QUAT samples:", res["quat_samples_chronological"])
        for n, v in res["windows_chronological"].items():
            print(f"   windows {n:38s}", v)
        print(" block-CV QUAT samples: mean", res["quat_samples_block_cv"]["mean"], "min", res["quat_samples_block_cv"]["min"],
              [f["accuracy"] for f in res["quat_samples_block_cv"]["folds"]])
        for n, v in res["windows_block_cv"].items():
            print(f"   block-CV windows {n:38s}", v)
    print("=== Task 1 recordings ==="); show(resA)
    if "quaternion_logs" in summary:
        print("=== Quaternion-only logs ==="); show(summary["quaternion_logs"])
        print("=== Transfer ==="); print(json.dumps(summary["transfer"], indent=1))
    print("outputs ->", out)


if __name__ == "__main__":
    main()
