#!/usr/bin/env python3
"""Feature-engineered IMU decision tree with Recursive Feature Elimination (RFE).

This is a SEPARATE pipeline from imu_tree_pipeline.py. It creates time-domain
features over windows of six IMU axes, selects a subset using RFE, trains a
DecisionTreeClassifier, evaluates it, exports a complete JSON tree, and generates
C/H code which computes the selected window features and executes the tree.

CSV inputs: one or more recordings for each class, with accelerometer and
 gyroscope columns. Common headers such as acc_x[mg] and gyro_x[mdps] are detected.

Install:
    python -m pip install pandas scikit-learn matplotlib numpy

Example (Windows CMD or PowerShell):
    python .\\imu_feature_rfe_pipeline.py --horizontal .\\Horizontal.csv --static .\\Static.csv --vertical .\\Vertical.csv --output-dir .\\feature_rfe_results

Model behavior:
- Default window length: 42 samples, default stride: 21 samples (50% overlap).
- Feature extraction is performed independently inside each train/validation/test
  segment, so a window does not cross a split boundary.
- RFE is fitted only on the training windows, not validation/test data.
- Firmware input must use the same six channel order, physical units, and axis
  convention as the CSV logs. Pass a full 42-sample window to the generated C API.
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
from sklearn.feature_selection import RFE
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree, _tree

RAW_CHANNELS = ["ACC_X", "ACC_Y", "ACC_Z", "GYR_X", "GYR_Y", "GYR_Z"]
CLASSES = ["Horizontal", "Static", "Vertical"]
# Feature order matters: the C feature extractor uses this exact sequence.
STATISTICS = [
    "mean", "std", "min", "max", "range", "rms", "median", "iqr",
    "mean_abs", "zero_crossing_rate", "waveform_length",
]
ALL_FEATURE_NAMES = [f"{axis}__{stat}" for axis in RAW_CHANNELS for stat in STATISTICS]
N_STATS = len(STATISTICS)

ALIASES = {
    "ACC_X": {"accx", "accelx", "accelerometerx", "accelerationx"},
    "ACC_Y": {"accy", "accely", "accelerometery", "accelerationy"},
    "ACC_Z": {"accz", "accelz", "accelerometerz", "accelerationz"},
    "GYR_X": {"gyrx", "gyrox", "gyroscopex", "angularratex", "angvelx"},
    "GYR_Y": {"gyry", "gyroy", "gyroscopey", "angularratey", "angvely"},
    "GYR_Z": {"gyrz", "gyroz", "gyroscopez", "angularratez", "angvelz"},
}
UNIT_SUFFIXES = {
    "g", "mg", "ms2", "mss", "dps", "mdps", "radps", "rads",
    "raw", "count", "counts", "degsec", "degreespersecond",
}


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
            matches = [col for col in columns if col.strip().lower() == desired.strip().lower()]
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
                norm.startswith(alias) and norm[len(alias):] in UNIT_SUFFIXES
                for alias in aliases
            )
            if recognized and canonical not in mapping and col not in used:
                mapping[canonical] = col
                used.add(col)
    missing = [name for name in RAW_CHANNELS if name not in mapping]
    if missing:
        raise ValueError(
            f"Could not detect IMU columns {missing}. Available headers: {columns}. "
            "Use --feature-columns COL_ACC_X COL_ACC_Y COL_ACC_Z COL_GYR_X COL_GYR_Y COL_GYR_Z."
        )
    return mapping


def read_csv_flexible(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    last_error = None
    for delimiter, engine in [(None, "python"), (",", "python"), (";", "python"), ("\t", "python")]:
        try:
            frame = pd.read_csv(path, comment="#", skip_blank_lines=True, sep=delimiter, engine=engine)
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
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=RAW_CHANNELS).reset_index(drop=True)
    if len(frame) < 50:
        raise ValueError(f"{path} has only {len(frame)} valid rows; need enough rows for windowed feature extraction.")
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
    return {
        "train": frame.iloc[:a].copy(),
        "validation": frame.iloc[a:b].copy(),
        "test": frame.iloc[b:].copy(),
    }


def percentile_sorted(sorted_values: np.ndarray, quantile: float) -> float:
    """Linear percentile interpolation, equivalent to NumPy's default percentile method."""
    return float(np.percentile(sorted_values, quantile * 100.0))


