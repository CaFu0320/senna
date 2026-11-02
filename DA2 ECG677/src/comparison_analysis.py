#!/usr/bin/env python3
"""comparison_analysis.py - Task 6: comparison and insights for the four decision trees.

Models compared (all trained on the same recordings, with the same chronological 70/15/15 split and
the same default hyperparameters):
    RAW      (Task 2, model_raw.py)            6 raw IMU values per sample
    RAW+FE   (Task 3, model_raw_fe.py)         36 window statistics of the 6 IMU axes
    QUAT     (Task 4, model_quaternion.py)     4 quaternion components per sample
    QUAT+FE  (Task 5, model_quaternion_fe.py)  8 of 24 window statistics of the quaternion (ANOVA + RFE)

What it does
  1. Reads the result folders of the four tasks (model_summary.json, confusion_matrix_test.csv,
     metrics_by_class.csv) and writes the performance and cost table (model_comparison.csv).
  2. Per-class test F1 and recall (per_class_metrics.csv, per_class_f1.png).
  3. Robustness to unseen time blocks for ALL FOUR models with one protocol: every recording is cut into
     5 consecutive blocks and each block is held out in turn (robustness_all_models.csv / .png).
     QUAT+FE repeats its feature selection (RFE) inside every fold, on the training blocks only.
  4. Accuracy against memory (tree table + window buffer) and confusion matrices side by side
     (tradeoff.png, confusion_comparison.png, accuracy_all_models.png).
  5. comparison_summary.json with every number used in the report.

Usage (from src/):
  python comparison_analysis.py --task2 ../docs/task2 --task3 ../docs/task3 --task4 ../docs/task4 \
      --task5 ../docs/task5 --horizontal ../data/raw/Horizontal.csv --static ../data/raw/Static.csv \
      --vertical ../data/raw/Vertical.csv --out ../docs/comparison
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

import model_raw_fe as imu          # loader + window statistics for the six IMU axes
import model_quaternion_fe as qf     # loader + window statistics + ANOVA/RFE for the quaternion

MODELS = ["RAW", "RAW+FE", "QUAT", "QUAT+FE"]
CLASSES = ["Horizontal", "Static", "Vertical"]
K_BLOCKS, WINDOW, STRIDE, K_SELECT = 5, 42, 21, 8


def dt():
    return DecisionTreeClassifier(random_state=42)       # the defaults used in every task


# ------------------------------------------------------------------ 1-2. tables from the task results
def load_results(dirs):
    S = {m: json.loads((Path(d) / "model_summary.json").read_text()) for m, d in dirs.items()}
    CM = {m: pd.read_csv(Path(d) / "confusion_matrix_test.csv", index_col=0) for m, d in dirs.items()}
    MC = {m: pd.read_csv(Path(d) / "metrics_by_class.csv") for m, d in dirs.items()}
    return S, CM, MC


def features_used(folder):
    """Number of inputs the tree actually uses (importance > 0), from the task's feature_importance.csv."""
    t = pd.read_csv(Path(folder) / "feature_importance.csv")
    return int((t["importance"] > 0).sum())


def performance_table(S, CM, MC, dirs):
    rows = []
    for m in MODELS:
        s, cm = S[m], CM[m].to_numpy()
        test = MC[m][(MC[m].split == "test") & (MC[m]["class"].isin(CLASSES))]
        window = m.endswith("FE")
        buf = s.get("window_buffer_bytes", 0)
        nodes = s["node_count"]
        rows.append({
            "model": m, "input": "42-sample window" if window else "1 sample",
            "features_used_by_tree": features_used(dirs[m]),
            "test_items": s.get("test_samples", s.get("test_windows")),
            "acc_train": s["train_accuracy"], "acc_val": s["validation_accuracy"], "acc_test": s["test_accuracy"],
            "gap_points": 100 * s["generalization_gap_train_minus_test"],
            "test_macro_f1": float(test.f1_score.mean()), "test_errors": int(cm.sum() - np.trace(cm)),
            "depth": s["tree_depth"], "leaves": s["leaf_count"], "nodes": nodes, "json_kb": s["json_size_kb"],
            "tree_bytes_est": nodes * 9, "window_buffer_bytes": buf, "memory_bytes_est": nodes * 9 + buf,
            "mcu_tree_us_est": s.get("mcu_tree_worst_case_us_est", s["tree_depth"] * 12 / 84e6 * 1e6),
            "decision_every_samples": STRIDE if window else 1, "first_decision_after_samples": WINDOW if window else 1,
        })
    return pd.DataFrame(rows)


