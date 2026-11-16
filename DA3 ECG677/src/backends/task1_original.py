#!/usr/bin/env python3
"""Quaternion feature extraction, ANOVA/RFE reduction, and Float32/Int8 training.

Input CSV: one quaternion sample per row. Required fields:
    label, q0, q1, q2, q3
Recommended fields:
    recording_id, timestamp_s

Example:
    python nn_quat_train.py --csv quaternion_data.csv --sample-rate 52

If timestamp_s is present, the sample rate is estimated separately for each
recording. Otherwise --sample-rate must be provided.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.feature_selection import SelectKBest, f_classif, RFE
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

LABEL_ALIASES = ("label", "class", "activity", "motion", "gesture", "category")
GROUP_ALIASES = ("recordingid", "sessionid", "trialid", "fileid", "recording", "session", "trial")
TIME_ALIASES = ("timestamps", "times", "timestampms", "timems", "timestamp", "time", "elapsed_s", "elapsed_ms")


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def find_column(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    lookup = {norm_name(c): c for c in columns}
    for candidate in candidates:
        if norm_name(candidate) in lookup:
            return lookup[norm_name(candidate)]
    return None


def resolve_quaternion_columns(columns: Sequence[str], requested: Optional[Sequence[str]]) -> Tuple[List[str], List[str]]:
    lookup = {norm_name(c): c for c in columns}
    if requested:
        if len(requested) != 4:
            raise ValueError("--quat-cols must contain exactly four column names in order.")
        try:
            resolved = [lookup[norm_name(c)] for c in requested]
        except KeyError as exc:
            raise ValueError(f"Quaternion column {exc.args[0]!r} not found. CSV columns: {list(columns)}") from exc
        return resolved, [f"q{i}" for i in range(4)]

    aliases = [
        ("q0", "qw", "quatw", "quaternionw", "rotationw"),
        ("q1", "qx", "quatx", "quaternionx", "rotationx"),
        ("q2", "qy", "quaty", "quaterniony", "rotationy"),
        ("q3", "qz", "quatz", "quaternionz", "rotationz"),
    ]
    if all(any(a in lookup for a in group) for group in aliases):
        resolved = [lookup[next(a for a in group if a in lookup)] for group in aliases]
        tags = [f"q{i}" for i in range(4)] if all(norm_name(c) in {"q0", "q1", "q2", "q3"} for c in resolved) else ["qw", "qx", "qy", "qz"]
        return resolved, tags
    raise ValueError("Could not identify quaternion columns. Use --quat-cols COL1 COL2 COL3 COL4 in the exact printed order.")


def load_data(
    csv_paths: Sequence[Path],
    label_column: Optional[str],
    quat_columns: Optional[Sequence[str]],
    group_column: Optional[str],
    timestamp_column: Optional[str],
    timestamp_unit: str,
    sample_rate: Optional[float],
) -> Tuple[pd.DataFrame, List[str], List[str], str, Optional[str], Optional[str]]:
    if not csv_paths:
        raise ValueError("Provide at least one input CSV file with --csv.")

    frames = []
    for csv_path in csv_paths:
        if not csv_path.exists():
            raise FileNotFoundError(f"Input CSV does not exist: {csv_path}")
        frame = pd.read_csv(csv_path)
        if frame.empty:
            raise ValueError(f"Input CSV is empty: {csv_path}")

        file_label_col = label_column or find_column(frame.columns, LABEL_ALIASES)
        if file_label_col is None:
            inferred_label = re.sub(r"[_-]?\d+$", "", csv_path.stem).strip("_-")
            if not inferred_label:
                raise ValueError(
                    f"Cannot infer a label from filename {csv_path.name!r}. "
                    "Use filenames such as REST_01.csv, PITCH_01.csv, or add a label column."
                )
            file_label_col = "label"
            frame[file_label_col] = inferred_label

        if group_column and group_column.lower() != "none":
            if group_column not in frame.columns:
                raise ValueError(f"Group column {group_column!r} not found in {csv_path.name!r}.")
        elif not find_column(frame.columns, GROUP_ALIASES):
            frame["recording_id"] = csv_path.stem

        frames.append(frame)

    raw = pd.concat(frames, ignore_index=True, sort=False)
    label_col = label_column or find_column(raw.columns, LABEL_ALIASES)
    if not label_col or label_col not in raw.columns:
        raise ValueError("A label column is required. Add a 'label' column or use filenames such as REST_01.csv.")
    quat_cols, tags = resolve_quaternion_columns(raw.columns, quat_columns)

    if group_column and group_column.lower() == "none":
        group_col = None
    elif group_column:
        if group_column not in raw.columns:
            raise ValueError(f"Group column {group_column!r} not found.")
        group_col = group_column
    else:
        group_col = find_column(raw.columns, GROUP_ALIASES)

    if timestamp_column and timestamp_column.lower() == "none":
        time_col = None
    elif timestamp_column:
        if timestamp_column not in raw.columns:
            raise ValueError(f"Timestamp column {timestamp_column!r} not found.")
        time_col = timestamp_column
    else:
        time_col = find_column(raw.columns, TIME_ALIASES)

    keep = [label_col] + quat_cols
    if group_col:
        keep.append(group_col)
    if time_col:
        keep.append(time_col)
    data = raw[keep].copy()
    data["_row_order"] = np.arange(len(data), dtype=np.int64)
    data["_label"] = data[label_col].astype(str).str.strip()
    data = data[~data["_label"].str.lower().isin(["", "nan", "none", "null"])].copy()

    for col in quat_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    before = len(data)
    data = data.dropna(subset=quat_cols).copy()
    if len(data) < before:
        print(f"[INFO] Dropped {before - len(data)} rows with invalid quaternion values.")

    if group_col:
        data["_group"] = data[group_col].astype(str).str.strip()
        data.loc[data["_group"].isin(["", "nan", "None"]), "_group"] = "missing_recording_id"
    else:
        run_change = data["_label"].ne(data["_label"].shift()).fillna(True)
        data["_group"] = [f"run_{int(v):04d}" for v in run_change.cumsum()]
        warnings.warn("No recording_id column found. Each contiguous label run is treated as a separate recording. Add recording_id for reliable independent train/validation/test splits.")
    data["_group"] = data["_group"].astype(str) + "__" + data["_label"].astype(str)

    if time_col:
        data["_time_s"] = pd.to_numeric(data[time_col], errors="coerce")
        unit = timestamp_unit
        if unit == "auto":
            unit = "ms" if "ms" in norm_name(time_col) else "s"
        if unit == "ms":
            data["_time_s"] = data["_time_s"] / 1000.0
        if data["_time_s"].isna().any():
            raise ValueError(f"Timestamp column {time_col!r} contains non-numeric or missing values.")
    elif sample_rate is None or sample_rate <= 0:
        raise ValueError("Frequency-domain features need timing information. Add timestamp_s to the CSV, or pass --sample-rate with your actual quaternion output rate in Hz.")

    q = data[quat_cols].to_numpy(dtype=np.float64)
    norms = np.linalg.norm(q, axis=1)
    valid = np.isfinite(norms) & (norms > 1e-12)
    if not np.all(valid):
        data = data.loc[valid].copy()
        q = q[valid]
        norms = norms[valid]
    if len(data) == 0:
        raise ValueError("No valid non-zero quaternion samples remain.")
    q = q / norms[:, None]
    data.loc[:, quat_cols] = q

    data = data.sort_values("_row_order").reset_index(drop=True)
    data["_sample_rate_hz"] = float(sample_rate) if sample_rate else np.nan
    if time_col:
        rates = {}
        for group_id, grp in data.groupby("_group", sort=False):
            times = grp.sort_values("_row_order")["_time_s"].to_numpy(dtype=np.float64)
            dt = np.diff(times)
            dt = dt[np.isfinite(dt) & (dt > 0)]
            if len(dt) == 0:
                raise ValueError(f"Could not calculate sample rate for recording {group_id!r}; timestamps must increase.")
            rates[group_id] = 1.0 / float(np.median(dt))
        data["_sample_rate_hz"] = data["_group"].map(rates).astype(float)
        print("[INFO] Estimated sample rates (Hz): " + ", ".join(f"{k}: {v:.2f}" for k, v in rates.items()))
    else:
        print(f"[INFO] Using supplied sample rate: {sample_rate:g} Hz")

    for _, idx in data.groupby("_group", sort=False).groups.items():
        seq = data.loc[idx, quat_cols].to_numpy(dtype=np.float64)
        for i in range(1, len(seq)):
            if np.dot(seq[i - 1], seq[i]) < 0:
                seq[i] *= -1.0
        data.loc[idx, quat_cols] = seq

    return data, quat_cols, tags, label_col, group_col, time_col


def frequency_features(values: np.ndarray, fs: float, prefix: str) -> Dict[str, float]:
    x = np.asarray(values, dtype=np.float64)
    n = len(x)
    if n < 4 or not np.isfinite(fs) or fs <= 0:
        return {f"{prefix}_{k}": 0.0 for k in ("dominant_hz", "centroid_hz", "bandwidth_hz", "entropy", "power", "peak_amplitude", "rolloff85_hz")}

    centered = x - np.mean(x)
    window = np.hanning(n)
    spectrum = np.fft.rfft(centered * window)
    magnitude = np.abs(spectrum)
    power = magnitude ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    if len(power) > 1:
        power = power[1:]
        magnitude = magnitude[1:]
        freqs = freqs[1:]
    total_power = float(np.sum(power))
    if not np.isfinite(total_power) or total_power <= 1e-20 or len(power) == 0:
        vals = [0.0] * 7
    else:
        probs = power / total_power
        dominant = float(freqs[int(np.argmax(power))])
        centroid = float(np.sum(freqs * probs))
        bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * probs)))
        nz = probs[probs > 0]
        entropy = float(-np.sum(nz * np.log2(nz)) / math.log2(len(probs))) if len(probs) > 1 else 0.0
        cumulative = np.cumsum(probs)
        roll_idx = min(int(np.searchsorted(cumulative, 0.85)), len(freqs) - 1)
        rolloff = float(freqs[roll_idx])
        peak_amplitude = float(np.max(magnitude))
        vals = [dominant, centroid, bandwidth, entropy, total_power, peak_amplitude, rolloff]
    keys = ("dominant_hz", "centroid_hz", "bandwidth_hz", "entropy", "power", "peak_amplitude", "rolloff85_hz")
    return {f"{prefix}_{k}": float(v) for k, v in zip(keys, vals)}


def quaternion_features(q: np.ndarray, tags: Sequence[str], fs: float) -> Dict[str, float]:
    features: Dict[str, float] = {}
    n = len(q)
    x_axis = np.linspace(-1.0, 1.0, n) if n > 1 else np.array([0.0])

    for j, tag in enumerate(tags):
        v = q[:, j]
        mean = float(np.mean(v))
        std = float(np.std(v))
        centered = v - mean
        features[f"{tag}_mean"] = mean
        features[f"{tag}_std"] = std
        features[f"{tag}_min"] = float(np.min(v))
        features[f"{tag}_max"] = float(np.max(v))
        features[f"{tag}_range"] = float(np.ptp(v))
        features[f"{tag}_median"] = float(np.median(v))
        features[f"{tag}_iqr"] = float(np.percentile(v, 75) - np.percentile(v, 25))
        features[f"{tag}_rms"] = float(np.sqrt(np.mean(v ** 2)))
        features[f"{tag}_mean_abs_diff"] = float(np.mean(np.abs(np.diff(v)))) if n > 1 else 0.0
        features[f"{tag}_slope"] = float(np.polyfit(x_axis, v, 1)[0]) if n > 1 else 0.0
        if std > 1e-12:
            z = centered / std
            features[f"{tag}_skew"] = float(np.mean(z ** 3))
            features[f"{tag}_kurtosis"] = float(np.mean(z ** 4) - 3.0)
        else:
            features[f"{tag}_skew"] = 0.0
            features[f"{tag}_kurtosis"] = 0.0
        features.update(frequency_features(v, fs, f"{tag}_fft"))

    for a, b in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)):
        va, vb = q[:, a], q[:, b]
        corr = float(np.corrcoef(va, vb)[0, 1]) if n > 1 and np.std(va) > 1e-12 and np.std(vb) > 1e-12 else 0.0
        features[f"corr_{tags[a]}_{tags[b]}"] = corr

    if n > 1:
        dots = np.clip(np.abs(np.sum(q[:-1] * q[1:], axis=1)), 0.0, 1.0)
        angle = 2.0 * np.arccos(dots)
        dt = 1.0 / fs
        rotation_rate = angle / dt
    else:
        angle = np.array([0.0])
        rotation_rate = np.array([0.0])
    features["rotation_angle_mean_rad"] = float(np.mean(angle))
    features["rotation_angle_std_rad"] = float(np.std(angle))
    features["rotation_angle_max_rad"] = float(np.max(angle))
    features["rotation_rate_mean_rad_s"] = float(np.mean(rotation_rate))
    features["rotation_rate_std_rad_s"] = float(np.std(rotation_rate))
    features["rotation_rate_max_rad_s"] = float(np.max(rotation_rate))
    features.update(frequency_features(rotation_rate, fs, "rotation_rate_fft"))
    return features


def build_windows(data: pd.DataFrame, quat_cols: Sequence[str], tags: Sequence[str], window_size: int, step_size: int) -> Tuple[pd.DataFrame, List[str]]:
    rows: List[Dict[str, object]] = []
    for group_id, grp in data.groupby("_group", sort=False):
        grp = grp.sort_values("_row_order")
        q = grp[list(quat_cols)].to_numpy(dtype=np.float64)
        label = str(grp["_label"].iloc[0])
        fs = float(grp["_sample_rate_hz"].median())
        if len(q) <= window_size:
            starts = [0]
        else:
            starts = list(range(0, len(q) - window_size + 1, step_size))
            final_start = len(q) - window_size
            if starts[-1] != final_start:
                starts.append(final_start)
        for window_index, start in enumerate(starts):
            segment = q[start:start + window_size]
            rec: Dict[str, object] = {
                "recording_id": str(group_id),
                "label": label,
                "window_index": int(window_index),
                "sample_start": int(start),
                "sample_stop": int(start + len(segment)),
                "samples_in_window": int(len(segment)),
                "sample_rate_hz": fs,
            }
            rec.update(quaternion_features(segment, tags, fs))
            rows.append(rec)
    if not rows:
        raise ValueError("No feature windows were produced.")
    out = pd.DataFrame(rows)
    metadata = {"recording_id", "label", "window_index", "sample_start", "sample_stop", "samples_in_window", "sample_rate_hz"}
    feature_names = [c for c in out.columns if c not in metadata]
    print(f"[INFO] Created {len(out)} windows from {data['_group'].nunique()} independent recordings.")
    return out, feature_names


def save_signal_outputs(data: pd.DataFrame, quat_cols: Sequence[str], tags: Sequence[str], out_dir: Path) -> None:
    group_id = data["_group"].iloc[0]
    grp = data[data["_group"] == group_id].sort_values("_row_order")
    q = grp[list(quat_cols)].to_numpy(dtype=np.float64)
    fs = float(grp["_sample_rate_hz"].median())

    fig, axes = plt.subplots(4, 1, figsize=(11, 8), sharex=True)
    t = np.arange(len(q)) / fs
    for j, ax in enumerate(axes):
        ax.plot(t, q[:, j], linewidth=1.0)
        ax.set_ylabel(tags[j])
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("Time (seconds)")
    fig.suptitle(f"Quaternion signals — {grp['_label'].iloc[0]} / {group_id}")
    fig.tight_layout()
    fig.savefig(out_dir / "quaternion_signals.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(4, 1, figsize=(11, 8), sharex=True)
    for j, ax in enumerate(axes):
        v = q[:, j] - np.mean(q[:, j])
        win = np.hanning(len(v))
        mag = np.abs(np.fft.rfft(v * win))
        freq = np.fft.rfftfreq(len(v), d=1.0 / fs)
        ax.plot(freq, mag, linewidth=1.0)
        ax.set_ylabel(tags[j])
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("Frequency (Hz)")
    fig.suptitle(f"Quaternion magnitude spectra — {grp['_label'].iloc[0]} / {group_id}")
    fig.tight_layout()
    fig.savefig(out_dir / "quaternion_spectrum.png", dpi=160)
    plt.close(fig)


def save_summary(data: pd.DataFrame, quat_cols: Sequence[str], tags: Sequence[str], out_dir: Path) -> None:
    rows = []
    for label, grp in data.groupby("_label", sort=True):
        q = grp[list(quat_cols)].to_numpy(dtype=np.float64)
        rec: Dict[str, object] = {"label": label, "sample_count": int(len(q)), "recording_count": int(grp["_group"].nunique())}
        for j, tag in enumerate(tags):
            v = q[:, j]
            rec[f"{tag}_mean"] = float(np.mean(v))
            rec[f"{tag}_std"] = float(np.std(v))
            rec[f"{tag}_min"] = float(np.min(v))
            rec[f"{tag}_max"] = float(np.max(v))
            rec[f"{tag}_range"] = float(np.ptp(v))
        norms = np.linalg.norm(q, axis=1)
        rec["quaternion_norm_mean"] = float(np.mean(norms))
        rec["quaternion_norm_std"] = float(np.std(norms))
        rows.append(rec)
    pd.DataFrame(rows).to_csv(out_dir / "quaternion_feature_summary.csv", index=False)


def split_recordings(y: np.ndarray, groups: np.ndarray, holdout_fraction: float, seed: int, purpose: str) -> Tuple[np.ndarray, np.ndarray]:
    classes = np.unique(y)
    groups_by_class: Dict[int, List[str]] = {int(c): [] for c in classes}
    for group in np.unique(groups):
        gy = np.unique(y[groups == group])
        if len(gy) != 1:
            raise ValueError(f"Recording group {group!r} contains multiple labels. Use a unique recording_id for each labeled trial.")
        groups_by_class[int(gy[0])].append(str(group))
    min_required = 3 if purpose == "test" else 2
    if not all(len(groups_by_class[int(c)]) >= min_required for c in classes):
        warnings.warn(f"Not enough separate recordings per class for a whole-recording {purpose} split. Recommended: at least 5 recordings per class. Falling back to stratified window split; test results may be optimistic.")
        return train_test_split(np.arange(len(y)), test_size=holdout_fraction, random_state=seed, stratify=y)
    rng = np.random.default_rng(seed)
    hold_groups = set()
    for c in classes:
        options = np.asarray(groups_by_class[int(c)], dtype=object)
        count = max(1, int(math.ceil(len(options) * holdout_fraction)))
        max_hold = len(options) - (2 if purpose == "test" else 1)
        count = min(count, max_hold)
        chosen = rng.choice(options, size=count, replace=False)
        hold_groups.update(str(v) for v in np.atleast_1d(chosen))
    mask = np.array([str(g) in hold_groups for g in groups], dtype=bool)
    train_idx = np.flatnonzero(~mask)
    hold_idx = np.flatnonzero(mask)
    if not set(np.unique(y[train_idx])) == set(classes) or not set(np.unique(y[hold_idx])) == set(classes):
        raise ValueError(f"Could not make a class-complete {purpose} split. Record more trials for each label.")
    return train_idx, hold_idx


def select_features(x: np.ndarray, y: np.ndarray, names: Sequence[str], top_k: int, method: str, seed: int):
    k = min(top_k, x.shape[1])
    if method == "anova":
        selector = SelectKBest(score_func=f_classif, k=k)
        selector.fit(x, y)
        scores = np.nan_to_num(selector.scores_, nan=0.0, posinf=0.0, neginf=0.0)
        selected = selector.get_support()
        score_name = "anova_f_score"
    else:
        estimator = ExtraTreesClassifier(n_estimators=120, random_state=seed, class_weight="balanced", n_jobs=-1)
        selector = RFE(estimator=estimator, n_features_to_select=k, step=0.10)
        selector.fit(x, y)
        selected = selector.get_support()
        scores = selector.ranking_.astype(float)
        score_name = "rfe_ranking_lower_is_better"
    selected_names = [n for n, keep in zip(names, selected) if keep]
    table = pd.DataFrame({"feature": list(names), score_name: scores, "selected": selected})
    table = table.sort_values(score_name, ascending=(method == "rfe"), kind="stable")
    return selected, selected_names, table


def build_raw_model(tf, trained, scaler: StandardScaler, input_count: int, class_count: int):
    dense = [layer for layer in trained.layers if isinstance(layer, tf.keras.layers.Dense)]
    if len(dense) != 3:
        raise RuntimeError("Unexpected neural-network topology.")
    model = tf.keras.Sequential([
        tf.keras.Input(shape=(input_count,), dtype=tf.float32),
        tf.keras.layers.Dense(24, activation="relu", name="dense_1"),
        tf.keras.layers.Dense(12, activation="relu", name="dense_2"),
        tf.keras.layers.Dense(class_count, activation="softmax", name="class_output"),
    ], name="quaternion_classifier_raw_features")
    w, b = dense[0].get_weights()
    scale = np.asarray(scaler.scale_, dtype=np.float32)
    mean = np.asarray(scaler.mean_, dtype=np.float32)
    model.layers[0].set_weights([(w / scale[:, None]).astype(np.float32), (b - np.matmul(mean / scale, w)).astype(np.float32)])
    model.layers[1].set_weights(dense[1].get_weights())
    model.layers[2].set_weights(dense[2].get_weights())
    return model


def metrics(y_true: np.ndarray, y_pred: np.ndarray, class_count: int) -> Dict[str, float]:
    pw, rw, fw, _ = precision_recall_fscore_support(y_true, y_pred, labels=np.arange(class_count), average="weighted", zero_division=0)
    pm, rm, fm, _ = precision_recall_fscore_support(y_true, y_pred, labels=np.arange(class_count), average="macro", zero_division=0)
    return {"accuracy": float(accuracy_score(y_true, y_pred)), "precision_weighted": float(pw), "recall_weighted": float(rw), "f1_weighted": float(fw), "precision_macro": float(pm), "recall_macro": float(rm), "f1_macro": float(fm)}


def predict_tflite(tf, model_bytes: bytes, x: np.ndarray) -> Tuple[np.ndarray, str, str]:
    interpreter = tf.lite.Interpreter(model_content=model_bytes)
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    input_type = np.dtype(inp["dtype"]).name
    output_type = np.dtype(out["dtype"]).name
    in_scale, in_zero = inp["quantization"]
    out_scale, out_zero = out["quantization"]
    results = []
    for row in x:
        sample = np.asarray(row, dtype=np.float32).reshape(1, -1)
        if np.issubdtype(inp["dtype"], np.integer):
            if in_scale == 0:
                raise RuntimeError("TFLite input quantization scale is zero.")
            limits = np.iinfo(inp["dtype"])
            sample = np.clip(np.rint(sample / in_scale + in_zero), limits.min, limits.max).astype(inp["dtype"])
        else:
            sample = sample.astype(inp["dtype"])
        interpreter.set_tensor(inp["index"], sample)
        interpreter.invoke()
        pred = interpreter.get_tensor(out["index"])[0]
        if np.issubdtype(out["dtype"], np.integer):
            pred = (pred.astype(np.float32) - out_zero) * out_scale
        results.append(np.asarray(pred, dtype=np.float32))
    return np.vstack(results), input_type, output_type


def save_confusion(y_true: np.ndarray, y_pred: np.ndarray, classes: Sequence[str], output: Path, title: str) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=np.arange(len(classes)))
    pd.DataFrame(cm, index=classes, columns=classes).to_csv(output.with_suffix(".csv"))
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(cm, interpolation="nearest")
    fig.colorbar(im, ax=ax)
    ax.set(xticks=np.arange(len(classes)), yticks=np.arange(len(classes)), xticklabels=classes, yticklabels=classes,
           xlabel="Predicted label", ylabel="True label", title=title)
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    limit = cm.max() / 2 if cm.size else 0
    for r in range(cm.shape[0]):
        for c in range(cm.shape[1]):
            ax.text(c, r, str(cm[r, c]), ha="center", va="center", color="white" if cm[r, c] > limit else "black")
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def save_importance(model, x: np.ndarray, y: np.ndarray, feature_names: Sequence[str], tags: Sequence[str], out_dir: Path, repeats: int, seed: int) -> None:
    baseline = accuracy_score(y, np.argmax(model.predict(x, verbose=0), axis=1))
    rng = np.random.default_rng(seed)
    rows = []
    for col, name in enumerate(feature_names):
        drops = []
        for _ in range(repeats):
            shuffled = x.copy()
            shuffled[:, col] = rng.permutation(shuffled[:, col])
            pred = np.argmax(model.predict(shuffled, verbose=0), axis=1)
            drops.append(baseline - accuracy_score(y, pred))
        rows.append({"feature": name, "importance_mean_accuracy_drop": float(np.mean(drops)), "importance_std": float(np.std(drops))})
    table = pd.DataFrame(rows).sort_values("importance_mean_accuracy_drop", ascending=False)
    table.to_csv(out_dir / "feature_importance.csv", index=False)
    top = table.head(min(20, len(table))).sort_values("importance_mean_accuracy_drop")
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(top["feature"], top["importance_mean_accuracy_drop"])
    ax.set_xlabel("Test accuracy decrease after feature shuffling")
    ax.set_title("Permutation feature importance — Float32")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "feature_importance.png", dpi=160)
    plt.close(fig)

    def family(name: str) -> str:
        for tag in tags:
            if name.startswith(tag + "_"):
                return tag
        if name.startswith("corr_"):
            return "cross_component"
        if name.startswith("rotation_"):
            return "rotation_change"
        return "other"

    table["component_family"] = table["feature"].map(family)
    group = table.assign(positive=table["importance_mean_accuracy_drop"].clip(lower=0)).groupby("component_family", as_index=False)["positive"].sum()
    total = float(group["positive"].sum())
    group["dominance_percent"] = group["positive"] / total * 100.0 if total > 0 else 0.0
    group = group.sort_values("dominance_percent", ascending=False)
    group.to_csv(out_dir / "component_dominance.csv", index=False)
    plot = group.sort_values("dominance_percent")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(plot["component_family"], plot["dominance_percent"])
    ax.set_xlabel("Share of positive permutation importance (%)")
    ax.set_title("Quaternion component / feature-family dominance")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "component_dominance.png", dpi=160)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Quaternion time/frequency feature extraction, ANOVA/RFE reduction, Float32 and Int8 model evaluation.")
    p.add_argument("--csv", required=True, nargs="+", help="One or more CSVs, one recording per file. If label/recording_id columns are absent, filenames such as REST_01.csv are used to infer them.")
    p.add_argument("--output-dir", default="quat_model_output")
    p.add_argument("--label-column", default=None)
    p.add_argument("--quat-cols", nargs=4, default=None, metavar=("Q0", "Q1", "Q2", "Q3"), help="Quaternion values in the exact order printed by firmware.")
    p.add_argument("--group-column", default=None, help="Recording/trial ID column; defaults to auto-detect. Use none to disable.")
    p.add_argument("--timestamp-column", default=None, help="Timestamp column. Defaults to auto-detect. Use none if absent.")
    p.add_argument("--timestamp-unit", choices=("auto", "s", "ms"), default="auto")
    p.add_argument("--sample-rate", type=float, default=None, help="Actual sample rate in Hz, used only when timestamp column is absent.")
    p.add_argument("--window-size", type=int, default=128, help="Samples per feature window (default 128).")
    p.add_argument("--step-size", type=int, default=64, help="Window stride (default 64).")
    p.add_argument("--top-k", type=int, default=16)
    p.add_argument("--selection", choices=("anova", "rfe"), default="anova")
    p.add_argument("--epochs", type=int, default=120)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--importance-repeats", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--prepare-only", action="store_true", help="Generate plots and features without TensorFlow training.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.window_size < 8 or args.step_size < 1 or args.top_k < 1:
        raise ValueError("Use --window-size >= 8, --step-size >= 1, and --top-k >= 1.")
    if args.sample_rate is not None and args.sample_rate <= 0:
        raise ValueError("--sample-rate must be positive.")
    np.random.seed(args.seed)
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    data, quat_cols, tags, label_col, group_col, time_col = load_data(
        [Path(v).expanduser() for v in args.csv], args.label_column, args.quat_cols, args.group_column,
        args.timestamp_column, args.timestamp_unit, args.sample_rate
    )
    save_summary(data, quat_cols, tags, out_dir)
    save_signal_outputs(data, quat_cols, tags, out_dir)
    windows, all_names = build_windows(data, quat_cols, tags, args.window_size, args.step_size)
    windows.to_csv(out_dir / "window_features.csv", index=False)

    x_all = windows[all_names].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=np.float32)
    labels_text = windows["label"].astype(str).to_numpy()
    groups = windows["recording_id"].astype(str).to_numpy()
    enc = LabelEncoder()
    y = enc.fit_transform(labels_text)
    class_names = [str(v) for v in enc.classes_]
    if len(class_names) < 2:
        raise ValueError("At least two labels are needed to train a classifier. The current static-only recording is not enough.")
    trainval_idx, test_idx = split_recordings(y, groups, 0.20, args.seed, "test")
    train_local, val_local = split_recordings(y[trainval_idx], groups[trainval_idx], 0.20, args.seed + 1, "validation")
    train_idx, val_idx = trainval_idx[train_local], trainval_idx[val_local]

    selection_mask, selected_names, selection_table = select_features(x_all[train_idx], y[train_idx], all_names, args.top_k, args.selection, args.seed)
    selection_table.to_csv(out_dir / "feature_selection_scores.csv", index=False)
    x = x_all[:, selection_mask].astype(np.float32)
    x_train, x_val, x_test = x[train_idx], x[val_idx], x[test_idx]
    y_train, y_val, y_test = y[train_idx], y[val_idx], y[test_idx]

    if args.prepare_only:
        with open(out_dir / "selected_features.json", "w", encoding="utf-8") as f:
            json.dump({"selected_features_in_model_input_order": selected_names, "class_names_in_output_index_order": class_names, "selection_method": args.selection, "window_size_samples": args.window_size, "window_step_samples": args.step_size}, f, indent=2)
        print(f"[DONE] Feature extraction completed: {out_dir}")
        print("Install TensorFlow and rerun without --prepare-only to train Float32 and Int8 models.")
        return 0

    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError("TensorFlow is needed for neural-network training and Int8 TFLite conversion. Install it with: python -m pip install tensorflow") from exc

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train).astype(np.float32)
    x_val_scaled = scaler.transform(x_val).astype(np.float32)
    tf.keras.utils.set_random_seed(args.seed)
    trained = tf.keras.Sequential([
        tf.keras.Input(shape=(len(selected_names),), dtype=tf.float32),
        tf.keras.layers.Dense(24, activation="relu", name="dense_1"),
        tf.keras.layers.Dense(12, activation="relu", name="dense_2"),
        tf.keras.layers.Dense(len(class_names), activation="softmax", name="class_output"),
    ], name="quaternion_classifier_scaled")
    trained.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    history = trained.fit(x_train_scaled, y_train, validation_data=(x_val_scaled, y_val), epochs=args.epochs, batch_size=args.batch_size,
                          callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=15, restore_best_weights=True)], verbose=1)
    model = build_raw_model(tf, trained, scaler, len(selected_names), len(class_names))
    model_path = out_dir / "quaternion_float32.h5"
    model.save(model_path, include_optimizer=False)

    check_n = min(32, len(x_test))
    ref = trained.predict(scaler.transform(x_test[:check_n]), verbose=0)
    got = model.predict(x_test[:check_n], verbose=0)
    max_diff = float(np.max(np.abs(ref - got)))
    if max_diff > 2e-4:
        raise RuntimeError(f"Raw-feature model conversion check failed (max difference {max_diff:.6g}).")

    float_predictions = {}
    metric_rows = []
    for split_name, xx, yy in (("Validation", x_val, y_val), ("Test", x_test, y_test)):
        probs = model.predict(xx, verbose=0)
        pred = np.argmax(probs, axis=1)
        float_predictions[split_name] = pred
        metric_rows.append({"Model": "Float32", "Split": split_name, **metrics(yy, pred, len(class_names))})
        if split_name == "Test":
            save_confusion(y_test, pred, class_names, out_dir / "confusion_matrix_float32.png", "Float32 test confusion matrix")

    calib_rng = np.random.default_rng(args.seed + 7)
    by_class = [np.flatnonzero(y_train == c) for c in np.unique(y_train)]
    n_each = min(100, min(len(v) for v in by_class))
    calib_idx = np.concatenate([calib_rng.choice(v, size=n_each, replace=False) for v in by_class])
    calib_idx = calib_rng.permutation(calib_idx)
    def representative_dataset():
        for i in calib_idx:
            yield [x_train[i:i + 1].astype(np.float32)]

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    tflite_bytes = converter.convert()
    tflite_path = out_dir / "quaternion_int8.tflite"
    tflite_path.write_bytes(tflite_bytes)

    int8_input_type = int8_output_type = "unknown"
    for split_name, xx, yy in (("Validation", x_val, y_val), ("Test", x_test, y_test)):
        probs, int8_input_type, int8_output_type = predict_tflite(tf, tflite_bytes, xx)
        pred = np.argmax(probs, axis=1)
        metric_rows.append({"Model": "Int8 quantized", "Split": split_name, **metrics(yy, pred, len(class_names))})
        if split_name == "Test":
            save_confusion(y_test, pred, class_names, out_dir / "confusion_matrix_int8.png", "Int8 test confusion matrix")

    metric_df = pd.DataFrame(metric_rows)
    metric_df.to_csv(out_dir / "float32_vs_int8_metrics.csv", index=False)
    save_importance(model, x_test, y_test, selected_names, tags, out_dir, args.importance_repeats, args.seed)
    np.savez_compressed(out_dir / "cubeai_quantization_dataset.npz", x_test=x_train[calib_idx].astype(np.float32), y_test=y_train[calib_idx].astype(np.int32))

    with open(out_dir / "selected_features.json", "w", encoding="utf-8") as f:
        json.dump({
            "selected_features_in_model_input_order": selected_names,
            "all_engineered_features": all_names,
            "class_names_in_output_index_order": class_names,
            "quaternion_columns_in_input_order": quat_cols,
            "component_tags": tags,
            "feature_selection_method": args.selection,
            "window_size_samples": args.window_size,
            "window_step_samples": args.step_size,
            "sample_rate_hz_by_recording": {str(g): float(v["_sample_rate_hz"].iloc[0]) for g, v in data.groupby("_group", sort=False)},
            "model_input": "selected raw time/frequency features; scaler folded into first Dense layer",
        }, f, indent=2)
    with open(out_dir / "training_metadata.json", "w", encoding="utf-8") as f:
        json.dump({
            "source_csv": [str(Path(p).expanduser()) for p in args.csv],
            "label_column": label_col,
            "recording_id_column": group_col,
            "timestamp_column": time_col,
            "total_samples": int(len(data)),
            "total_windows": int(len(windows)),
            "recordings_per_class": {str(k): int(v) for k, v in data.groupby("_label")["_group"].nunique().items()},
            "train_windows": int(len(train_idx)),
            "validation_windows": int(len(val_idx)),
            "test_windows": int(len(test_idx)),
            "selected_feature_count": int(len(selected_names)),
            "feature_selection_method": args.selection,
            "float32_raw_input_equivalence_max_abs_difference": max_diff,
            "tensorflow_version": str(tf.__version__),
            "int8_input_dtype": int8_input_type,
            "int8_output_dtype": int8_output_type,
        }, f, indent=2)
    pd.DataFrame(history.history).to_csv(out_dir / "training_history.csv", index=False)

    print("\n[DONE] Training/evaluation complete.")
    print(f"Output folder: {out_dir}")
    print("Models: quaternion_float32.h5, quaternion_int8.tflite")
    print("Metrics: float32_vs_int8_metrics.csv")
    print("Confusion matrices: confusion_matrix_float32.png, confusion_matrix_int8.png")
    print("Importance: feature_importance.csv/png, component_dominance.csv/png")
    print("Selected features/order: selected_features.json")
    print("Representative data: cubeai_quantization_dataset.npz")
    print("\n" + metric_df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nNote: This PC script does not measure target Flash/RAM or MCU cycles. Use STM32Cube.AI analysis and on-target benchmarking for those figures.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
