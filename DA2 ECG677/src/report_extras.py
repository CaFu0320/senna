#!/usr/bin/env python3
"""report_extras.py - small figures and numbers for the Task 2 and Task 3 reports.

Reads the output folders of model_raw.py (Task 2) and model_raw_fe.py
(Task 3) and writes to --out:
  task2_accuracy.png          train / validation / test accuracy of the RAW tree
  task2_depth_profile.csv/png nodes and leaves at each depth of the RAW tree (from the JSON)
  task2_latency.json          time to walk the RAW tree on the host + MCU cycle estimate
  accuracy_raw_vs_rawfe.png   train / validation / test accuracy of both models
Usage:  python report_extras.py --task2 task2_results --task3 task3_results --out extras
"""
import argparse
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MCU_CLOCK_HZ, CYCLES_PER_NODE = 84e6, 12
RAW = ["ACC_X", "ACC_Y", "ACC_Z", "GYR_X", "GYR_Y", "GYR_Z"]

ap = argparse.ArgumentParser()
ap.add_argument("--task2", default="task2_results")
ap.add_argument("--task3", default="task3_results")
ap.add_argument("--out", default="extras")
a = ap.parse_args()
t2, t3, out = Path(a.task2), Path(a.task3), Path(a.out)
out.mkdir(parents=True, exist_ok=True)

s2 = json.loads((t2 / "model_summary.json").read_text())
s3 = json.loads((t3 / "model_summary.json").read_text())
tj = json.loads((t2 / "decision_tree_raw.json").read_text())
nodes = {n["node_id"]: n for n in tj["nodes"]}

# ---- accuracy bars ----
def bars(ax, vals, labels, title):
    b = ax.bar(labels, [v * 100 for v in vals], color=["#4c72b0", "#dd8452", "#55a868"])
    ax.bar_label(b, fmt="%.2f%%")
    ax.set_ylim(max(0, min(vals) * 100 - 6), 100.8)
    ax.set_ylabel("Accuracy [%]")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)

fig, ax = plt.subplots(figsize=(5.5, 4))
bars(ax, [s2["train_accuracy"], s2["validation_accuracy"], s2["test_accuracy"]],
     ["train", "validation", "test"], "RAW tree - accuracy per set")
fig.tight_layout(); fig.savefig(out / "task2_accuracy.png", dpi=160); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 4.2))
x = np.arange(3)
for i, (name, s) in enumerate([("RAW (Task 2, samples)", s2), ("RAW+FE (Task 3, windows)", s3)]):
    v = [s["train_accuracy"] * 100, s["validation_accuracy"] * 100, s["test_accuracy"] * 100]
    b = ax.bar(x + (i - 0.5) * 0.38, v, 0.38, label=name)
    ax.bar_label(b, fmt="%.2f", fontsize=8)
ax.set_xticks(x, ["train", "validation", "test"])
ax.set_ylim(97, 100.6)
ax.set_ylabel("Accuracy [%]")
ax.set_title("Accuracy of the RAW and RAW+FE trees")
ax.legend(loc="lower right")
ax.grid(axis="y", alpha=0.3)
fig.tight_layout(); fig.savefig(out / "accuracy_raw_vs_rawfe.png", dpi=160); plt.close(fig)

# ---- depth profile of the RAW tree (from the JSON) ----
depth = {0: 0}
for i in sorted(nodes):
    n = nodes[i]
    if not n["is_leaf"]:
        depth[n["left_child"]] = depth[i] + 1
        depth[n["right_child"]] = depth[i] + 1
prof = pd.DataFrame([{"depth": d, "nodes": sum(1 for v in depth.values() if v == d),
                      "leaves": sum(1 for i, v in depth.items() if v == d and nodes[i]["is_leaf"])}
                     for d in range(max(depth.values()) + 1)])
prof.to_csv(out / "task2_depth_profile.csv", index=False)
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.bar(prof["depth"] - 0.2, prof["nodes"], 0.4, label="nodes")
ax.bar(prof["depth"] + 0.2, prof["leaves"], 0.4, label="leaves")
ax.set_xlabel("Depth"); ax.set_ylabel("Count"); ax.set_title("RAW tree depth profile")
ax.legend(); ax.grid(axis="y", alpha=0.3)
fig.tight_layout(); fig.savefig(out / "task2_depth_profile.png", dpi=160); plt.close(fig)

# ---- tree-walk latency of the RAW tree (host) and MCU estimate ----
pred = pd.read_csv(t2 / "predictions_all_splits.csv")
X = pred[pred["split"] == "test"][RAW].to_numpy(dtype=float)
col = {n: i for i, n in enumerate(RAW)}
reps = max(1, 5000 // len(X))
t0 = time.perf_counter()
for _ in range(reps):
    for x in X:
        n = nodes[0]
        while not n["is_leaf"]:
            n = nodes[n["left_child"]] if x[n["feature_index"]] <= n["threshold"] else nodes[n["right_child"]]
walk_us = (time.perf_counter() - t0) / (reps * len(X)) * 1e6
lat = {"json_walk_us_host": round(walk_us, 3),
       "mcu_worst_case_us_est": round(tj["tree_depth"] * CYCLES_PER_NODE / MCU_CLOCK_HZ * 1e6, 3),
       "mcu_cycles_est": tj["tree_depth"] * CYCLES_PER_NODE,
       "embedded_tree_bytes_est": tj["node_count"] * 9,
       "note": "Host timing shows relative cost only. MCU figure = depth x 12 cycles at 84 MHz (estimate)."}
(out / "task2_latency.json").write_text(json.dumps(lat, indent=2))
print(json.dumps(lat, indent=2))
print("wrote", sorted(p.name for p in out.iterdir()))