def per_class_table(MC, out):
    rows = []
    for m in MODELS:
        d = MC[m][(MC[m].split == "test") & (MC[m]["class"].isin(CLASSES))].set_index("class")
        for c in CLASSES:
            rows.append({"model": m, "class": c, "precision": d.loc[c, "precision"], "recall": d.loc[c, "recall"],
                         "f1": d.loc[c, "f1_score"], "support": int(d.loc[c, "support"])})
    t = pd.DataFrame(rows)
    t.to_csv(out / "per_class_metrics.csv", index=False)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for a, col, title in [(ax[0], "f1", "Test F1-score per class"), (ax[1], "recall", "Test recall per class")]:
        M = t.pivot(index="model", columns="class", values=col).loc[MODELS, CLASSES]
        a.imshow(M.values, cmap="RdYlGn", vmin=0, vmax=1)
        for i in range(len(MODELS)):
            for j in range(len(CLASSES)):
                a.text(j, i, f"{M.values[i, j]:.2f}", ha="center", va="center", fontsize=11)
        a.set_xticks(range(3), CLASSES); a.set_yticks(range(4), MODELS); a.set_title(title)
    fig.tight_layout(); fig.savefig(out / "per_class_f1.png", dpi=150); plt.close(fig)
    return t


# ------------------------------------------------------------------ 3. robustness of all four models
def load_recordings(paths):
    imu_rec = [(lab, imu.load_recording(Path(p), lab, None)) for lab, p in paths]
    q_rec = [(lab, qf.load_recording(Path(p), lab)) for lab, p in paths]
    return imu_rec, q_rec


def block_slice(df, j):
    n = len(df)
    return df.iloc[j * n // K_BLOCKS:(j + 1) * n // K_BLOCKS].copy()


def leave_one_block_out(imu_rec, q_rec):
    res = {m: [] for m in MODELS}
    for j in range(K_BLOCKS):
        # ----- samples (RAW and QUAT)
        for m, rec, cols in [("RAW", imu_rec, imu.RAW_CHANNELS), ("QUAT", q_rec, qf.CHANNELS)]:
            tr = pd.concat([block_slice(d, k) for _, d in rec for k in range(K_BLOCKS) if k != j])
            te = pd.concat([block_slice(d, j) for _, d in rec])
            p = dt().fit(tr[cols], tr["label"]).predict(te[cols])
            res[m].append(float(accuracy_score(te["label"], p)))
        # ----- windows (RAW+FE and QUAT+FE)
        wi_tr = pd.concat([imu.windows_from_segment(block_slice(d, k), WINDOW, STRIDE) for _, d in imu_rec for k in range(K_BLOCKS) if k != j], ignore_index=True)
        wi_te = pd.concat([imu.windows_from_segment(block_slice(d, j), WINDOW, STRIDE) for _, d in imu_rec], ignore_index=True)
        p = dt().fit(wi_tr[imu.ALL_FEATURE_NAMES], wi_tr["label"]).predict(wi_te[imu.ALL_FEATURE_NAMES])
        res["RAW+FE"].append(float(accuracy_score(wi_te["label"], p)))
        wq_tr = pd.concat([qf.window_segment(block_slice(d, k), WINDOW, STRIDE) for _, d in q_rec for k in range(K_BLOCKS) if k != j], ignore_index=True)
        wq_te = pd.concat([qf.window_segment(block_slice(d, j), WINDOW, STRIDE) for _, d in q_rec], ignore_index=True)
        rank = qf.rfe_rank_all(wq_tr[qf.ALL_FEATURES].to_numpy(float), wq_tr["label"].astype(str).to_numpy(), 42)
        sel = list(rank.sort_values().index[:K_SELECT])         # selection on the training blocks only
        p = dt().fit(wq_tr[sel], wq_tr["label"]).predict(wq_te[sel])
        res["QUAT+FE"].append(float(accuracy_score(wq_te["label"], p)))
    return res


def robustness_outputs(res, out):
    rows = [{"model": m, **{f"block_{j + 1}": round(a, 4) for j, a in enumerate(v)},
             "mean": round(float(np.mean(v)), 4), "worst": round(float(np.min(v)), 4)} for m, v in res.items()]
    pd.DataFrame(rows).to_csv(out / "robustness_all_models.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 4.4))
    w = 0.8 / K_BLOCKS
    for j in range(K_BLOCKS):
        vals = [res[m][j] * 100 for m in MODELS]
        b = ax.bar(np.arange(len(MODELS)) + j * w - 0.4 + w / 2, vals, w, label=f"block {j + 1} held out")
    ax.set_xticks(range(len(MODELS)), MODELS); ax.set_ylim(40, 101); ax.set_ylabel("Accuracy on the held-out block [%]")
    ax.set_title("Leave-one-time-block-out accuracy of the four models")
    ax.legend(fontsize=8, ncol=5, loc="lower center"); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(out / "robustness_all_models.png", dpi=150); plt.close(fig)
    return rows


# ------------------------------------------------------------------ 4. trade-off and side-by-side figures
def tradeoff_figure(perf, rob, out):
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.4))
    mem = perf.set_index("model")["memory_bytes_est"]
    for a, (title, y) in zip(ax, [("Test accuracy (chronological split)", perf.set_index("model")["acc_test"] * 100),
                                  ("Mean accuracy, leave-one-block-out", pd.Series({r["model"]: 100 * r["mean"] for r in rob}))]):
        for m, col in zip(MODELS, ["#4c72b0", "#55a868", "#c44e52", "#8172b2"]):
            a.scatter(mem[m], y[m], s=140, color=col, label=m, zorder=3)
            off = {"RAW": (-36, -16), "RAW+FE": (8, 8), "QUAT": (8, 6), "QUAT+FE": (8, -14)}[m]
            a.annotate(m, (mem[m], y[m]), textcoords="offset points", xytext=off, fontsize=9)
        a.set_xscale("log"); a.set_xlabel("Estimated memory: tree table + window buffer [bytes, log scale]")
        a.set_ylabel("Accuracy [%]"); a.set_title(title); a.grid(alpha=0.3); a.set_ylim(60, 103)
    fig.tight_layout(); fig.savefig(out / "tradeoff.png", dpi=150); plt.close(fig)