def extract_window_features(window: np.ndarray) -> dict[str, float]:
    if window.ndim != 2 or window.shape[1] != len(RAW_CHANNELS):
        raise ValueError("Window must have shape (window_size, 6).")
    result: dict[str, float] = {}
    n = window.shape[0]
    if n < 2:
        raise ValueError("Window must contain at least 2 samples.")
    for axis_index, axis_name in enumerate(RAW_CHANNELS):
        x = np.asarray(window[:, axis_index], dtype=np.float64)
        mean = float(np.mean(x))
        std = float(np.std(x, ddof=0))
        min_value = float(np.min(x))
        max_value = float(np.max(x))
        rms = float(np.sqrt(np.mean(x * x)))
        median = float(np.median(x))
        q1 = percentile_sorted(x, 0.25)
        q3 = percentile_sorted(x, 0.75)
        mean_abs = float(np.mean(np.abs(x)))
        waveform_length = float(np.sum(np.abs(np.diff(x))))
        centered = x - mean
        signs = np.sign(centered)
        last_nonzero_sign = 0
        crossings = 0
        for sign_value in signs:
            sign_int = 1 if sign_value > 0 else (-1 if sign_value < 0 else 0)
            if sign_int == 0:
                continue
            if last_nonzero_sign != 0 and sign_int != last_nonzero_sign:
                crossings += 1
            last_nonzero_sign = sign_int
        zcr = float(crossings / (n - 1))

        values = [mean, std, min_value, max_value, max_value - min_value, rms,
                  median, q3 - q1, mean_abs, zcr, waveform_length]
        for stat_name, value in zip(STATISTICS, values):
            result[f"{axis_name}__{stat_name}"] = float(value)
    return result


def windows_from_segment(frame: pd.DataFrame, window_size: int, stride: int) -> pd.DataFrame:
    raw = frame[RAW_CHANNELS].to_numpy(dtype=np.float64)
    rows = []
    label = str(frame["label"].iloc[0])
    source_file = str(frame["source_file"].iloc[0])
    source_path = str(frame["source_path"].iloc[0])
    source_row = frame["source_row"].to_numpy(dtype=int)
    for start in range(0, len(frame) - window_size + 1, stride):
        features = extract_window_features(raw[start:start + window_size])
        features.update({
            "label": label,
            "source_file": source_file,
            "source_path": source_path,
            "window_start_row": int(source_row[start]),
            "window_end_row": int(source_row[start + window_size - 1]),
        })
        rows.append(features)
    return pd.DataFrame(rows)


def assign_splits(recordings, split_mode: str, train_fraction: float, validation_fraction: float, random_state: int):
    files_per_class = {label: sum(1 for lab, _ in recordings if lab == label) for label in CLASSES}
    mode = split_mode
    if mode == "auto":
        mode = "sessions" if all(files_per_class[c] >= 3 for c in CLASSES) else "chronological"
    if mode == "sessions" and not all(files_per_class[c] >= 3 for c in CLASSES):
        raise ValueError("Session split requires at least 3 separate CSV recordings per class; use --split-mode chronological or add more logs.")
    pieces = {"train": [], "validation": [], "test": []}
    if mode == "sessions":
        rng = np.random.default_rng(random_state)
        for label in CLASSES:
            class_frames = [frame for lab, frame in recordings if lab == label]
            order = list(rng.permutation(len(class_frames)))
            n = len(class_frames)
            n_train = max(1, int(round(n * train_fraction)))
            n_val = max(1, int(round(n * validation_fraction)))
            if n_train + n_val >= n:
                n_train, n_val = n - 2, 1
            assignment = {}
            for idx in order[:n_train]: assignment[idx] = "train"
            for idx in order[n_train:n_train + n_val]: assignment[idx] = "validation"
            for idx in order[n_train + n_val:]: assignment[idx] = "test"
            for idx, frame in enumerate(class_frames):
                pieces[assignment[idx]].append(frame)
        return pieces, mode

    for _, frame in recordings:
        split_frames = split_raw_recording(frame, train_fraction, validation_fraction)
        for split_name, subframe in split_frames.items():
            pieces[split_name].append(subframe)
    return pieces, mode


