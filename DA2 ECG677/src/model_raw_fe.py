#!/usr/bin/env python3
"""Task 3 - RAW+FE: feature-engineered IMU decision tree (windowed statistics).

This is the corrected version of imu_feature_rfe_pipeline.py. What changed, and why
  1. Features are the six statistics the assignment lists - mean, variance, maximum,
     minimum, peak-to-peak and energy - for each of the six IMU axes: 6 x 6 = 36 features.
     (The old script used 11 statistics = 66 features.)
  2. No Recursive Feature Elimination. Task 3 trains on all engineered features; feature
     selection belongs to Task 5. (RFE with a single decision tree also degenerated: it
     kept the last columns in column order, not the useful ones.)
  3. Output names follow the assignment: decision_tree_raw_fe.json (+ .c / .h).
  4. Extra outputs the assignment asks for: feature importance ranking (CSV + plot),
     complexity comparison RAW vs RAW+FE (--raw-summary), accuracy progression, and
     the inference requirements (window buffer, feature work, delay).
  5. Latency is measured on numpy arrays, not DataFrames (the DataFrame call made the
     old figure mostly pandas overhead), and a tree walk on the exported JSON is timed too.
Unchanged: CSV loading, chronological per-recording split, windows that never cross a
split boundary, the same hyperparameters (defaults identical to model_raw.py),
and the C export for the board.

Example
  python model_raw_fe.py --curl Curl.csv --lateralraise LateralRaise.csv \
      --leftpunch LeftPunch.csv --output-dir task3_results \
      --raw-summary task2_results/model_summary.json
Window: --window-size samples (default 42), --stride (default 21 = 50 % overlap).
Raw inputs keep the units of the CSV (mg, mdps); the firmware must use the same units.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             ConfusionMatrixDisplay)
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree, _tree

RAW_CHANNELS = ["ACC_X", "ACC_Y", "ACC_Z", "GYR_X", "GYR_Y", "GYR_Z"]
CLASSES = ["Curl", "LateralRaise", "LeftPunch"]
# Order matters: the generated C code uses exactly this order.
STATISTICS = ["mean", "var", "max", "min", "p2p", "energy"]
ALL_FEATURE_NAMES = [f"{axis}__{stat}" for axis in RAW_CHANNELS for stat in STATISTICS]  # 36
N_STATS = len(STATISTICS)

MCU_CLOCK_HZ = 84e6       # NUCLEO-F401RE
CYCLES_PER_NODE = 12      # rough cost of one tree level (load, compare, branch)

ALIASES = {
    "ACC_X": {"accx", "accelx", "accelerometerx", "accelerationx"},
    "ACC_Y": {"accy", "accely", "accelerometery", "accelerationy"},
    "ACC_Z": {"accz", "accelz", "accelerometerz", "accelerationz"},
    "GYR_X": {"gyrx", "gyrox", "gyroscopex", "angularratex", "angvelx"},
    "GYR_Y": {"gyry", "gyroy", "gyroscopey", "angularratey", "angvely"},
    "GYR_Z": {"gyrz", "gyroz", "gyroscopez", "angularratez", "angvelz"},
}
UNIT_SUFFIXES = {"g", "mg", "ms2", "mss", "dps", "mdps", "radps", "rads", "raw", "count",
                 "counts", "degsec", "degreespersecond"}


# ----------------------------------------------------------------------------
# Loading (unchanged logic from the original script)
# ----------------------------------------------------------------------------
def normalize_column_name(name: str) -> str:
    text = str(name).strip().lower()
    text = re.sub(r"\.\d+$", "", text)
    text = re.sub(r"__\d+$", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def find_raw_columns(columns: Sequence[str], requested: Optional[Sequence[str]]) -> dict[str, str]:
    columns = [str(c) for c in columns]
    if requested:
        if len(requested) != 6:
            raise ValueError("--feature-columns expects six names in ACC_X ACC_Y ACC_Z GYR_X GYR_Y GYR_Z order.")
        result = {}
        for canonical, desired in zip(RAW_CHANNELS, requested):
            matches = [c for c in columns if c.strip().lower() == desired.strip().lower()]
            if not matches:
                raise ValueError(f"Column {desired!r} for {canonical} was not found. CSV columns: {columns}")
            result[canonical] = matches[0]
        return result
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for col in columns:
        norm = normalize_column_name(col)
        for canonical, aliases in ALIASES.items():
            recognized = norm in aliases or any(
                norm.startswith(a) and norm[len(a):] in UNIT_SUFFIXES for a in aliases)
            if recognized and canonical not in mapping and col not in used:
                mapping[canonical] = col
                used.add(col)
    missing = [n for n in RAW_CHANNELS if n not in mapping]
    if missing:
        raise ValueError(f"Could not detect IMU columns {missing}. Available headers: {columns}. "
                         "Use --feature-columns COL_ACC_X COL_ACC_Y COL_ACC_Z COL_GYR_X COL_GYR_Y COL_GYR_Z.")
    return mapping


def read_csv_flexible(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    last_error = None
    for delimiter in (None, ",", ";", "\t"):
        try:
            frame = pd.read_csv(path, comment="#", skip_blank_lines=True, sep=delimiter, engine="python")
            frame = frame.dropna(axis=1, how="all")
            frame.columns = [str(c).strip() for c in frame.columns]
            if len(frame.columns) >= 2:
                return frame
        except Exception as exc:
            last_error = exc
    raise ValueError(f"Could not parse {path}: {last_error}")


def load_recording(path: Path, label: str, requested_columns: Optional[Sequence[str]]) -> pd.DataFrame:
    source = read_csv_flexible(path)
    mapping = find_raw_columns(source.columns, requested_columns)
    frame = pd.DataFrame()
    for canonical in RAW_CHANNELS:
        frame[canonical] = pd.to_numeric(source[mapping[canonical]], errors="coerce")
    time_col = next((c for c in source.columns if normalize_column_name(c) in ("timeus", "time")), None)
    if time_col is not None:                       # only used to report the effective sampling rate
        frame["time_s"] = pd.to_numeric(source[time_col], errors="coerce") / 1e6
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=RAW_CHANNELS).reset_index(drop=True)
    if len(frame) < 50:
        raise ValueError(f"{path} has only {len(frame)} valid rows; need enough rows for windowed features.")
    frame["label"] = label
    frame["source_file"] = path.name
    frame["source_path"] = str(path.resolve())
    frame["source_row"] = np.arange(len(frame), dtype=int)
    print(f"Loaded {len(frame):,} samples: {path} -> {label}")
    print("  Column mapping: " + ", ".join(f"{k}={v}" for k, v in mapping.items()))
    return frame


def split_raw_recording(frame: pd.DataFrame, train_fraction: float, validation_fraction: float):
    n = len(frame)
    a = int(n * train_fraction)
    b = int(n * (train_fraction + validation_fraction))
    if a <= 0 or b <= a or b >= n:
        raise ValueError(f"Recording {frame['source_file'].iloc[0]} is too short for the requested split.")
    return {"train": frame.iloc[:a].copy(), "validation": frame.iloc[a:b].copy(), "test": frame.iloc[b:].copy()}


# Assign raw recordings or recording segments to partitions before constructing overlapping windows.
def assign_splits(recordings, split_mode: str, train_fraction: float, validation_fraction: float,
                  random_state: int):
    files_per_class = {label: sum(1 for lab, _ in recordings if lab == label) for label in CLASSES}
    mode = split_mode
    if mode == "auto":
        mode = "sessions" if all(files_per_class[c] >= 3 for c in CLASSES) else "chronological"
    if mode == "sessions" and not all(files_per_class[c] >= 3 for c in CLASSES):
        raise ValueError("Session split requires at least 3 CSV recordings per class.")
    pieces = {"train": [], "validation": [], "test": []}
    if mode == "sessions":
        rng = np.random.default_rng(random_state)
        for label in CLASSES:
            frames = [f for lab, f in recordings if lab == label]
            order = list(rng.permutation(len(frames)))
            n = len(frames)
            n_train = max(1, int(round(n * train_fraction)))
            n_val = max(1, int(round(n * validation_fraction)))
            if n_train + n_val >= n:
                n_train, n_val = n - 2, 1
            assignment = {}
            for idx in order[:n_train]:
                assignment[idx] = "train"
            for idx in order[n_train:n_train + n_val]:
                assignment[idx] = "validation"
            for idx in order[n_train + n_val:]:
                assignment[idx] = "test"
            for idx, frame in enumerate(frames):
                pieces[assignment[idx]].append(frame)
        return pieces, mode
    for _, frame in recordings:
        for name, sub in split_raw_recording(frame, train_fraction, validation_fraction).items():
            pieces[name].append(sub)
    return pieces, mode


# ----------------------------------------------------------------------------
# Windowing and the six statistics
# ----------------------------------------------------------------------------
def extract_window_features(window: np.ndarray) -> dict[str, float]:
    """window: (n_samples, 6) raw values -> 36 features.
    For each axis: mean, variance (population, ddof = 0), maximum, minimum,
    peak-to-peak (max - min) and energy (mean of the squared values)."""
    if window.ndim != 2 or window.shape[1] != len(RAW_CHANNELS):
        raise ValueError("Window must have shape (window_size, 6).")
    x = np.asarray(window, dtype=np.float64)
    mean = x.mean(axis=0)
    var = x.var(axis=0)
    mx, mn = x.max(axis=0), x.min(axis=0)
    energy = (x * x).mean(axis=0)
    out: dict[str, float] = {}
    for i, axis in enumerate(RAW_CHANNELS):
        for stat, value in zip(STATISTICS, (mean[i], var[i], mx[i], mn[i], mx[i] - mn[i], energy[i])):
            out[f"{axis}__{stat}"] = float(value)
    return out


def windows_from_segment(frame: pd.DataFrame, window_size: int, stride: int) -> pd.DataFrame:
    """Windows are cut inside one segment, so no window crosses a train/val/test boundary."""
    raw = frame[RAW_CHANNELS].to_numpy(dtype=np.float64)
    rows = []
    label = str(frame["label"].iloc[0])
    source_file = str(frame["source_file"].iloc[0])
    source_row = frame["source_row"].to_numpy(dtype=int)
    gaps = np.array([], dtype=int)
    if "time_s" in frame:
        steps = np.diff(frame["time_s"].to_numpy())
        # Mark pauses and non-increasing timestamps so windows span consecutive samples.
        gaps = np.flatnonzero((steps > 0.1) | (steps <= 0))
    for start in range(0, len(frame) - window_size + 1, stride):
        if np.any((gaps >= start) & (gaps < start + window_size - 1)):
            continue
        feats = extract_window_features(raw[start:start + window_size])
        # Keep source row bounds so each prediction can be traced to its input window.
        feats.update({"label": label, "source_file": source_file,
                      "window_start_row": int(source_row[start]),
                      "window_end_row": int(source_row[start + window_size - 1])})
        rows.append(feats)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# JSON + C export
# ----------------------------------------------------------------------------
def c_identifier(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_]", "_", str(value).upper())
    return ("CLASS_" + out) if (not out or out[0].isdigit()) else out


def c_float(value: float) -> str:
    text = format(float(value), ".9g")
    if "." not in text and "e" not in text.lower():
        text += ".0"
    return text + "f"


def export_tree_json(model, path: Path, window_size: int, stride: int, args, extra: dict) -> dict:
    tree = model.tree_
    class_names = [str(v) for v in model.classes_]
    nodes = []
    for node_id in range(tree.node_count):
        fi = int(tree.feature[node_id])
        leaf = fi == _tree.TREE_UNDEFINED
        values = [float(v) for v in tree.value[node_id][0]]
        pred = int(np.argmax(values))
        nodes.append({
            "node_id": node_id,
            "feature_index": None if leaf else fi,
            "feature_name": None if leaf else ALL_FEATURE_NAMES[fi],
            "threshold": None if leaf else float(tree.threshold[node_id]),
            "left_child": None if leaf else int(tree.children_left[node_id]),
            "right_child": None if leaf else int(tree.children_right[node_id]),
            "is_leaf": bool(leaf),
            "predicted_class_index": pred,
            "predicted_class": class_names[pred] if leaf else None,
            "class_counts": {class_names[i]: values[i] for i in range(len(class_names))},
            "samples": int(tree.n_node_samples[node_id]),
            "impurity": float(tree.impurity[node_id]),
        })
    payload = {
        "format": "imu_feature_decision_tree_v2",
        "description": "Decision tree on 36 windowed IMU features (6 statistics x 6 axes); no feature selection.",
        "raw_channels": RAW_CHANNELS,
        "raw_units_note": "Input sample units and axis convention must match the CSV used for training.",
        "window_size_samples": int(window_size),
        "recommended_stride_samples": int(stride),
        "statistic_order_per_axis": STATISTICS,
        "statistic_definitions": {
            "mean": "average", "var": "population variance (divide by n)", "max": "maximum",
            "min": "minimum", "p2p": "max - min", "energy": "mean of squares (sum of squares / n)"},
        "all_engineered_features": ALL_FEATURE_NAMES,
        "selected_features": ALL_FEATURE_NAMES,
        "selected_feature_indices_in_all_features": list(range(len(ALL_FEATURE_NAMES))),
        "classes": class_names,
        "tree_depth": int(model.get_depth()),
        "leaf_count": int(model.get_n_leaves()),
        "node_count": int(tree.node_count),
        "criterion": args.criterion, "max_depth": args.max_depth,
        "min_samples_leaf": args.min_samples_leaf, "min_samples_split": args.min_samples_split,
        "nodes": nodes,
        **extra,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


# Emit the same feature order and tree traversal that the Python model uses.
def generate_c_from_json(json_path: Path, out_prefix: Path) -> tuple[Path, Path]:
    p = json.loads(json_path.read_text(encoding="utf-8"))
    if p.get("format") != "imu_feature_decision_tree_v2":
        raise ValueError("This JSON is not an imu_feature_decision_tree_v2 file.")
    channels, stats, all_names = p["raw_channels"], p["statistic_order_per_axis"], p["all_engineered_features"]
    nodes, classes, n = p["nodes"], p["classes"], int(p["window_size_samples"])
    if n < 2 or stats != ["mean", "var", "max", "min", "p2p", "energy"]:
        raise ValueError("Unsupported window size or statistic order.")
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    c_path, h_path = out_prefix.with_suffix(".c"), out_prefix.with_suffix(".h")
    guard = re.sub(r"[^A-Za-z0-9_]", "_", out_prefix.name.upper()) + "_H"
    enum_items = [f"    IMU_FEATURE_CLASS_{c_identifier(c)} = {i}" for i, c in enumerate(classes)]
    enum_items.append("    IMU_FEATURE_CLASS_UNKNOWN = 255")
    comments = "\n".join(f" *   {i}: {name}" for i, name in enumerate(all_names))
    h_path.write_text(f'''/* Auto-generated from {json_path.name}; do not edit by hand.
 * Window length: {n} samples. Raw channel order: {", ".join(channels)}.
 * Raw input units MUST match the training CSV (mg and mdps for MEMS Studio logs).
 * Feature order seen by the tree (6 statistics per axis: mean, var, max, min, p2p, energy):
{comments}
 */
#ifndef {guard}
#define {guard}
#include <stdint.h>
#define IMU_FEATURE_TREE_WINDOW_SIZE ((uint32_t){n}u)
#define IMU_FEATURE_TREE_RAW_CHANNELS ((uint32_t){len(channels)}u)
#define IMU_FEATURE_TREE_FEATURE_COUNT ((uint32_t){len(all_names)}u)
#define IMU_FEATURE_TREE_NODE_COUNT ((uint32_t){len(nodes)}u)

typedef enum {{
{",\n".join(enum_items)}
}} imu_feature_tree_class_t;

/* Call with a complete window [sample][channel] in the documented order and units. */
imu_feature_tree_class_t imu_feature_tree_predict_window(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS]);
#endif /* {guard} */
''', encoding="utf-8")
    rows = []
    for node in nodes:
        fi = node["feature_index"]
        if fi is None:
            rows.append(f"    {{-1, 0.0f, -1, -1, {int(node['predicted_class_index'])}u}},")
        else:
            rows.append(f"    {{{int(fi)}, {c_float(node['threshold'])}, {int(node['left_child'])}, "
                        f"{int(node['right_child'])}, {int(node['predicted_class_index'])}u}},")
    c_path.write_text(f'''/* Auto-generated from {json_path.name}; do not edit by hand. */
#include "{h_path.name}"
#include <stddef.h>
#include <stdint.h>

typedef struct {{ int16_t feature_index; float threshold; int32_t left; int32_t right; uint8_t predicted_class; }} imu_feature_tree_node_t;
static const imu_feature_tree_node_t imu_tree_nodes[{len(nodes)}] = {{
{chr(10).join(rows)}
}};

/* The 36 features, in the same order as Python's extract_window_features():
   per axis: mean, variance (divide by n), max, min, peak-to-peak, energy (mean of squares). */
static void imu_compute_features(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS],
    float out[IMU_FEATURE_TREE_FEATURE_COUNT])
{{
    uint32_t axis, i;
    for (axis = 0u; axis < IMU_FEATURE_TREE_RAW_CHANNELS; ++axis) {{
        float sum = 0.0f, sum_sq = 0.0f, mean, variance = 0.0f;
        float minimum = samples[0][axis], maximum = samples[0][axis];
        uint32_t base = axis * {N_STATS}u;
        for (i = 0u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {{
            float v = samples[i][axis];
            sum += v;
            sum_sq += v * v;
            if (v < minimum) minimum = v;
            if (v > maximum) maximum = v;
        }}
        mean = sum / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
        for (i = 0u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {{
            float d = samples[i][axis] - mean;
            variance += d * d;
        }}
        out[base + 0u] = mean;
        out[base + 1u] = variance / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
        out[base + 2u] = maximum;
        out[base + 3u] = minimum;
        out[base + 4u] = maximum - minimum;
        out[base + 5u] = sum_sq / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
    }}
}}

imu_feature_tree_class_t imu_feature_tree_predict_window(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS])
{{
    float features[IMU_FEATURE_TREE_FEATURE_COUNT];
    int32_t node_index = 0;
    uint32_t steps;
    if (samples == NULL) return IMU_FEATURE_CLASS_UNKNOWN;
    imu_compute_features(samples, features);
    for (steps = 0u; steps < IMU_FEATURE_TREE_NODE_COUNT; ++steps) {{
        const imu_feature_tree_node_t *node;
        if (node_index < 0 || (uint32_t)node_index >= IMU_FEATURE_TREE_NODE_COUNT) return IMU_FEATURE_CLASS_UNKNOWN;
        node = &imu_tree_nodes[node_index];
        if (node->feature_index < 0) return (imu_feature_tree_class_t)node->predicted_class;
        if ((uint32_t)node->feature_index >= IMU_FEATURE_TREE_FEATURE_COUNT) return IMU_FEATURE_CLASS_UNKNOWN;
        node_index = (features[node->feature_index] <= node->threshold) ? node->left : node->right;
    }}
    return IMU_FEATURE_CLASS_UNKNOWN;
}}
''', encoding="utf-8")
    return c_path, h_path


# ----------------------------------------------------------------------------
# Evaluation helpers
# ----------------------------------------------------------------------------
def tree_depth_profile(model) -> pd.DataFrame:
    t = model.tree_
    depth = np.zeros(t.node_count, dtype=int)
    for i in range(t.node_count):
        for child in (t.children_left[i], t.children_right[i]):
            if child != -1:
                depth[child] = depth[i] + 1
    leaf = t.children_left == t.children_right
    return pd.DataFrame([{"depth": d, "nodes": int((depth == d).sum()),
                          "leaves": int(((depth == d) & leaf).sum())} for d in range(depth.max() + 1)])


# Benchmark host-side processing. Treat any MCU timing derived from assumed cycles as an estimate.
def measure_latency(model, X: np.ndarray, tree_json: dict, windows: np.ndarray) -> dict:
    """Host-PC timings (relative cost only) and a cycle estimate for the MCU."""
    x1 = X[:1]
    t0 = time.perf_counter()
    for _ in range(300):
        model.predict(x1)
    single_us = (time.perf_counter() - t0) / 300 * 1e6
    nodes = {n["node_id"]: n for n in tree_json["nodes"]}
    reps = max(1, 5000 // len(X))
    t0 = time.perf_counter()
    for _ in range(reps):
        for x in X:
            n = nodes[0]
            while not n["is_leaf"]:
                n = nodes[n["left_child"]] if x[n["feature_index"]] <= n["threshold"] else nodes[n["right_child"]]
    walk_us = (time.perf_counter() - t0) / (reps * len(X)) * 1e6
    t0 = time.perf_counter()
    for _ in range(300):
        extract_window_features(windows[0])
    feat_us = (time.perf_counter() - t0) / 300 * 1e6
    return {"sklearn_single_call_us": single_us, "json_walk_us": walk_us,
            "feature_extraction_host_us_per_window": feat_us,
            "mcu_tree_worst_case_us_est": model.get_depth() * CYCLES_PER_NODE / MCU_CLOCK_HZ * 1e6}


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def run_training(args) -> None:
    if not (0 < args.train_fraction < 1 and 0 < args.validation_fraction < 1
            and args.train_fraction + args.validation_fraction < 1):
        raise ValueError("Train and validation fractions must be > 0 and sum to less than 1.")
    if args.window_size < 2 or args.stride < 1:
        raise ValueError("--window-size must be >= 2 and --stride >= 1.")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for label, files in [("Curl", args.curl), ("LateralRaise", args.lateralraise), ("LeftPunch", args.leftpunch)]:
        if not files:
            raise ValueError(f"Provide at least one --{label.lower()} CSV file.")
        paths += [(label, Path(f)) for f in files]
    recordings = [(label, load_recording(path, label, args.feature_columns)) for label, path in paths]

    # effective sampling rate (for reporting the window duration only)
    rates = []
    for _, fr in recordings:
        if "time_s" in fr and fr["time_s"].notna().all() and len(fr) > 2:
            rates.append(1.0 / float(np.diff(fr["time_s"]).mean()))
    eff_rate = float(np.mean(rates)) if rates else None

    raw_pieces, mode = assign_splits(recordings, args.split_mode, args.train_fraction,
                                     args.validation_fraction, args.random_state)
    window_pieces: dict[str, list[pd.DataFrame]] = {"train": [], "validation": [], "test": []}
    for split_name, frames in raw_pieces.items():
        for fr in frames:
            w = windows_from_segment(fr, args.window_size, args.stride)
            if not w.empty:
                w["split"] = split_name
                window_pieces[split_name].append(w)
    combined = {}
    for name, frames in window_pieces.items():
        if not frames:
            raise ValueError(f"No windows were generated for {name}. Check recording length vs window settings.")
        combined[name] = pd.concat(frames, ignore_index=True)
        missing = set(CLASSES) - set(combined[name]["label"].unique())
        if missing:
            raise ValueError(f"The {name} split is missing classes {sorted(missing)}.")
    train_df, val_df, test_df = combined["train"], combined["validation"], combined["test"]

    model = DecisionTreeClassifier(criterion=args.criterion, max_depth=args.max_depth,
                                   min_samples_leaf=args.min_samples_leaf,
                                   min_samples_split=args.min_samples_split,
                                   random_state=args.random_state)
    # Train on all 36 window statistics. Feature selection is evaluated separately in Task 5.
    model.fit(train_df[ALL_FEATURE_NAMES].to_numpy(dtype=np.float64), train_df["label"].astype(str))
    class_names = [str(c) for c in model.classes_]
    print("\n=== Windows and features ===")
    dur = f" (about {args.window_size / eff_rate:.2f} s at the effective {eff_rate:.1f} Hz)" if eff_rate else ""
    print(f"Window: {args.window_size} samples{dur}; stride {args.stride} samples "
          f"({100 * (1 - args.stride / args.window_size):.0f} % overlap)")
    print(f"Features: {len(RAW_CHANNELS)} axes x {N_STATS} statistics = {len(ALL_FEATURE_NAMES)} (no feature selection)")
    print(f"Split strategy: {mode}")
    print(f"Hyperparameters: criterion={args.criterion}, max_depth={args.max_depth}, "
          f"min_samples_leaf={args.min_samples_leaf}, min_samples_split={args.min_samples_split}, "
          f"random_state={args.random_state}")
    for nm, fr in [("Train", train_df), ("Validation", val_df), ("Test", test_df)]:
        print(f"{nm:10s}: {len(fr):,} windows; class counts={fr['label'].value_counts().to_dict()}")

    metrics, preds, acc = [], [], {}
    for name in ("train", "validation", "test"):
        fr = combined[name]
        y = fr["label"].astype(str)
        p = model.predict(fr[ALL_FEATURE_NAMES].to_numpy(dtype=np.float64))
        acc[name] = float(accuracy_score(y, p))
        rep = classification_report(y, p, labels=class_names, target_names=class_names,
                                    output_dict=True, zero_division=0)
        print(f"\n{name.upper()} (accuracy={acc[name]:.4f})")
        print(classification_report(y, p, labels=class_names, target_names=class_names, zero_division=0))
        for label in class_names + ["macro avg", "weighted avg"]:
            r = rep[label]
            metrics.append({"split": name, "class": label, "precision": r["precision"], "recall": r["recall"],
                            "f1_score": r["f1-score"], "support": r["support"], "accuracy_overall": acc[name]})
        pf = fr[["label", "source_file", "window_start_row", "window_end_row"]].copy()
        pf["predicted_label"] = p
        pf["correct"] = pf["label"].astype(str) == pf["predicted_label"].astype(str)
        pf["split"] = name
        preds.append(pf)
    pd.DataFrame(metrics).to_csv(out_dir / "metrics_by_class.csv", index=False)
    allp = pd.concat(preds, ignore_index=True)
    allp.to_csv(out_dir / "predictions_all_splits.csv", index=False)
    allp[(allp["split"] == "test") & (~allp["correct"])].to_csv(out_dir / "test_misclassifications.csv", index=False)
    gap = acc["train"] - acc["test"]

    # confusion matrix (numbers + heatmap)
    ytest = test_df["label"].astype(str)
    ptest = model.predict(test_df[ALL_FEATURE_NAMES].to_numpy(dtype=np.float64))
    cm = confusion_matrix(ytest, ptest, labels=class_names)
    pd.DataFrame(cm, index=[f"Actual {c}" for c in class_names],
                 columns=[f"Predicted {c}" for c in class_names]).to_csv(out_dir / "confusion_matrix_test.csv")
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    ConfusionMatrixDisplay(cm, display_labels=class_names).plot(ax=ax[0], cmap="Blues", values_format="d", colorbar=False)
    ax[0].set_title("RAW+FE - test confusion matrix (counts)")
    ConfusionMatrixDisplay(cm / cm.sum(axis=1, keepdims=True).clip(min=1), display_labels=class_names).plot(
        ax=ax[1], cmap="Blues", values_format=".3f", colorbar=False)
    ax[1].set_title("RAW+FE - row-normalised")
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_matrix_test.png", dpi=160)
    plt.close(fig)

    # feature importance (all 36 engineered features)
    imp = pd.DataFrame({"feature": ALL_FEATURE_NAMES, "importance": model.feature_importances_})
    imp = imp.sort_values("importance", ascending=False).reset_index(drop=True)
    imp.to_csv(out_dir / "feature_importance.csv", index=False)
    top = imp.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 5.5))
    bars = ax.barh(top["feature"], top["importance"], color="steelblue")
    ax.bar_label(bars, fmt="%.3f")
    ax.set_xlabel("Gini importance")
    ax.set_title("RAW+FE - top 15 engineered features")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "feature_importance_top15.png", dpi=160)
    plt.close(fig)
    by_axis = {a: float(imp[imp.feature.str.startswith(a + "__")].importance.sum()) for a in RAW_CHANNELS}
    by_stat = {s: float(imp[imp.feature.str.endswith("__" + s)].importance.sum()) for s in STATISTICS}

    # tree plot, rules, depth profile
    fig, ax = plt.subplots(figsize=(14, 7))
    plot_tree(model, feature_names=ALL_FEATURE_NAMES, class_names=class_names, filled=True, rounded=True,
              max_depth=args.plot_depth, fontsize=7, ax=ax, impurity=False)
    ax.set_title(f"RAW+FE decision tree (display limited to depth {args.plot_depth}; full tree in JSON)")
    fig.tight_layout()
    fig.savefig(out_dir / "tree_structure.png", dpi=160)
    plt.close(fig)
    (out_dir / "decision_tree_rules.txt").write_text(
        export_text(model, feature_names=ALL_FEATURE_NAMES, decimals=6), encoding="utf-8")
    tree_depth_profile(model).to_csv(out_dir / "depth_profile.csv", index=False)

    # JSON + C
    extra = {"effective_sample_rate_hz": eff_rate}
    json_path = out_dir / "decision_tree_raw_fe.json"
    payload = export_tree_json(model, json_path, args.window_size, args.stride, args, extra)
    c_path, h_path = generate_c_from_json(json_path, out_dir / "decision_tree_raw_fe")

    # latency and inference requirements
    raw_windows = np.stack([recordings[0][1][RAW_CHANNELS].to_numpy(dtype=np.float64)[:args.window_size]])
    lat = measure_latency(model, test_df[ALL_FEATURE_NAMES].to_numpy(dtype=np.float64), payload, raw_windows)
    buf_bytes = args.window_size * len(RAW_CHANNELS) * 4
    json_kb = json_path.stat().st_size / 1024.0
    c_bytes = c_path.stat().st_size + h_path.stat().st_size
    summary = {
        "model_type": "DecisionTreeClassifier on windowed IMU statistics (6 statistics x 6 axes)",
        "raw_channels": RAW_CHANNELS, "classes": class_names, "statistics": STATISTICS,
        "feature_count": len(ALL_FEATURE_NAMES),
        "window_size_samples": args.window_size, "stride_samples": args.stride,
        "overlap_percent": round(100 * (1 - args.stride / args.window_size), 1),
        "effective_sample_rate_hz": eff_rate,
        "window_duration_s_at_effective_rate": (args.window_size / eff_rate) if eff_rate else None,
        "split_mode": mode,
        "train_windows": len(train_df), "validation_windows": len(val_df), "test_windows": len(test_df),
        "criterion": args.criterion, "max_depth_setting": args.max_depth,
        "min_samples_leaf": args.min_samples_leaf, "min_samples_split": args.min_samples_split,
        "random_state": args.random_state,
        "train_accuracy": acc["train"], "validation_accuracy": acc["validation"], "test_accuracy": acc["test"],
        "generalization_gap_train_minus_test": gap,
        "tree_depth": int(model.get_depth()), "leaf_count": int(model.get_n_leaves()),
        "node_count": int(model.tree_.node_count),
        "json_file": json_path.name, "json_size_kb": round(json_kb, 3),
        "c_source_and_header_combined_bytes": c_bytes,
        "embedded_tree_size_bytes_est": int(model.tree_.node_count * 9),
        "window_buffer_bytes": buf_bytes,
        "features_used_by_tree": [n for n in ALL_FEATURE_NAMES if imp.set_index("feature").loc[n, "importance"] > 0],
        "importance_by_axis": by_axis, "importance_by_statistic": by_stat,
        "top_features": imp.head(10).set_index("feature")["importance"].to_dict(),
        **{k: float(v) for k, v in lat.items()},
        "latency_note": "Host timings show relative cost only; the MCU figure is an estimate "
                        f"({CYCLES_PER_NODE} cycles per tree level at {MCU_CLOCK_HZ / 1e6:.0f} MHz). "
                        "Measure the generated C function on the board for real numbers.",
        "evaluation_note": ("Recording sessions were held out by file." if mode == "sessions" else
                            "Chronological portions of each recording were used; these results do not test "
                            "generalisation to independently recorded sessions."),
    }
    (out_dir / "model_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    pd.DataFrame([{"train_accuracy": acc["train"], "validation_accuracy": acc["validation"],
                   "test_accuracy": acc["test"], "generalization_gap_train_minus_test": gap,
                   "tree_depth": summary["tree_depth"], "leaf_count": summary["leaf_count"],
                   "node_count": summary["node_count"]}]).to_csv(out_dir / "accuracy_and_complexity_summary.csv", index=False)

    # complexity comparison against Task 2 (RAW)
    if args.raw_summary and Path(args.raw_summary).is_file():
        raw = json.loads(Path(args.raw_summary).read_text())
        rows = [("Input to the tree", "1 sample", f"{args.window_size}-sample window"),
                ("Features", 6, len(ALL_FEATURE_NAMES)),
                ("Tree depth", raw["tree_depth"], summary["tree_depth"]),
                ("Leaves", raw["leaf_count"], summary["leaf_count"]),
                ("Nodes", raw["node_count"], summary["node_count"]),
                ("JSON size [KB]", raw["json_size_kb"], summary["json_size_kb"]),
                ("Estimated size in C [bytes]", raw["node_count"] * 9, summary["embedded_tree_size_bytes_est"]),
                ("Train accuracy [%]", round(100 * raw["train_accuracy"], 2), round(100 * acc["train"], 2)),
                ("Validation accuracy [%]", round(100 * raw["validation_accuracy"], 2), round(100 * acc["validation"], 2)),
                ("Test accuracy [%]", round(100 * raw["test_accuracy"], 2), round(100 * acc["test"], 2)),
                ("Generalisation gap [points]", round(100 * raw["generalization_gap_train_minus_test"], 2), round(100 * gap, 2)),
                ("Window buffer [bytes]", 0, buf_bytes),
                ("Work before the tree", "none", "36 statistics per window"),
                ("Decision rate", "every sample", f"every {args.stride} samples"),
                ("Delay to first decision", "1 sample", f"{args.window_size} samples")]
        pd.DataFrame(rows, columns=["metric", "RAW (Task 2)", "RAW+FE (Task 3)"]).to_csv(
            out_dir / "complexity_comparison.csv", index=False)

    print("\n=== Result ===")
    print(f"Accuracy train/val/test: {acc['train']:.4f} / {acc['validation']:.4f} / {acc['test']:.4f} (gap {gap:+.4f})")
    print(f"Tree depth {model.get_depth()}, leaves {model.get_n_leaves()}, nodes {model.tree_.node_count}; JSON {json_kb:.2f} KB")
    print("Features used by the tree:", summary["features_used_by_tree"])
    print(f"Window buffer {buf_bytes} bytes; host feature extraction {lat['feature_extraction_host_us_per_window']:.1f} us/window; "
          f"JSON walk {lat['json_walk_us']:.2f} us; MCU tree estimate {lat['mcu_tree_worst_case_us_est']:.2f} us")
    print(f"Outputs: {out_dir.resolve()}\nJSON: {json_path}\nC: {c_path}\nH: {h_path}")


def build_parser():
    p = argparse.ArgumentParser(description="Task 3 RAW+FE: windowed IMU statistics -> decision tree -> JSON and C.")
    p.add_argument("--curl", nargs="+")
    p.add_argument("--lateralraise", nargs="+")
    p.add_argument("--leftpunch", nargs="+")
    p.add_argument("--feature-columns", nargs=6, metavar=("ACC_X", "ACC_Y", "ACC_Z", "GYR_X", "GYR_Y", "GYR_Z"))
    p.add_argument("--output-dir", default="task3_results")
    p.add_argument("--raw-summary", default=None, help="Task 2 model_summary.json, for the complexity comparison")
    p.add_argument("--window-size", type=int, default=42, help="Samples per window (default 42)")
    p.add_argument("--stride", type=int, default=21, help="Step between windows (default 21 = 50%% overlap)")
    p.add_argument("--train-fraction", type=float, default=0.70)
    p.add_argument("--validation-fraction", type=float, default=0.15)
    p.add_argument("--split-mode", choices=["auto", "chronological", "sessions"], default="auto")
    # Same defaults as model_raw.py (Task 2): keep them identical in all tasks.
    p.add_argument("--max-depth", type=int, default=None)
    p.add_argument("--min-samples-leaf", type=int, default=1)
    p.add_argument("--min-samples-split", type=int, default=2)
    p.add_argument("--criterion", choices=["gini", "entropy", "log_loss"], default="gini")
    p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--plot-depth", type=int, default=3)
    p.add_argument("--convert-json", type=Path, help="Only regenerate C/H from decision_tree_raw_fe.json")
    p.add_argument("--c-out-prefix", type=Path)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.convert_json:
            prefix = args.c_out_prefix or args.convert_json.with_suffix("")
            c_path, h_path = generate_c_from_json(args.convert_json, prefix)
            print(f"Generated C source: {c_path}\nGenerated C header: {h_path}")
            return 0
        if not (args.curl and args.lateralraise and args.leftpunch):
            parser.error("Supply --curl, --lateralraise and --leftpunch (or use --convert-json).")
        run_training(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
