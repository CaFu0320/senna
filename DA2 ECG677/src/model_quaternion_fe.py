#!/usr/bin/env python3
"""Task 5 - QUAT+FE: quaternion window features + feature selection (ANOVA + RFE) -> decision tree.

Corrected version of quaternion_feature_rfe_pipeline.py. Unchanged: loading of the q0..q3
columns, the chronological per-recording split, windows that never cross a split boundary,
default window of 42 samples with stride 21 (50 % overlap, the same as Task 3), the C export.
Changed, and why
  1. Features are the six statistics the assignment lists (mean, variance, max, min,
     peak-to-peak, energy) for each quaternion component: 4 x 6 = 24 candidate features
     (the old script used 11 statistics = 44 features, which is not comparable with Task 3).
  2. ANOVA F-statistic (and p-value) of every candidate feature is computed on the training
     windows (required output) and saved to anova_f_statistics.csv.
  3. RFE uses a random-forest estimator. With a single decision tree one feature already
     separates the classes, so 22 of 24 features get importance 0 and RFE just removes the
     features in column order. The top K (default 8) of the RFE ranking are kept.
  4. The final classifier is a DecisionTreeClassifier with the SAME default hyperparameters as
     Tasks 2-3 (the old script reused the RFE estimator).
  5. Output names follow the assignment: decision_tree_quaternion_fe.json (+ .c/.h).
  6. Extra outputs: accuracy/gap table, importance plot, selection by component/statistic,
     complexity comparison with Task 3, latency and window buffer size.
Example
  python model_quaternion_fe.py --curl Curl.csv --lateralraise LateralRaise.csv \
      --leftpunch LeftPunch.csv --output-dir task5_results --rawfe-summary task3_results/model_summary.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFE, f_classif
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree, _tree

CHANNELS = ["q0", "q1", "q2", "q3"]
CLASSES = ["Curl", "LateralRaise", "LeftPunch"]
STATS = ["mean", "var", "max", "min", "p2p", "energy"]               # order used by the C code
ALL_FEATURES = [f"{ch}__{s}" for ch in CHANNELS for s in STATS]       # 24 candidates
DYNAMIC_ONLY = [f"{ch}__{s}" for ch in CHANNELS for s in ("var", "p2p")]
MCU_CLOCK_HZ, CYCLES_PER_NODE = 84e6, 12


# ---------------------------------------------------------------- loading (original logic)
def read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    last = None
    for sep in [None, ",", ";", "\t"]:
        try:
            df = pd.read_csv(path, comment="#", skip_blank_lines=True, sep=sep, engine="python")
            df = df.dropna(axis=1, how="all")
            df.columns = [str(c).strip() for c in df.columns]
            if len(df.columns) >= 1:
                return df
        except Exception as e:
            last = e
    raise ValueError(f"Could not parse {path}: {last}")


def load_recording(path: Path, label: str) -> pd.DataFrame:
    df = read_csv(path)
    found, keep = set(), []
    for col in df.columns:
        base = re.sub(r"\.\d+$", "", col).strip()
        if base in CHANNELS and base not in found:      # the first copy of duplicated columns
            found.add(base)
            keep.append((col, base))
    missing = [c for c in CHANNELS if c not in found]
    if missing:
        raise ValueError(f"{path}: missing quaternion columns {missing}. Found headers: {list(df.columns)}")
    out = pd.DataFrame({base: pd.to_numeric(df[src], errors="coerce") for src, base in keep})
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=CHANNELS).reset_index(drop=True)
    # Discard all-zero vectors, which cannot represent a valid orientation.
    out = out.loc[(out[CHANNELS] ** 2).sum(axis=1) > 0].reset_index(drop=True)
    if len(out) < 50:
        raise ValueError(f"{path} has only {len(out)} valid quaternion rows.")
    out["label"], out["source_file"], out["source_row"] = label, path.name, np.arange(len(out))
    print(f"Loaded {len(out):,} samples: {path} -> {label}; quaternion columns = {CHANNELS}")
    return out


def split_recording(df, train_fraction, val_fraction):
    n = len(df)
    a, b = int(n * train_fraction), int(n * (train_fraction + val_fraction))
    if a < 2 or b <= a or b >= n:
        raise ValueError(f"Recording {df.source_file.iloc[0]} too short for split.")
    return {"train": df.iloc[:a].copy(), "validation": df.iloc[a:b].copy(), "test": df.iloc[b:].copy()}


# ---------------------------------------------------------------- windows + the six statistics
def extract_features(w: np.ndarray) -> dict[str, float]:
    """w: (n, 4) -> 24 features: per component mean, variance (divide by n), max, min,
    peak-to-peak, energy (mean of the squares)."""
    x = np.asarray(w, dtype=np.float64)
    mean, var, mx, mn, energy = x.mean(0), x.var(0), x.max(0), x.min(0), (x * x).mean(0)
    d = {}
    for i, ch in enumerate(CHANNELS):
        for s, v in zip(STATS, (mean[i], var[i], mx[i], mn[i], mx[i] - mn[i], energy[i])):
            d[f"{ch}__{s}"] = float(v)
    return d


def window_segment(df, win, stride):
    raw = df[CHANNELS].to_numpy(float)
    label, source = str(df.label.iloc[0]), str(df.source_file.iloc[0])
    rows = []
    for start in range(0, len(df) - win + 1, stride):
        r = extract_features(raw[start:start + win])
        r.update(label=label, source_file=source, window_start_row=int(df.source_row.iloc[start]),
                 window_end_row=int(df.source_row.iloc[start + win - 1]))
        rows.append(r)
    return pd.DataFrame(rows)


def build_windows(paths_by_class, args):
    recordings = [(lab, load_recording(Path(p), lab)) for lab, ps in paths_by_class for p in ps]
    split = {"train": [], "validation": [], "test": []}
    # Build windows inside each chronological partition so overlapping windows never cross a split boundary.
    for _, df in recordings:
        for k, part in split_recording(df, args.train_fraction, args.validation_fraction).items():
            wf = window_segment(part, args.window_size, args.stride)
            if not wf.empty:
                split[k].append(wf)
    out = {}
    for k, v in split.items():
        if not v:
            raise ValueError(f"No {k} windows.")
        out[k] = pd.concat(v, ignore_index=True)
    return out


# ---------------------------------------------------------------- feature selection
def anova_table(X, y):
    # Score each candidate independently with ANOVA. RFE determines which features are retained.
    F, p = f_classif(X, y)
    return pd.DataFrame({"feature": ALL_FEATURES, "anova_F": F, "p_value": p})


def rfe_rank_all(X, y, seed):
    # Remove one feature at a time to get a complete ranking from the random forest.
    sel = RFE(RandomForestClassifier(n_estimators=200, random_state=seed), n_features_to_select=1, step=1)
    sel.fit(X, y)
    return pd.Series(sel.ranking_, index=ALL_FEATURES)


def tree_diagnostic(X, y, seed):
    """Why RFE with a single decision tree is unreliable on this data."""
    dt = DecisionTreeClassifier(random_state=seed).fit(X, y)
    r = RFE(DecisionTreeClassifier(random_state=seed), n_features_to_select=1, step=1).fit(X, y)
    order = [ALL_FEATURES[i] for i in np.argsort(-r.ranking_)]
    return {"features_with_zero_importance": int((dt.feature_importances_ == 0).sum()),
            "first_eliminated": order[:6], "elimination_follows_column_order": bool(order[:6] == ALL_FEATURES[:6])}


# ---------------------------------------------------------------- export
def cident(s):
    s = re.sub(r"[^A-Za-z0-9_]", "_", str(s).upper())
    return ("CLASS_" if not s or s[0].isdigit() else "") + s


def cf(x):
    s = format(float(x), ".9g")
    return s + (".0" if "." not in s and "e" not in s.lower() else "") + "f"


def export_json(model, selected, idx, rank, anova, path, args):
    t, classes = model.tree_, [str(c) for c in model.classes_]
    nodes = []
    for i in range(t.node_count):
        fi = int(t.feature[i]); leaf = fi == _tree.TREE_UNDEFINED
        vals = [float(v) for v in t.value[i][0]]; pi = int(np.argmax(vals))
        nodes.append({"node_id": i, "feature_index": None if leaf else fi,
                      "feature_name": None if leaf else selected[fi],
                      "threshold": None if leaf else float(t.threshold[i]),
                      "left_child": None if leaf else int(t.children_left[i]),
                      "right_child": None if leaf else int(t.children_right[i]), "is_leaf": bool(leaf),
                      "predicted_class_index": pi, "predicted_class": classes[pi] if leaf else None,
                      "class_counts": {classes[j]: vals[j] for j in range(len(classes))},
                      "samples": int(t.n_node_samples[i]), "impurity": float(t.impurity[i])})
    payload = {"format": "quaternion_feature_decision_tree_v2", "channels": CHANNELS,
               "window_size_samples": args.window_size, "recommended_stride_samples": args.stride,
               "statistic_order_per_channel": STATS, "all_engineered_features": ALL_FEATURES,
               "selected_feature_indices_in_all_features": idx, "selected_features": selected,
               "feature_selection": {"method": "ANOVA F-statistics reported; RFE with a random-forest estimator",
                                     "n_candidates": len(ALL_FEATURES), "n_selected": len(selected),
                                     "rfe_rank": {k: int(v) for k, v in rank.items()},
                                     "anova_F": {r.feature: round(float(r.anova_F), 3) for r in anova.itertuples()}},
               "classes": classes, "tree_depth": int(model.get_depth()), "leaf_count": int(model.get_n_leaves()),
               "node_count": int(t.node_count), "criterion": args.criterion, "max_depth": args.max_depth,
               "min_samples_leaf": args.min_samples_leaf, "nodes": nodes,
               "note": "Quaternion order and convention must match the training CSV."}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def generate_c(json_path: Path, prefix: Path):
    p = json.loads(json_path.read_text(encoding="utf-8"))
    n, nodes, classes, sel = int(p["window_size_samples"]), p["nodes"], p["classes"], p["selected_feature_indices_in_all_features"]
    names = p["selected_features"]; allf = p["all_engineered_features"]
    prefix.parent.mkdir(parents=True, exist_ok=True)
    hp, cp = prefix.with_suffix(".h"), prefix.with_suffix(".c")
    guard = re.sub(r"\W", "_", prefix.name.upper()) + "_H"
    enums = ",\n".join(f"    QUAT_FEATURE_CLASS_{cident(c)} = {i}" for i, c in enumerate(classes)) + ",\n    QUAT_FEATURE_CLASS_UNKNOWN = 255"
    comments = "\n".join(f" * {i}: {nm}" for i, nm in enumerate(names))
    hp.write_text(f"""/* Auto-generated. Window={n}; input order q0,q1,q2,q3. */