def c_identifier(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_]", "_", str(value).upper())
    if not out or out[0].isdigit():
        out = "CLASS_" + out
    return out


def c_float(value: float) -> str:
    text = format(float(value), ".9g")
    if "." not in text and "e" not in text.lower():
        text += ".0"
    return text + "f"


def percentile_c_expression(q: str) -> str:
    return q


def export_tree_json(model: DecisionTreeClassifier, selected_names: list[str], selected_indices: list[int],
                     rfe_ranking: dict[str, int], path: Path, window_size: int, stride: int, args) -> dict:
    tree = model.tree_
    class_names = [str(v) for v in model.classes_]
    nodes = []
    for node_id in range(tree.node_count):
        feat_idx = int(tree.feature[node_id])
        is_leaf = feat_idx == _tree.TREE_UNDEFINED
        values = [float(v) for v in tree.value[node_id][0]]
        pred_idx = int(np.argmax(values))
        nodes.append({
            "node_id": node_id,
            "feature_index": None if is_leaf else feat_idx,
            "feature_name": None if is_leaf else selected_names[feat_idx],
            "threshold": None if is_leaf else float(tree.threshold[node_id]),
            "left_child": None if is_leaf else int(tree.children_left[node_id]),
            "right_child": None if is_leaf else int(tree.children_right[node_id]),
            "is_leaf": bool(is_leaf),
            "predicted_class_index": pred_idx,
            "predicted_class": class_names[pred_idx] if is_leaf else None,
            "class_counts": {class_names[i]: values[i] for i in range(len(class_names))},
            "samples": int(tree.n_node_samples[node_id]),
            "impurity": float(tree.impurity[node_id]),
        })
    payload = {
        "format": "imu_feature_rfe_decision_tree_v1",
        "description": "Decision tree trained on windowed IMU time-domain features selected with Recursive Feature Elimination.",
        "raw_channels": RAW_CHANNELS,
        "raw_units_note": "Input sample units and axis convention must match the CSV data used for training.",
        "window_size_samples": int(window_size),
        "recommended_stride_samples": int(stride),
        "all_engineered_features": ALL_FEATURE_NAMES,
        "statistic_order_per_axis": STATISTICS,
        "selected_feature_indices_in_all_features": selected_indices,
        "selected_features": selected_names,
        "rfe_ranking": rfe_ranking,
        "rfe_estimator": "DecisionTreeClassifier feature_importances_",
        "classes": class_names,
        "tree_depth": int(model.get_depth()),
        "leaf_count": int(model.get_n_leaves()),
        "node_count": int(tree.node_count),
        "criterion": args.criterion,
        "max_depth": args.max_depth,
        "min_samples_leaf": args.min_samples_leaf,
        "min_samples_split": args.min_samples_split,
        "nodes": nodes,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def generate_c_from_json(json_path: Path, out_prefix: Path) -> tuple[Path, Path]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if payload.get("format") != "imu_feature_rfe_decision_tree_v1":
        raise ValueError("This JSON is not a compatible feature-RFE decision tree from this script.")
    raw_channels = payload["raw_channels"]
    stats = payload["statistic_order_per_axis"]
    all_names = payload["all_engineered_features"]
    selected_names = payload["selected_features"]
    selected_indices = payload["selected_feature_indices_in_all_features"]
    nodes = payload["nodes"]
    classes = payload["classes"]
    window_size = int(payload["window_size_samples"])
    if window_size < 2 or len(selected_names) != len(selected_indices):
        raise ValueError("The JSON feature/window metadata is invalid.")

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    c_path = out_prefix.with_suffix(".c")
    h_path = out_prefix.with_suffix(".h")
    guard = re.sub(r"[^A-Za-z0-9_]", "_", out_prefix.name.upper()) + "_H"
    enum_names = ["IMU_FEATURE_CLASS_" + c_identifier(label) for label in classes]
    enum_items = [f"    {name} = {i}" for i, name in enumerate(enum_names)]
    enum_items.append("    IMU_FEATURE_CLASS_UNKNOWN = 255")
    enum_text = ",\n".join(enum_items)
    feature_comments = "\n".join(f" *   {i}: {name}" for i, name in enumerate(selected_names))
    header = f'''/* Auto-generated from {json_path.name}; do not edit by hand.
 * Window length: {window_size} samples.
 * Raw input channel order: {", ".join(raw_channels)}.
 * Raw input units MUST match training CSV (check units in CSV headers).
 * Selected engineered features, in tree input order:
{feature_comments}
 */
#ifndef {guard}
#define {guard}
#include <stdint.h>
#define IMU_FEATURE_TREE_WINDOW_SIZE ((uint32_t){window_size}u)
#define IMU_FEATURE_TREE_RAW_CHANNELS ((uint32_t){len(raw_channels)}u)
#define IMU_FEATURE_TREE_FEATURE_COUNT ((uint32_t){len(selected_names)}u)
#define IMU_FEATURE_TREE_NODE_COUNT ((uint32_t){len(nodes)}u)

typedef enum {{
{enum_text}
}} imu_feature_tree_class_t;

/* Call with a complete window [sample][channel], using the documented order/units. */
imu_feature_tree_class_t imu_feature_tree_predict_window(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS]);
#endif /* {guard} */
'''
    h_path.write_text(header, encoding="utf-8")

    node_rows = []
    for node in nodes:
        fi = node["feature_index"]
        if fi is None:
            fi_text, threshold, left, right = -1, "0.0f", -1, -1
        else:
            fi_text = int(fi)
            threshold = c_float(node["threshold"])
            left = int(node["left_child"])
            right = int(node["right_child"])
        predicted = int(node["predicted_class_index"])
        node_rows.append(f"    {{{fi_text}, {threshold}, {left}, {right}, {predicted}u}},")

    # C feature extractor: this exact order/formula mirrors extract_window_features().
    # STATISTICS index: mean,std,min,max,range,rms,median,iqr,mean_abs,zcr,waveform_length
    n = window_size
    compute = f'''static void imu_compute_all_features(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS],
    float out[{len(all_names)}])
{{
    uint32_t axis;
    for (axis = 0u; axis < IMU_FEATURE_TREE_RAW_CHANNELS; ++axis) {{
        float values[IMU_FEATURE_TREE_WINDOW_SIZE];
        float sorted[IMU_FEATURE_TREE_WINDOW_SIZE];
        float sum = 0.0f, sum_sq = 0.0f, sum_abs = 0.0f, wave_len = 0.0f;
        float mean, variance = 0.0f, minimum, maximum, rms, median, q1, q3;
        uint32_t i, j, crossings = 0u;
        int last_sign = 0;
        for (i = 0u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {{
            values[i] = samples[i][axis];
            sorted[i] = values[i];
            sum += values[i];
            sum_sq += values[i] * values[i];
            sum_abs += fabsf(values[i]);
            if (i == 0u) {{ minimum = values[i]; maximum = values[i]; }}
            else {{
                if (values[i] < minimum) minimum = values[i];
                if (values[i] > maximum) maximum = values[i];
                wave_len += fabsf(values[i] - values[i - 1u]);
            }}
        }}
        mean = sum / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
        for (i = 0u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {{
            float delta = values[i] - mean;
            variance += delta * delta;
            if (delta > 0.0f) {{ if (last_sign < 0) ++crossings; last_sign = 1; }}
            else if (delta < 0.0f) {{ if (last_sign > 0) ++crossings; last_sign = -1; }}
        }}
        variance /= (float)IMU_FEATURE_TREE_WINDOW_SIZE;
        rms = sqrtf(sum_sq / (float)IMU_FEATURE_TREE_WINDOW_SIZE);
        /* Insertion sort permits deterministic median and quartile computation. */
        for (i = 1u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {{
            float key = sorted[i];
            j = i;
            while (j > 0u && sorted[j - 1u] > key) {{
                sorted[j] = sorted[j - 1u];
                --j;
            }}
            sorted[j] = key;
        }}
        {{
            float pos = ((float)IMU_FEATURE_TREE_WINDOW_SIZE - 1.0f) * 0.5f;
            uint32_t lo = (uint32_t)pos;
            uint32_t hi = lo + 1u;
            median = (lo == hi) ? sorted[lo] : sorted[lo] + (pos - (float)lo) * (sorted[hi] - sorted[lo]);
        }}
        {{
            float pos1 = ((float)IMU_FEATURE_TREE_WINDOW_SIZE - 1.0f) * 0.25f;
            uint32_t lo1 = (uint32_t)pos1, hi1 = lo1 + 1u;
            q1 = sorted[lo1] + (pos1 - (float)lo1) * (sorted[hi1] - sorted[lo1]);
            float pos3 = ((float)IMU_FEATURE_TREE_WINDOW_SIZE - 1.0f) * 0.75f;
            uint32_t lo3 = (uint32_t)pos3, hi3 = lo3 + 1u;
            q3 = sorted[lo3] + (pos3 - (float)lo3) * (sorted[hi3] - sorted[lo3]);
        }}
        {{
            uint32_t base = axis * {len(stats)}u;
            out[base + 0u] = mean;
            out[base + 1u] = sqrtf(variance);
            out[base + 2u] = minimum;
            out[base + 3u] = maximum;
            out[base + 4u] = maximum - minimum;
            out[base + 5u] = rms;
            out[base + 6u] = median;
            out[base + 7u] = q3 - q1;
            out[base + 8u] = sum_abs / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
            out[base + 9u] = (float)crossings / (float)(IMU_FEATURE_TREE_WINDOW_SIZE - 1u);
            out[base + 10u] = wave_len;
        }}
    }}
}}
'''
    source = f'''/* Auto-generated from {json_path.name}; do not edit by hand. */
#include "{h_path.name}"
#include <math.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {{ int16_t feature_index; float threshold; int32_t left; int32_t right; uint8_t predicted_class; }} imu_feature_tree_node_t;
static const imu_feature_tree_node_t imu_tree_nodes[{len(nodes)}] = {{
{chr(10).join(node_rows)}
}};
{compute}

imu_feature_tree_class_t imu_feature_tree_predict_window(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS])
{{
    float all_features[{len(all_names)}];
    float selected_features[{len(selected_indices)}];
    int32_t node_index = 0;
    uint32_t steps;
    if (samples == NULL) return IMU_FEATURE_CLASS_UNKNOWN;
    imu_compute_all_features(samples, all_features);
'''
    for selected_pos, all_idx in enumerate(selected_indices):
        source += f"    selected_features[{selected_pos}u] = all_features[{int(all_idx)}u]; /* {selected_names[selected_pos]} */\n"
    source += '''    for (steps = 0u; steps < IMU_FEATURE_TREE_NODE_COUNT; ++steps) {
        const imu_feature_tree_node_t *node;
        if (node_index < 0 || (uint32_t)node_index >= IMU_FEATURE_TREE_NODE_COUNT) return IMU_FEATURE_CLASS_UNKNOWN;
        node = &imu_tree_nodes[node_index];
        if (node->feature_index < 0) return (imu_feature_tree_class_t)node->predicted_class;
        if ((uint32_t)node->feature_index >= IMU_FEATURE_TREE_FEATURE_COUNT) return IMU_FEATURE_CLASS_UNKNOWN;
        if (selected_features[node->feature_index] <= node->threshold) node_index = node->left;
        else node_index = node->right;
    }
    return IMU_FEATURE_CLASS_UNKNOWN;
}
'''
    c_path.write_text(source, encoding="utf-8")
    return c_path, h_path


def evaluate(model, x: pd.DataFrame, y: pd.Series, class_names: list[str]):
    predictions = model.predict(x.to_numpy(dtype=np.float64))
    return accuracy_score(y, predictions), predictions, classification_report(
        y, predictions, labels=class_names, target_names=class_names,
        output_dict=True, zero_division=0,
    )


def run_training(args) -> None:
    if not (0 < args.train_fraction < 1 and 0 < args.validation_fraction < 1 and
            args.train_fraction + args.validation_fraction < 1):
        raise ValueError("Train and validation fractions must be > 0 and sum to less than 1.")
    if args.window_size < 2 or args.stride < 1:
        raise ValueError("--window-size must be >= 2 and --stride >= 1.")
    if not 1 <= args.n_features <= len(ALL_FEATURE_NAMES):
        raise ValueError(f"--n-features must be from 1 to {len(ALL_FEATURE_NAMES)}.")
    if args.min_samples_leaf < 1 or args.min_samples_split < 2:
        raise ValueError("--min-samples-leaf must be >= 1 and --min-samples-split >= 2.")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    labelled_paths = []
    for label, paths in [("Horizontal", args.horizontal), ("Static", args.static), ("Vertical", args.vertical)]:
        if not paths:
            raise ValueError(f"Provide at least one --{label.lower()} CSV file.")
        for path in paths:
            labelled_paths.append((label, Path(path)))
    recordings = [(label, load_recording(path, label, args.feature_columns)) for label, path in labelled_paths]

    raw_pieces, actual_mode = assign_splits(recordings, args.split_mode, args.train_fraction,
                                            args.validation_fraction, args.random_state)
    window_pieces: dict[str, list[pd.DataFrame]] = {"train": [], "validation": [], "test": []}
    for split_name, frames in raw_pieces.items():
        for frame in frames:
            windows = windows_from_segment(frame, args.window_size, args.stride)
            if not windows.empty:
                windows["split"] = split_name
                window_pieces[split_name].append(windows)
    combined = {}
    for split_name, frames in window_pieces.items():
        if not frames:
            raise ValueError(f"No windows were generated for {split_name}. Check recording length vs --window-size/--stride.")
        combined[split_name] = pd.concat(frames, ignore_index=True)
        present = set(combined[split_name]["label"].unique())
        missing = set(CLASSES) - present
        if missing:
            raise ValueError(f"The {split_name} split is missing classes {sorted(missing)}. Record more data or adjust window/split settings.")

    train_df, val_df, test_df = combined["train"], combined["validation"], combined["test"]
    x_train_all = train_df[ALL_FEATURE_NAMES]
    y_train = train_df["label"].astype(str)
    base_tree = DecisionTreeClassifier(
        criterion=args.criterion,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        min_samples_split=args.min_samples_split,
        random_state=args.random_state,
    )
    selector = RFE(estimator=base_tree, n_features_to_select=args.n_features, step=args.rfe_step)
    selector.fit(x_train_all, y_train)
    selected_indices = np.flatnonzero(selector.support_).astype(int).tolist()
    selected_names = [ALL_FEATURE_NAMES[i] for i in selected_indices]
    model = selector.estimator_  # final DecisionTreeClassifier already fit by RFE
    class_names = [str(c) for c in model.classes_]

    print("\n=== Feature engineering and RFE ===")
    print(f"Window size: {args.window_size} samples; stride: {args.stride} samples")
    print(f"Candidate engineered features: {len(ALL_FEATURE_NAMES)}")
    print(f"RFE-selected features: {len(selected_names)}")
    for name in selected_names:
        print(f"  - {name}")
    print(f"Split strategy: {actual_mode}")
    print("\n=== Dataset split (window counts) ===")
    for name, frame in [("Train", train_df), ("Validation", val_df), ("Test", test_df)]:
        print(f"{name:10s}: {len(frame):,} windows; class counts={frame['label'].value_counts().to_dict()}")

    # Apply the exact RFE-selected feature order to all splits.
    selected = {name: frame[selected_names] for name, frame in combined.items()}
    metrics = []
    all_predictions = []
    summary = {}
    for split_name in ["train", "validation", "test"]:
        frame = combined[split_name]
        acc, pred, report = evaluate(model, selected[split_name], frame["label"].astype(str), class_names)
        summary[f"{split_name}_accuracy"] = float(acc)
        print(f"\n{split_name.upper()} (accuracy={acc:.4f})")
        print(classification_report(frame["label"].astype(str), pred, labels=class_names,
                                    target_names=class_names, zero_division=0))
        for label in class_names:
            row = report[label]
            metrics.append({"split": split_name, "class": label, "precision": row["precision"],
                            "recall": row["recall"], "f1_score": row["f1-score"], "support": row["support"],
                            "accuracy_overall": float(acc)})
        pred_frame = frame[["label", "source_file", "window_start_row", "window_end_row"]].copy()
        pred_frame["predicted_label"] = pred
        pred_frame["correct"] = pred_frame["label"].astype(str) == pred_frame["predicted_label"].astype(str)
        pred_frame["split"] = split_name
        all_predictions.append(pred_frame)

    pd.DataFrame(metrics).to_csv(out_dir / "metrics_by_class.csv", index=False)
    prediction_frame = pd.concat(all_predictions, ignore_index=True)
    prediction_frame.to_csv(out_dir / "predictions_all_splits.csv", index=False)
    prediction_frame[(prediction_frame["split"] == "test") & (~prediction_frame["correct"])].to_csv(
        out_dir / "test_misclassifications.csv", index=False)

    ranking = pd.DataFrame({"feature": ALL_FEATURE_NAMES, "rfe_ranking": selector.ranking_,
                             "selected_by_rfe": selector.support_})
    importance_by_selected = dict(zip(selected_names, model.feature_importances_))
    ranking["final_tree_importance"] = ranking["feature"].map(importance_by_selected).fillna(0.0)
    ranking.sort_values(["selected_by_rfe", "rfe_ranking", "final_tree_importance"],
                        ascending=[False, True, False]).to_csv(out_dir / "rfe_feature_ranking.csv", index=False)
    (out_dir / "decision_tree_features_rfe.txt").write_text(
        export_text(model, feature_names=selected_names, decimals=6), encoding="utf-8")

    # Test confusion matrix.
    test_pred = model.predict(selected["test"].to_numpy(dtype=np.float64))
    cm = confusion_matrix(test_df["label"].astype(str), test_pred, labels=class_names)
    pd.DataFrame(cm, index=[f"Actual {c}" for c in class_names],
                 columns=[f"Predicted {c}" for c in class_names]).to_csv(out_dir / "confusion_matrix_test.csv")
    fig, ax = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay(cm, display_labels=class_names).plot(ax=ax, values_format="d", colorbar=False)
    ax.set_title("Feature-RFE IMU decision tree — test confusion matrix")
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_matrix_test.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    plot_tree(model, feature_names=selected_names, class_names=class_names, filled=False,
              rounded=True, max_depth=args.plot_depth, fontsize=7, ax=ax)
    ax.set_title(f"Decision tree (display limited to depth {args.plot_depth}; full tree in JSON)")
    fig.tight_layout()
    fig.savefig(out_dir / "tree_structure.png", dpi=160)
    plt.close(fig)

    rfe_ranking = {name: int(rank) for name, rank in zip(ALL_FEATURE_NAMES, selector.ranking_)}
    json_path = out_dir / "decision_tree_features_rfe.json"
    export_tree_json(model, selected_names, selected_indices, rfe_ranking, json_path,
                     args.window_size, args.stride, args)
    c_path, h_path = generate_c_from_json(json_path, out_dir / "decision_tree_features_rfe")

    # Estimate software-model prediction latency only; it is not MCU timing.
    test_one = selected["test"].iloc[[0]]
    elapsed = []
    for _ in range(15):
        start = time.perf_counter_ns()
        for _ in range(100):
            model.predict(test_one.to_numpy(dtype=np.float64))
        elapsed.append((time.perf_counter_ns() - start) / 100 / 1000.0)
    latency_us = float(np.median(elapsed))
    summary.update({
        "model_type": "DecisionTreeClassifier on windowed IMU engineered features selected by RFE",
        "raw_channels": RAW_CHANNELS,
        "candidate_feature_count": len(ALL_FEATURE_NAMES),
        "selected_feature_count": len(selected_names),
        "selected_features": selected_names,
        "selected_feature_indices_in_all_features": selected_indices,
        "window_size_samples": args.window_size,
        "stride_samples": args.stride,
        "split_mode": actual_mode,
        "train_windows": len(train_df), "validation_windows": len(val_df), "test_windows": len(test_df),
        "criterion": args.criterion, "max_depth_setting": args.max_depth,
        "min_samples_leaf": args.min_samples_leaf, "min_samples_split": args.min_samples_split,
        "tree_depth": int(model.get_depth()), "leaf_count": int(model.get_n_leaves()),
        "node_count": int(model.tree_.node_count),
        "json_size_bytes": json_path.stat().st_size,
        "c_source_and_header_size_bytes": c_path.stat().st_size + h_path.stat().st_size,
        "python_sklearn_predict_median_us_per_window": latency_us,
        "latency_note": "This only times sklearn classification of a precomputed feature row; it is not STM32 timing and excludes feature calculation.",
        "evaluation_note": ("Recording sessions were held out by file." if actual_mode == "sessions" else
                            "Chronological portions of each recording were used. These results do not test generalization to independently recorded sessions; collect separate sessions per class for stronger evaluation."),
        "embedded_note": "Generated C consumes a complete window of 42 (or configured size) raw samples in order ACC_X, ACC_Y, ACC_Z, GYR_X, GYR_Y, GYR_Z and calculates selected features internally. Convert hardware readings to the training CSV units before calling it.",
    })
    (out_dir / "model_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== RFE and model outputs ===")
    print(f"Selected features: {len(selected_names)} / {len(ALL_FEATURE_NAMES)}")
    print(f"Tree depth: {model.get_depth()}; leaves: {model.get_n_leaves()}; nodes: {model.tree_.node_count}")
    print(f"JSON size: {json_path.stat().st_size / 1024:.2f} KB")
    print(f"Python sklearn prediction estimate: {latency_us:.2f} us/window (precomputed features; not MCU timing)")
    print(f"All files saved to: {out_dir.resolve()}")
    print(f"RFE ranking: {out_dir / 'rfe_feature_ranking.csv'}")
    print(f"Tree JSON: {json_path}")
    print(f"C source: {c_path}")
    print(f"C header: {h_path}")
    if actual_mode == "chronological":
        print("\nNOTE: With one recording per class, chronological splits are not independent recording sessions.")


def build_parser():
    parser = argparse.ArgumentParser(description="Train a feature-engineered IMU tree with Recursive Feature Elimination and export embedded C.")
    parser.add_argument("--horizontal", nargs="+", help="One or more Horizontal class CSV files")
    parser.add_argument("--static", nargs="+", help="One or more Static class CSV files")
    parser.add_argument("--vertical", nargs="+", help="One or more Vertical class CSV files")
    parser.add_argument("--feature-columns", nargs=6, metavar=("ACC_X", "ACC_Y", "ACC_Z", "GYR_X", "GYR_Y", "GYR_Z"),
                        help="Exact raw CSV column names, in that order, if automatic detection fails")
    parser.add_argument("--output-dir", default="feature_rfe_results", help="Directory for metrics, JSON, and generated C")
    parser.add_argument("--window-size", type=int, default=42, help="Samples per feature window (default 42)")
    parser.add_argument("--stride", type=int, default=21, help="Step between windows (default 21; 50%% overlap)")
    parser.add_argument("--n-features", type=int, default=12, help="How many of the 66 engineered features RFE should keep (default 12)")
    parser.add_argument("--rfe-step", type=int, default=1, help="Number of features removed per RFE iteration (default 1)")
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--split-mode", choices=["auto", "chronological", "sessions"], default="auto",
                        help="auto uses whole recording sessions only when >=3 CSV files per class; otherwise chronological")
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--min-samples-leaf", type=int, default=1)
    parser.add_argument("--min-samples-split", type=int, default=2)
    parser.add_argument("--criterion", choices=["gini", "entropy", "log_loss"], default="gini")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--plot-depth", type=int, default=3)
    parser.add_argument("--convert-json", type=Path, help="Convert a compatible decision_tree_features_rfe.json to C/H only")
    parser.add_argument("--c-out-prefix", type=Path, help="Output prefix for C/H when using --convert-json")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.convert_json:
            if not args.convert_json.is_file():
                raise FileNotFoundError(f"JSON file not found: {args.convert_json}")
            prefix = args.c_out_prefix or args.convert_json.with_suffix("")
            c_path, h_path = generate_c_from_json(args.convert_json, prefix)
            print(f"Generated C source: {c_path}")
            print(f"Generated C header: {h_path}")
            return 0
        if not (args.horizontal and args.static and args.vertical):
            parser.error("Supply --horizontal, --static, and --vertical. Use --convert-json FILE for C-only conversion.")
        run_training(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