def side_by_side(perf, CM, out):
    fig, ax = plt.subplots(1, 4, figsize=(17, 4.4))
    for a, m in zip(ax, MODELS):
        cm = CM[m].to_numpy(); norm = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
        a.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        for i in range(3):
            for j in range(3):
                a.text(j, i, f"{cm[i, j]}", ha="center", va="center", color="white" if norm[i, j] > .5 else "black", fontsize=12)
        a.set_xticks(range(3), CLASSES, rotation=30); a.set_yticks(range(3), CLASSES)
        a.set_title(f"{m}\n{cm.sum()} test items, {int(cm.sum() - np.trace(cm))} error(s)"); a.set_xlabel("Predicted")
    ax[0].set_ylabel("True"); fig.suptitle("Test confusion matrices (counts; colour = row-normalised)", y=1.02)
    fig.tight_layout(); fig.savefig(out / "confusion_comparison.png", dpi=150, bbox_inches="tight"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8.5, 4.4)); x = np.arange(4); w = .26
    for i, (k, c) in enumerate([("acc_train", "#4c72b0"), ("acc_val", "#dd8452"), ("acc_test", "#55a868")]):
        b = ax.bar(x + (i - 1) * w, perf[k] * 100, w, label=k.replace("acc_", ""), color=c); ax.bar_label(b, fmt="%.1f", fontsize=7)
    ax.set_xticks(x, MODELS); ax.set_ylim(60, 101); ax.set_ylabel("Accuracy [%]"); ax.legend(loc="lower left"); ax.grid(axis="y", alpha=.3)
    ax.set_title("Train / validation / test accuracy of the four models")
    fig.tight_layout(); fig.savefig(out / "accuracy_all_models.png", dpi=150); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for t in ("task2", "task3", "task4", "task5"):
        ap.add_argument(f"--{t}", default=f"../docs/{t}")
    ap.add_argument("--horizontal", default="../data/raw/Horizontal.csv")
    ap.add_argument("--static", default="../data/raw/Static.csv")
    ap.add_argument("--vertical", default="../data/raw/Vertical.csv")
    ap.add_argument("--out", default="../docs/comparison")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    dirs = dict(zip(MODELS, [a.task2, a.task3, a.task4, a.task5]))
    S, CM, MC = load_results(dirs)
    perf = performance_table(S, CM, MC, dirs); perf.to_csv(out / "model_comparison.csv", index=False)
    pc = per_class_table(MC, out)
    imu_rec, q_rec = load_recordings([("Horizontal", a.horizontal), ("Static", a.static), ("Vertical", a.vertical)])
    rob = robustness_outputs(leave_one_block_out(imu_rec, q_rec), out)
    tradeoff_figure(perf, rob, out); side_by_side(perf, CM, out)
    (out / "comparison_summary.json").write_text(json.dumps({"performance": perf.to_dict(orient="records"),
        "robustness": rob, "per_class": pc.to_dict(orient="records")}, indent=2, default=float))

    pd.set_option("display.width", 220)
    print(perf.round(4).to_string(index=False))
    print("\nPer-class test recall:\n", pc.pivot(index="model", columns="class", values="recall").loc[MODELS, CLASSES].round(3))
    print("\nLeave-one-block-out accuracy:\n", pd.DataFrame(rob).to_string(index=False))
    print("\noutputs ->", out)


if __name__ == "__main__":
    main()