#ifndef {guard}
#define {guard}
#include <stdint.h>
#define QUAT_TREE_WINDOW_SIZE {n}u
#define QUAT_TREE_CHANNELS 4u
#define QUAT_TREE_FEATURE_COUNT {len(names)}u
#define QUAT_TREE_NODE_COUNT {len(nodes)}u
typedef enum {{
{enums}
}} quat_feature_tree_class_t;
/* samples[window_index][q0..q3]; quaternion convention must match training.
 * Selected features, in tree order:
{comments}
 */
quat_feature_tree_class_t quat_feature_tree_predict_window(const float samples[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS]);
#endif
""", encoding="utf-8")
    rows = []
    for nd in nodes:
        if nd["is_leaf"]:
            rows.append(f"    {{-1, 0.0f, -1, -1, {int(nd['predicted_class_index'])}u}},")
        else:
            rows.append(f"    {{{int(nd['feature_index'])}, {cf(nd['threshold'])}, {int(nd['left_child'])}, {int(nd['right_child'])}, {int(nd['predicted_class_index'])}u}},")
    sel_lines = "\n".join(f"    sel[{k}u] = f[{int(ix)}u]; /* {names[k]} */" for k, ix in enumerate(sel))
    cp.write_text(f"""/* Auto-generated from {json_path.name}; do not edit. */
#include "{hp.name}"
#include <stddef.h>
typedef struct {{ int16_t feature; float threshold; int32_t left; int32_t right; uint8_t cls; }} quat_node_t;
static const quat_node_t nodes[{len(nodes)}] = {{
{chr(10).join(rows)}
}};
/* 6 statistics per component, in the order of the Python code: mean, var, max, min, p2p, energy */
static void features(const float x[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS], float out[{len(allf)}]) {{
    uint32_t a, i;
    for (a = 0u; a < QUAT_TREE_CHANNELS; ++a) {{
        float sum = 0.0f, sq = 0.0f, mean, var = 0.0f, mn = x[0][a], mx = x[0][a];
        uint32_t b = a * {len(STATS)}u;
        for (i = 0u; i < QUAT_TREE_WINDOW_SIZE; ++i) {{
            float v = x[i][a];
            sum += v; sq += v * v;
            if (v < mn) mn = v;
            if (v > mx) mx = v;
        }}
        mean = sum / (float)QUAT_TREE_WINDOW_SIZE;
        for (i = 0u; i < QUAT_TREE_WINDOW_SIZE; ++i) {{ float d = x[i][a] - mean; var += d * d; }}
        out[b + 0u] = mean;
        out[b + 1u] = var / (float)QUAT_TREE_WINDOW_SIZE;
        out[b + 2u] = mx;
        out[b + 3u] = mn;
        out[b + 4u] = mx - mn;
        out[b + 5u] = sq / (float)QUAT_TREE_WINDOW_SIZE;
    }}
}}
quat_feature_tree_class_t quat_feature_tree_predict_window(const float samples[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS]) {{
    float f[{len(allf)}], sel[{len(names)}];
    int32_t ni = 0;
    uint32_t step;
    if (samples == NULL) return QUAT_FEATURE_CLASS_UNKNOWN;
    features(samples, f);
{sel_lines}
    for (step = 0u; step < QUAT_TREE_NODE_COUNT; ++step) {{
        const quat_node_t *n;
        if (ni < 0 || (uint32_t)ni >= QUAT_TREE_NODE_COUNT) return QUAT_FEATURE_CLASS_UNKNOWN;
        n = &nodes[ni];
        if (n->feature < 0) return (quat_feature_tree_class_t)n->cls;
        if ((uint32_t)n->feature >= QUAT_TREE_FEATURE_COUNT) return QUAT_FEATURE_CLASS_UNKNOWN;
        ni = (sel[n->feature] <= n->threshold) ? n->left : n->right;
    }}
    return QUAT_FEATURE_CLASS_UNKNOWN;
}}
""", encoding="utf-8")
    return cp, hp


# ---------------------------------------------------------------- main
def fit_tree(args, X, y):
    return DecisionTreeClassifier(criterion=args.criterion, max_depth=args.max_depth,
                                  min_samples_leaf=args.min_samples_leaf,
                                  min_samples_split=args.min_samples_split, random_state=args.random_state).fit(X, y)


def main():
    ap = argparse.ArgumentParser(description="Task 5: quaternion window features + ANOVA/RFE selection -> tree -> JSON, C")
    ap.add_argument("--curl", nargs="+", required=True)
    ap.add_argument("--lateralraise", nargs="+", required=True)
    ap.add_argument("--leftpunch", nargs="+", required=True)
    ap.add_argument("--output-dir", default="task5_results")
    ap.add_argument("--rawfe-summary", default=None, help="Task 3 model_summary.json for the comparison table")
    ap.add_argument("--window-size", type=int, default=42)
    ap.add_argument("--stride", type=int, default=21)
    ap.add_argument("--n-features", type=int, default=8, help="features kept by RFE (of 24)")
    ap.add_argument("--train-fraction", type=float, default=0.70)
    ap.add_argument("--validation-fraction", type=float, default=0.15)
    # same defaults as model_raw.py / model_raw_fe.py
    ap.add_argument("--max-depth", type=int, default=None)
    ap.add_argument("--min-samples-leaf", type=int, default=1)
    ap.add_argument("--min-samples-split", type=int, default=2)
    ap.add_argument("--criterion", choices=["gini", "entropy", "log_loss"], default="gini")
    ap.add_argument("--random-state", type=int, default=42)
    ap.add_argument("--plot-depth", type=int, default=3)
    args = ap.parse_args()
    try:
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        W = build_windows([("Curl", args.curl), ("LateralRaise", args.lateralraise), ("LeftPunch", args.leftpunch)], args)
        tr, va, te = W["train"], W["validation"], W["test"]
        for k, d in W.items():
            print(f"{k.title():10}: {len(d):,} windows; classes={d.label.value_counts().to_dict()}")
        Xtr, ytr = tr[ALL_FEATURES].to_numpy(float), tr.label.astype(str).to_numpy()

        # ---- feature selection (training windows only)
        anova = anova_table(Xtr, ytr)
        rank = rfe_rank_all(Xtr, ytr, args.random_state)
        selected = list(rank.sort_values().index[:args.n_features])
        # Save the original feature indices so the C extractor can reproduce the selected input order.
        sel_idx = [ALL_FEATURES.index(f) for f in selected]
        diag = tree_diagnostic(Xtr, ytr, args.random_state)
        table = pd.DataFrame({"feature": ALL_FEATURES}).merge(anova, on="feature")
        table["rfe_rank"] = table.feature.map(rank)
        table["selected"] = table.feature.isin(selected)
        table.sort_values("rfe_rank").to_csv(out / "rfe_feature_ranking.csv", index=False)
        anova.sort_values("anova_F", ascending=False).to_csv(out / "anova_f_statistics.csv", index=False)

        # ---- model on the selected features (same hyperparameters as Tasks 2-3)
        model = fit_tree(args, tr[selected].to_numpy(float), ytr)
        names = [str(c) for c in model.classes_]
        accs, reports, preds = {}, [], []
        for k, d in W.items():
            X, y = d[selected].to_numpy(float), d.label.astype(str).to_numpy()
            p = model.predict(X); accs[k] = float(accuracy_score(y, p))
            rep = classification_report(y, p, labels=names, output_dict=True, zero_division=0)
            print(f"\n{k.upper()} accuracy={accs[k]:.4f}\n" + classification_report(y, p, labels=names, zero_division=0))
            for c in names + ["macro avg", "weighted avg"]:
                r = rep[c]
                reports.append({"split": k, "class": c, "precision": r["precision"], "recall": r["recall"],
                                "f1_score": r["f1-score"], "support": r["support"], "accuracy_overall": accs[k]})
            z = d[["label", "source_file", "window_start_row", "window_end_row"]].copy()
            z["predicted_label"], z["correct"], z["split"] = p, d.label.astype(str).to_numpy() == p, k
            preds.append(z)
        pd.DataFrame(reports).to_csv(out / "metrics_by_class.csv", index=False)
        allp = pd.concat(preds, ignore_index=True); allp.to_csv(out / "predictions_all_splits.csv", index=False)
        allp[(allp.split == "test") & (~allp.correct)].to_csv(out / "test_misclassifications.csv", index=False)

        yp = model.predict(te[selected].to_numpy(float))
        cm = confusion_matrix(te.label.astype(str), yp, labels=CLASSES)
        pd.DataFrame(cm, index=[f"Actual {c}" for c in CLASSES], columns=[f"Predicted {c}" for c in CLASSES]).to_csv(out / "confusion_matrix_test.csv")
        fig, ax = plt.subplots(1, 2, figsize=(12, 5))
        ConfusionMatrixDisplay(cm, display_labels=CLASSES).plot(ax=ax[0], cmap="Blues", values_format="d", colorbar=False)
        ax[0].set_title("QUAT+FE - test confusion matrix (counts)")
        ConfusionMatrixDisplay(cm / cm.sum(axis=1, keepdims=True).clip(min=1), display_labels=CLASSES).plot(
            ax=ax[1], cmap="Blues", values_format=".3f", colorbar=False)
        ax[1].set_title("QUAT+FE - row-normalised")
        fig.tight_layout(); fig.savefig(out / "confusion_matrix_test.png", dpi=160); plt.close(fig)

        # ---- selection figures and importance
        top = anova.sort_values("anova_F", ascending=True)
        fig, ax = plt.subplots(figsize=(8, 7))
        ax.barh(top.feature, np.log10(top.anova_F.clip(lower=1e-3)), color=["#2a9d8f" if f in selected else "#bbbbbb" for f in top.feature])
        ax.set_xlabel("log10 of the ANOVA F-statistic"); ax.set_title("ANOVA F-statistic of the 24 quaternion features\n(green = kept by RFE)")
        ax.grid(axis="x", alpha=.3); fig.tight_layout(); fig.savefig(out / "anova_f_statistics.png", dpi=160); plt.close(fig)
        imp = pd.Series(model.feature_importances_, index=selected).sort_values(ascending=False)
        imp.rename("importance").to_csv(out / "feature_importance.csv")
        shown = imp[imp > 0] if (imp > 0).any() else imp
        fig, ax = plt.subplots(figsize=(7, 3.8)); b = ax.barh(shown.index[::-1], shown.values[::-1], color="steelblue")
        ax.bar_label(b, fmt="%.3f"); ax.set_xlabel("Gini importance"); ax.set_title("QUAT+FE - features used by the tree")
        ax.grid(axis="x", alpha=.3); fig.tight_layout(); fig.savefig(out / "feature_importance.png", dpi=160); plt.close(fig)
        sel_comp = {c: sum(f.startswith(c + "__") for f in selected) for c in CHANNELS}
        sel_stat = {s: sum(f.endswith("__" + s) for f in selected) for s in STATS}
        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        for a, d, t in [(ax[0], sel_comp, "selected features per component"), (ax[1], sel_stat, "selected features per statistic")]:
            bb = a.bar(list(d), list(d.values()), color="#2a9d8f"); a.bar_label(bb); a.set_title(t); a.grid(axis="y", alpha=.3)
        fig.tight_layout(); fig.savefig(out / "selection_by_group.png", dpi=160); plt.close(fig)
        fig, ax = plt.subplots(figsize=(12, 5))
        plot_tree(model, feature_names=selected, class_names=names, filled=True, rounded=True, max_depth=args.plot_depth,
                  fontsize=8, ax=ax, impurity=False)
        fig.tight_layout(); fig.savefig(out / "tree_structure.png", dpi=160); plt.close(fig)
        (out / "decision_tree_features_rfe.txt").write_text(export_text(model, feature_names=selected, decimals=6), encoding="utf-8")

        # ---- JSON, C
        jp = out / "decision_tree_quaternion_fe.json"
        payload = export_json(model, selected, sel_idx, rank, anova, jp, args)
        cpath, hpath = generate_c(jp, out / "decision_tree_quaternion_fe")

        # ---- latency / sizes
        nodes = {n["node_id"]: n for n in payload["nodes"]}
        # Time traversal of the exported tree separately from window feature extraction and scikit-learn calls.
        X = te[selected].to_numpy(float); reps = max(1, 5000 // len(X)); t0 = time.perf_counter()
        for _ in range(reps):
            for x in X:
                n = nodes[0]
                while not n["is_leaf"]:
                    n = nodes[n["left_child"]] if x[n["feature_index"]] <= n["threshold"] else nodes[n["right_child"]]
        walk_us = (time.perf_counter() - t0) / (reps * len(X)) * 1e6
        t0 = time.perf_counter()
        for _ in range(300): model.predict(X[:1])
        single_us = (time.perf_counter() - t0) / 300 * 1e6
        win0 = np.zeros((args.window_size, 4)); win0[:] = 0.5; t0 = time.perf_counter()
        for _ in range(300): extract_features(win0)
        feat_us = (time.perf_counter() - t0) / 300 * 1e6
        buf = args.window_size * len(CHANNELS) * 4
        gap = accs["train"] - accs["test"]
        summary = {
            "task": "Task 5 - QUAT+FE", "channels": CHANNELS, "classes": names, "statistics": STATS,
            "candidate_features": len(ALL_FEATURES), "selected_feature_count": len(selected), "selected_features": selected,
            "window_size_samples": args.window_size, "stride_samples": args.stride,
            "overlap_percent": round(100 * (1 - args.stride / args.window_size), 1), "split_mode": "chronological",
            "train_windows": len(tr), "validation_windows": len(va), "test_windows": len(te),
            "criterion": args.criterion, "max_depth_setting": args.max_depth, "min_samples_leaf": args.min_samples_leaf,
            "min_samples_split": args.min_samples_split, "random_state": args.random_state,
            "train_accuracy": accs["train"], "validation_accuracy": accs["validation"], "test_accuracy": accs["test"],
            "generalization_gap_train_minus_test": gap,
            "tree_depth": int(model.get_depth()), "leaf_count": int(model.get_n_leaves()), "node_count": int(model.tree_.node_count),
            "json_size_kb": round(jp.stat().st_size / 1024, 3), "c_source_and_header_combined_bytes": int(cpath.stat().st_size + hpath.stat().st_size),
            "embedded_tree_size_bytes_est": int(model.tree_.node_count * 9), "window_buffer_bytes": buf,
            "features_used_by_tree": [f for f in selected if imp[f] > 0],
            "importance": {k: float(v) for k, v in imp.items()},
            "importance_by_component": {c: float(sum(v for f, v in imp.items() if f.startswith(c + "__"))) for c in CHANNELS},
            "importance_by_statistic": {s: float(sum(v for f, v in imp.items() if f.endswith("__" + s))) for s in STATS},
            "selected_per_component": sel_comp, "selected_per_statistic": sel_stat, "tree_diagnostic": diag,
            "json_walk_us": float(walk_us), "sklearn_single_call_us": float(single_us),
            "feature_extraction_host_us_per_window": float(feat_us),
            "mcu_tree_worst_case_us_est": float(model.get_depth() * CYCLES_PER_NODE / MCU_CLOCK_HZ * 1e6),
            "latency_note": "Host timings show relative cost only; MCU figure is an estimate (12 cycles per level, 84 MHz)."}
        (out / "model_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        pd.DataFrame([{"train_accuracy": accs["train"], "validation_accuracy": accs["validation"], "test_accuracy": accs["test"],
                       "generalization_gap_train_minus_test": gap, "tree_depth": summary["tree_depth"],
                       "leaf_count": summary["leaf_count"], "node_count": summary["node_count"]}]).to_csv(out / "accuracy_and_complexity_summary.csv", index=False)

        if args.rawfe_summary and Path(args.rawfe_summary).is_file():
            r = json.loads(Path(args.rawfe_summary).read_text())
            rows = [("Candidate -> selected features", f"{r['feature_count']} -> {r['feature_count']}", f"{len(ALL_FEATURES)} -> {len(selected)}"),
                    ("Tree depth", r["tree_depth"], summary["tree_depth"]), ("Leaves", r["leaf_count"], summary["leaf_count"]),
                    ("Nodes", r["node_count"], summary["node_count"]), ("JSON size [KB]", r["json_size_kb"], summary["json_size_kb"]),
                    ("Estimated size in C [bytes]", r["embedded_tree_size_bytes_est"], summary["embedded_tree_size_bytes_est"]),
                    ("Test accuracy [%]", round(100 * r["test_accuracy"], 2), round(100 * accs["test"], 2)),
                    ("Window buffer [bytes]", r["window_buffer_bytes"], buf),
                    ("Channels buffered", 6, 4)]
            pd.DataFrame(rows, columns=["metric", "RAW+FE (Task 3)", "QUAT+FE (Task 5)"]).to_csv(out / "complexity_comparison.csv", index=False)

        print(f"\nSelected {len(selected)}/{len(ALL_FEATURES)} features: {selected}")
        print(f"Features used by the tree: {summary['features_used_by_tree']}")
        print(f"Tree depth={model.get_depth()}, leaves={model.get_n_leaves()}, nodes={model.tree_.node_count}; JSON {summary['json_size_kb']} KB; buffer {buf} B")
        print(f"Accuracy train/val/test = {accs['train']:.4f}/{accs['validation']:.4f}/{accs['test']:.4f}")
        print(f"Outputs: {out.resolve()}\nJSON: {jp}\nC: {cpath}\nHeader: {hpath}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
