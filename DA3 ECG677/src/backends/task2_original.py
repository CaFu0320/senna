#!/usr/bin/env python3
"""Train a compact 2D CNN on quaternion STFT spectrograms.

Input CSVs are one recording per file. By default, labels and recording IDs are
inferred from filenames such as static1.csv, leftrighttilt3.csv, and
updowntilt5.csv. The CSV must contain q0, q1, q2, q3 columns. If elapsed_s is
present, its median interval is used to estimate that recording's sample rate.

The script creates four-channel log-power STFT tensors, selects frequency bins
using ANOVA on the TRAINING recordings only, trains a Float32 CNN, converts it
to full-integer Int8 TFLite using a representative training set, and evaluates
both versions on recording-independent validation and test sets.

Example preparation run:
  py nn_quat_tfr_train.py --csv static1.csv ... updowntilt5.csv --prepare-only

Example full run:
  py nn_quat_tfr_train.py --csv static1.csv ... updowntilt5.csv
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import traceback
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import f_oneway
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    classification_report,
)

EPS = 1e-12
QUATERNION_COLUMNS = ["q0", "q1", "q2", "q3"]
CHANNEL_NAMES = ["q0", "q1", "q2", "q3"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create quaternion STFT spectrograms and train a compact 2D CNN."
    )
    parser.add_argument("--csv", nargs="+", required=True, help="One or more recording CSV files.")
    parser.add_argument("--output-dir", default="quat_tfr_output", help="Output directory (default: quat_tfr_output).")
    parser.add_argument("--label-source", choices=["filename", "csv"], default="filename",
                        help="Use filename prefixes (recommended) or the CSV label column.")
    parser.add_argument("--label-column", default="label", help="Label column when --label-source csv is used.")
    parser.add_argument("--timestamp-column", default="elapsed_s", help="Timestamp column used to estimate sample rate.")
    parser.add_argument("--sample-rate", type=float, default=10.0705,
                        help="Fallback sample rate in Hz when timestamps are unavailable (default: 10.0705).")
    parser.add_argument("--quat-cols", nargs=4, default=QUATERNION_COLUMNS,
                        metavar=("Q0", "Q1", "Q2", "Q3"), help="Quaternion column names.")
    parser.add_argument("--window-size", type=int, default=128, help="Quaternion samples per model example.")
    parser.add_argument("--step-size", type=int, default=64, help="Window hop in quaternion samples.")
    parser.add_argument("--stft-frame-length", type=int, default=32, help="Samples per STFT frame.")
    parser.add_argument("--stft-hop-length", type=int, default=8, help="STFT hop in samples.")
    parser.add_argument("--n-fft", type=int, default=32, help="FFT length (must be >= STFT frame length).")
    parser.add_argument("--top-frequency-bins", type=int, default=12,
                        help="Number of ANOVA-selected frequency bins to retain (default: 12).")
    parser.add_argument("--epochs", type=int, default=100, help="Maximum CNN training epochs.")
    parser.add_argument("--batch-size", type=int, default=16, help="Training batch size.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Create spectrograms, plots, splits, and ANOVA output without training.")
    parser.add_argument("--no-pad-last-window", action="store_true",
                        help="Drop a final partial window instead of padding it at the edge.")
    parser.add_argument("--skip-importance", action="store_true",
                        help="Skip test-set frequency/channel permutation importance after training.")
    return parser.parse_args()


def infer_label_from_filename(path: Path) -> str:
    stem = re.sub(r"[^a-z0-9]", "", path.stem.lower())
    patterns = [
        (r"^(static|rest)(?:\d+)?$", "static"),
        (r"^(leftrighttilt|leftright|lefttilt|lrtilt)(?:\d+)?$", "leftrighttilt"),
        (r"^(updowntilt|updown|pitch|udtilt)(?:\d+)?$", "updowntilt"),
    ]
    for pattern, label in patterns:
        if re.match(pattern, stem):
            return label
    raise ValueError(
        f"Cannot infer a class from filename '{path.name}'. Use prefixes "
        "static, leftrighttilt, or updowntilt, or use --label-source csv."
    )


def estimate_sample_rate(df: pd.DataFrame, timestamp_column: str, fallback_hz: float) -> tuple[float, str]:
    if timestamp_column not in df.columns:
        return float(fallback_hz), "fallback_argument"
    t = pd.to_numeric(df[timestamp_column], errors="coerce").to_numpy(dtype=np.float64)
    t = t[np.isfinite(t)]
    if t.size < 3:
        return float(fallback_hz), "fallback_argument_timestamp_unavailable"
    dt = np.diff(t)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    if dt.size == 0:
        return float(fallback_hz), "fallback_argument_invalid_timestamps"
    median_dt = float(np.median(dt))
    if median_dt <= 0:
        return float(fallback_hz), "fallback_argument_invalid_timestamps"
    return 1.0 / median_dt, "median_timestamp_interval"


def normalize_and_sign_align(quats: np.ndarray) -> np.ndarray:
    q = np.array(quats, dtype=np.float64, copy=True)
    norms = np.linalg.norm(q, axis=1)
    valid = np.isfinite(norms) & (norms > 1e-9)
    q = q[valid]
    norms = norms[valid]
    if q.shape[0] == 0:
        raise ValueError("No valid quaternion samples remain after removing invalid/zero rows.")
    q = q / norms[:, None]
    for i in range(1, q.shape[0]):
        if float(np.dot(q[i - 1], q[i])) < 0.0:
            q[i] *= -1.0
    return q.astype(np.float32)


def make_windows(data: np.ndarray, window_size: int, step_size: int, pad_last: bool) -> tuple[list[np.ndarray], list[int]]:
    n = len(data)
    if n == 0:
        return [], []
    starts = list(range(0, n - window_size + 1, step_size))
    windows: list[np.ndarray] = []
    used_starts: list[int] = []
    for start in starts:
        windows.append(np.array(data[start:start + window_size], dtype=np.float32, copy=True))
        used_starts.append(start)
    if pad_last:
        if starts:
            last_end = starts[-1] + window_size
            if n > last_end:
                next_start = starts[-1] + step_size
                if next_start < n:
                    tail = np.array(data[next_start:], dtype=np.float32, copy=True)
                    pad_count = window_size - len(tail)
                    if pad_count > 0:
                        tail = np.pad(tail, ((0, pad_count), (0, 0)), mode="edge")
                    windows.append(tail[:window_size])
                    used_starts.append(next_start)
        elif n < window_size:
            tail = np.array(data, dtype=np.float32, copy=True)
            tail = np.pad(tail, ((0, window_size - n), (0, 0)), mode="edge")
            windows.append(tail)
            used_starts.append(0)
    return windows, used_starts


def stft_log_power(window: np.ndarray, sample_rate: float, frame_length: int,
                   hop_length: int, n_fft: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if n_fft < frame_length:
        raise ValueError("--n-fft must be greater than or equal to --stft-frame-length.")
    if len(window) < frame_length:
        raise ValueError("Window is shorter than the STFT frame length.")
    starts = np.arange(0, len(window) - frame_length + 1, hop_length, dtype=int)
    frames = np.stack([window[s:s + frame_length] for s in starts], axis=0)
    hann = np.hanning(frame_length).astype(np.float64)
    window_energy = float(np.sum(hann ** 2))
    if window_energy <= 0:
        raise ValueError("STFT window energy is zero.")
    windowed = frames.astype(np.float64) * hann[None, :, None]
    spectrum = np.fft.rfft(windowed, n=n_fft, axis=1)
    power = (np.abs(spectrum) ** 2) / (float(sample_rate) * window_energy)
    if n_fft % 2 == 0:
        if power.shape[1] > 2:
            power[:, 1:-1, :] *= 2.0
    elif power.shape[1] > 1:
        power[:, 1:, :] *= 2.0
    log_power = (10.0 * np.log10(power + EPS)).astype(np.float32)
    tensor = np.transpose(log_power, (1, 0, 2))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / float(sample_rate)).astype(np.float32)
    frame_times = ((starts + (frame_length - 1) / 2.0) / float(sample_rate)).astype(np.float32)
    return tensor, freqs, frame_times


def load_recordings(args: argparse.Namespace) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]], dict[str, float]]:
    all_windows: list[np.ndarray] = []
    all_labels: list[str] = []
    all_groups: list[str] = []
    all_window_starts: list[int] = []
    all_sample_rates: list[float] = []
    summaries: list[dict[str, Any]] = []
    sample_rates_by_recording: dict[str, float] = {}
    pad_last = not args.no_pad_last_window

    for item in args.csv:
        csv_path = Path(item).expanduser().resolve()
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        df = pd.read_csv(csv_path)
        missing = [c for c in args.quat_cols if c not in df.columns]
        if missing:
            raise ValueError(f"{csv_path.name} is missing quaternion columns: {missing}")
        if args.label_source == "filename":
            label = infer_label_from_filename(csv_path)
        else:
            if args.label_column not in df.columns:
                raise ValueError(f"{csv_path.name} has no label column '{args.label_column}'.")
            labels_here = df[args.label_column].dropna().astype(str).str.strip().unique()
            if len(labels_here) != 1:
                raise ValueError(
                    f"{csv_path.name} must contain exactly one label per recording; found {labels_here.tolist()}"
                )
            label = labels_here[0].lower()
        recording_id = csv_path.stem
        q_df = df[args.quat_cols].apply(pd.to_numeric, errors="coerce")
        valid_rows = np.isfinite(q_df.to_numpy(dtype=np.float64)).all(axis=1)
        q_values = q_df.to_numpy(dtype=np.float64)[valid_rows]
        if q_values.size == 0:
            raise ValueError(f"No numeric quaternion rows found in {csv_path.name}.")
        q_values = normalize_and_sign_align(q_values)
        fs, fs_source = estimate_sample_rate(df.loc[valid_rows].reset_index(drop=True),
                                             args.timestamp_column, args.sample_rate)
        windows, starts = make_windows(q_values, args.window_size, args.step_size, pad_last)
        if not windows:
            raise ValueError(
                f"{csv_path.name} contains {len(q_values)} valid samples, fewer than "
                f"the {args.window_size}-sample window. Collect more data or reduce --window-size."
            )
        record_windows = []
        for w, start in zip(windows, starts):
            spec, freqs, frame_times = stft_log_power(
                w, fs, args.stft_frame_length, args.stft_hop_length, args.n_fft
            )
            record_windows.append(spec)
            all_windows.append(spec)
            all_labels.append(label)
            all_groups.append(recording_id)
            all_window_starts.append(int(start))
            all_sample_rates.append(fs)
        sample_rates_by_recording[recording_id] = float(fs)
        summaries.append({
            "source_csv": str(csv_path),
            "recording_id": recording_id,
            "label": label,
            "valid_quaternion_samples": int(len(q_values)),
            "window_count": int(len(windows)),
            "sample_rate_hz": float(fs),
            "sample_rate_source": fs_source,
            "quaternion_columns": ",".join(args.quat_cols),
        })
        print(f"[LOAD] {csv_path.name}: label={label}, samples={len(q_values)}, "
              f"windows={len(windows)}, sample_rate={fs:.4f} Hz ({fs_source})")

    X = np.stack(all_windows).astype(np.float32)
    y = np.asarray(all_labels, dtype=str)
    groups = np.asarray(all_groups, dtype=str)
    starts = np.asarray(all_window_starts, dtype=np.int32)
    rates = np.asarray(all_sample_rates, dtype=np.float32)
    return X, y, groups, starts, rates, summaries, sample_rates_by_recording


def _split_recordings_like_baseline(y: np.ndarray, groups: np.ndarray, holdout_fraction: float,
                                    seed: int, purpose: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Mirror the group-splitting procedure used by nn_quat_train_label_fix2.py."""
    classes = np.unique(y)
    groups_by_class: dict[str, list[str]] = {str(c): [] for c in classes}
    for group in np.unique(groups):
        group_labels = np.unique(y[groups == group])
        if len(group_labels) != 1:
            raise ValueError(f"Recording group {group!r} contains more than one class label.")
        groups_by_class[str(group_labels[0])].append(str(group))
    min_required = 3 if purpose == "test" else 2
    if not all(len(groups_by_class[str(c)]) >= min_required for c in classes):
        return None
    rng = np.random.default_rng(seed)
    holdout_groups: set[str] = set()
    for class_id in classes:
        options = np.asarray(groups_by_class[str(class_id)], dtype=object)
        count = max(1, int(math.ceil(len(options) * holdout_fraction)))
        max_hold = len(options) - (2 if purpose == "test" else 1)
        count = min(count, max_hold)
        chosen = rng.choice(options, size=count, replace=False)
        holdout_groups.update(str(v) for v in np.atleast_1d(chosen))
    mask = np.asarray([str(g) in holdout_groups for g in groups], dtype=bool)
    train_local = np.flatnonzero(~mask)
    hold_local = np.flatnonzero(mask)
    if not set(np.unique(y[train_local])) == set(classes) or not set(np.unique(y[hold_local])) == set(classes):
        return None
    return train_local, hold_local


def make_group_splits(y: np.ndarray, groups: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, dict[str, list[str]]]] | None:
    """Use the same two-stage 20% group holdouts as the statistical-feature baseline."""
    first = _split_recordings_like_baseline(y, groups, 0.20, seed, "test")
    if first is None:
        return None
    trainval_idx, test_idx = first
    second = _split_recordings_like_baseline(y[trainval_idx], groups[trainval_idx],
                                             0.20, seed + 1, "validation")
    if second is None:
        return None
    train_local, val_local = second
    train_idx = trainval_idx[train_local]
    val_idx = trainval_idx[val_local]
    classes = sorted(np.unique(y).tolist())
    assignment: dict[str, dict[str, list[str]]] = {}
    for label in classes:
        assignment[label] = {
            "train": sorted(np.unique(groups[train_idx][y[train_idx] == label]).tolist()),
            "validation": sorted(np.unique(groups[val_idx][y[val_idx] == label]).tolist()),
            "test": sorted(np.unique(groups[test_idx][y[test_idx] == label]).tolist()),
        }
    return train_idx.astype(np.int64), val_idx.astype(np.int64), test_idx.astype(np.int64), assignment


def anova_frequency_selection(X_train: np.ndarray, y_train: np.ndarray, n_keep: int,
                              freq_axis: np.ndarray, output_dir: Path) -> tuple[np.ndarray, pd.DataFrame]:
    n_freq = X_train.shape[1]
    per_channel_f = np.zeros((n_freq, X_train.shape[-1]), dtype=np.float64)
    per_channel_p = np.ones((n_freq, X_train.shape[-1]), dtype=np.float64)
    # One mean log-power value per sample, frequency bin, and quaternion channel.
    reduced = np.mean(X_train, axis=2)
    unique_classes = np.unique(y_train)
    if len(unique_classes) < 2:
        selected = np.arange(n_freq, dtype=int)
    else:
        for f in range(n_freq):
            for c in range(X_train.shape[-1]):
                groups = [reduced[y_train == cls, f, c] for cls in unique_classes]
                if all(len(g) > 0 for g in groups):
                    try:
                        with np.errstate(invalid="ignore", divide="ignore"):
                            f_stat, p_val = f_oneway(*groups)
                        per_channel_f[f, c] = 0.0 if not np.isfinite(f_stat) else float(f_stat)
                        per_channel_p[f, c] = 1.0 if not np.isfinite(p_val) else float(p_val)
                    except Exception:
                        per_channel_f[f, c] = 0.0
                        per_channel_p[f, c] = 1.0
        aggregate = np.mean(per_channel_f, axis=1)
        k = min(max(1, int(n_keep)), n_freq)
        selected = np.sort(np.argsort(aggregate)[::-1][:k])
    aggregate = np.mean(per_channel_f, axis=1)
    result = pd.DataFrame({
        "frequency_bin": np.arange(n_freq),
        "frequency_hz": freq_axis,
        "q0_f_score": per_channel_f[:, 0],
        "q1_f_score": per_channel_f[:, 1],
        "q2_f_score": per_channel_f[:, 2],
        "q3_f_score": per_channel_f[:, 3],
        "aggregate_f_score": aggregate,
        "selected": [int(i in set(selected.tolist())) for i in range(n_freq)],
    })
    result.to_csv(output_dir / "frequency_selection_scores.csv", index=False)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(freq_axis, aggregate, width=(freq_axis[1] - freq_axis[0]) * 0.8 if len(freq_axis) > 1 else 0.1)
    for i in selected:
        ax.axvline(float(freq_axis[i]), linestyle="--", alpha=0.5)
    ax.set_title("ANOVA frequency-bin selection (training recordings only)")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Mean ANOVA F-score across quaternion channels")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "frequency_selection_scores.png", dpi=160)
    plt.close(fig)
    return selected.astype(int), result


def save_dataset_plots(X: np.ndarray, y: np.ndarray, groups: np.ndarray, starts: np.ndarray,
                       sample_rates_by_recording: dict[str, float], args: argparse.Namespace,
                       freq_ref: np.ndarray, output_dir: Path) -> None:
    class_names = sorted(np.unique(y).tolist())
    nrows = len(class_names)
    global_vmin = float(np.percentile(X, 5))
    global_vmax = float(np.percentile(X, 98))

    fig, axes = plt.subplots(nrows, 4, figsize=(15, max(3.4, 3.0 * nrows)), squeeze=False)
    for row, label in enumerate(class_names):
        idx = int(np.flatnonzero(y == label)[0])
        rate = sample_rates_by_recording[groups[idx]]
        frame_count = X.shape[2]
        frame_times = (np.arange(frame_count) * args.stft_hop_length + (args.stft_frame_length - 1) / 2) / rate
        for ch in range(4):
            ax = axes[row, ch]
            ax.imshow(X[idx, :, :, ch], origin="lower", aspect="auto", interpolation="nearest",
                      extent=[float(frame_times[0]), float(frame_times[-1]), float(freq_ref[0]), float(freq_ref[-1])],
                      vmin=global_vmin, vmax=global_vmax, cmap="magma")
            ax.set_title(f"{label} — {CHANNEL_NAMES[ch]}")
            ax.set_xlabel("Time within window (s)")
            ax.set_ylabel("Frequency (Hz)")
    fig.suptitle("Quaternion STFT log-power spectrogram examples", y=1.01)
    fig.tight_layout()
    fig.savefig(output_dir / "spectrogram_examples.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(nrows, 4, figsize=(15, max(3.4, 3.0 * nrows)), squeeze=False)
    for row, label in enumerate(class_names):
        average = np.mean(X[y == label], axis=0)
        for ch in range(4):
            ax = axes[row, ch]
            ax.imshow(average[:, :, ch], origin="lower", aspect="auto", interpolation="nearest",
                      extent=[0, args.window_size / np.median(list(sample_rates_by_recording.values())),
                              float(freq_ref[0]), float(freq_ref[-1])],
                      vmin=global_vmin, vmax=global_vmax, cmap="magma")
            ax.set_title(f"Mean {label} — {CHANNEL_NAMES[ch]}")
            ax.set_xlabel("Time within window (s)")
            ax.set_ylabel("Frequency (Hz)")
    fig.suptitle("Class-average quaternion spectrograms", y=1.01)
    fig.tight_layout()
    fig.savefig(output_dir / "class_mean_spectrograms.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")


def plot_confusion(y_true: np.ndarray, y_pred: np.ndarray, class_names: list[str], path: Path, title: str) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=class_names)
    fig, ax = plt.subplots(figsize=(6.4, 5.5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(np.arange(len(class_names)), class_names, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(class_names)), class_names)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(title)
    threshold = cm.max() / 2 if cm.size else 0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > threshold else "black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def get_metrics(y_true: np.ndarray, y_pred: np.ndarray, model_name: str, split_name: str) -> dict[str, Any]:
    p_w, r_w, f_w, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
    p_m, r_m, f_m, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    return {
        "model": model_name,
        "split": split_name,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_weighted": float(p_w),
        "recall_weighted": float(r_w),
        "f1_weighted": float(f_w),
        "precision_macro": float(p_m),
        "recall_macro": float(r_m),
        "f1_macro": float(f_m),
    }


def quantized_tflite_predict(interpreter: Any, X: np.ndarray) -> np.ndarray:
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    input_scale, input_zero = input_detail.get("quantization", (0.0, 0))
    output_scale, output_zero = output_detail.get("quantization", (0.0, 0))
    predictions: list[int] = []
    for sample in X:
        batch = sample[np.newaxis, ...].astype(np.float32)
        if input_detail["dtype"] == np.int8:
            if not input_scale:
                raise RuntimeError("TFLite input is int8 but has no valid quantization scale.")
            batch_in = np.clip(np.rint(batch / input_scale + input_zero), -128, 127).astype(np.int8)
        elif input_detail["dtype"] == np.uint8:
            if not input_scale:
                raise RuntimeError("TFLite input is uint8 but has no valid quantization scale.")
            batch_in = np.clip(np.rint(batch / input_scale + input_zero), 0, 255).astype(np.uint8)
        else:
            batch_in = batch.astype(input_detail["dtype"])
        interpreter.set_tensor(input_detail["index"], batch_in)
        interpreter.invoke()
        out = interpreter.get_tensor(output_detail["index"])
        predictions.append(int(np.argmax(out.reshape(-1))))
    return np.asarray(predictions, dtype=np.int64)


def predict_float_model(model: Any, X: np.ndarray) -> np.ndarray:
    probabilities = model.predict(X, verbose=0)
    return np.argmax(probabilities, axis=1).astype(np.int64)


def permutation_importance(model: Any, X: np.ndarray, y_idx: np.ndarray, selected_bins: np.ndarray,
                           freq_ref: np.ndarray, output_dir: Path, seed: int) -> None:
    if len(X) < 2:
        print("[WARN] Not enough held-out windows for permutation importance; skipping.")
        return
    rng = np.random.default_rng(seed)
    base_probs = model.predict(X, verbose=0)
    base_loss = float(np.mean(-np.log(np.maximum(base_probs[np.arange(len(y_idx)), y_idx], EPS))))
    rows: list[dict[str, Any]] = []
    n_freq = X.shape[1]
    for f in range(n_freq):
        perturbed = X.copy()
        perm = rng.permutation(len(X))
        perturbed[:, f, :, :] = X[perm, f, :, :]
        probs = model.predict(perturbed, verbose=0)
        loss = float(np.mean(-np.log(np.maximum(probs[np.arange(len(y_idx)), y_idx], EPS))))
        original_bin = int(selected_bins[f])
        rows.append({"importance_type": "frequency_bin", "feature": f"bin_{original_bin}",
                     "frequency_hz": float(freq_ref[original_bin]), "loss_increase": loss - base_loss})
    for c, name in enumerate(CHANNEL_NAMES):
        perturbed = X.copy()
        perm = rng.permutation(len(X))
        perturbed[:, :, :, c] = X[perm, :, :, c]
        probs = model.predict(perturbed, verbose=0)
        loss = float(np.mean(-np.log(np.maximum(probs[np.arange(len(y_idx)), y_idx], EPS))))
        rows.append({"importance_type": "quaternion_channel", "feature": name,
                     "frequency_hz": np.nan, "loss_increase": loss - base_loss})
    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "frequency_channel_importance.csv", index=False)

    freq_df = df[df["importance_type"] == "frequency_bin"].sort_values("frequency_hz")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(freq_df["frequency_hz"], freq_df["loss_increase"])
    ax.set_xlabel("Selected frequency (Hz)")
    ax.set_ylabel("Increase in test cross-entropy")
    ax.set_title("CNN frequency-bin permutation importance")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "frequency_importance.png", dpi=160)
    plt.close(fig)

    ch_df = df[df["importance_type"] == "quaternion_channel"].sort_values("loss_increase", ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(ch_df["feature"], ch_df["loss_increase"])
    ax.set_xlabel("Quaternion channel")
    ax.set_ylabel("Increase in test cross-entropy")
    ax.set_title("Quaternion channel dominance (permutation importance)")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "quaternion_channel_importance.png", dpi=160)
    plt.close(fig)


def build_and_train_model(tf: Any, X_train: np.ndarray, y_train: np.ndarray,
                          X_val: np.ndarray, y_val: np.ndarray, n_classes: int,
                          epochs: int, batch_size: int, seed: int) -> Any:
    tf.keras.utils.set_random_seed(seed)
    train_mean = float(np.mean(X_train))
    train_std = float(np.std(X_train))
    if not np.isfinite(train_std) or train_std < 1e-6:
        train_std = 1.0
    input_shape = tuple(int(v) for v in X_train.shape[1:])
    inputs = tf.keras.Input(shape=input_shape, name="spectrogram_log_power")
    # Keep preprocessing in the graph so CubeAI receives raw log-power spectrograms.
    x = tf.keras.layers.Rescaling(scale=1.0 / train_std, offset=-train_mean / train_std,
                                  name="global_training_standardization")(inputs)
    x = tf.keras.layers.Conv2D(8, (3, 3), padding="same", activation="relu", name="conv2d_1")(x)
    x = tf.keras.layers.MaxPooling2D(pool_size=(2, 2), padding="same", name="max_pool_1")(x)
    x = tf.keras.layers.Conv2D(16, (3, 3), padding="same", activation="relu", name="conv2d_2")(x)
    x = tf.keras.layers.GlobalAveragePooling2D(name="global_average_pool")(x)
    x = tf.keras.layers.Dense(16, activation="relu", name="dense_16")(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="softmax", name="class_probabilities")(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="quaternion_time_frequency_cnn")
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
                  loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    early_stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=18,
                                                  restore_best_weights=True, min_delta=1e-4)
    model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=epochs,
              batch_size=batch_size, shuffle=True, callbacks=[early_stop], verbose=2)
    return model


def convert_full_int8(tf: Any, model: Any, representative_X: np.ndarray, destination: Path) -> Any:
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    def representative_dataset():
        for sample in representative_X:
            yield [np.asarray(sample[np.newaxis, ...], dtype=np.float32)]

    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    tflite_model = converter.convert()
    destination.write_bytes(tflite_model)
    interpreter = tf.lite.Interpreter(model_path=str(destination))
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    if input_detail["dtype"] != np.int8 or output_detail["dtype"] != np.int8:
        raise RuntimeError(
            f"Expected full Int8 input/output, got {input_detail['dtype']} / {output_detail['dtype']}."
        )
    return interpreter


def main() -> int:
    args = parse_args()
    if args.window_size < args.stft_frame_length:
        raise ValueError("--window-size must be at least --stft-frame-length.")
    if args.step_size < 1 or args.stft_hop_length < 1:
        raise ValueError("Window and STFT hop lengths must be positive.")
    if args.sample_rate <= 0:
        raise ValueError("--sample-rate must be positive.")
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    X, y, groups, starts, rates, recording_summaries, sample_rates_by_recording = load_recordings(args)
    class_names = sorted(np.unique(y).tolist())
    global_fs = float(np.median(rates))
    freq_ref = np.fft.rfftfreq(args.n_fft, d=1.0 / global_fs).astype(np.float32)
    frame_times = ((np.arange(X.shape[2]) * args.stft_hop_length +
                    (args.stft_frame_length - 1) / 2) / global_fs).astype(np.float32)

    print(f"[DATA] windows={len(X)}, tensor_shape={tuple(X.shape[1:])}, classes={class_names}")
    print(f"[DATA] median sample rate={global_fs:.5f} Hz; STFT bins={len(freq_ref)}; frames={X.shape[2]}")

    np.savez_compressed(
        output_dir / "spectrogram_windows.npz",
        X=X, labels=y, recording_ids=groups, window_starts=starts,
        sample_rates_hz=rates, frequency_axis_hz=freq_ref, frame_times_s=frame_times,
    )
    pd.DataFrame(recording_summaries).to_csv(output_dir / "recording_summary.csv", index=False)
    save_dataset_plots(X, y, groups, starts, sample_rates_by_recording, args, freq_ref, output_dir)

    split_result = make_group_splits(y, groups, args.seed)
    split_assignment_json: dict[str, Any] = {}
    if split_result is None:
        print("[WARN] Not enough independent recordings per class for train/validation/test group splits.")
        print("[WARN] Spectrogram preparation and plots will be saved; training requires at least 3 recordings per class.")
        selected_bins = np.arange(len(freq_ref), dtype=int)
        score_df = pd.DataFrame({
            "frequency_bin": np.arange(len(freq_ref)), "frequency_hz": freq_ref,
            "q0_f_score": np.nan, "q1_f_score": np.nan, "q2_f_score": np.nan,
            "q3_f_score": np.nan, "aggregate_f_score": np.nan, "selected": 1,
        })
        score_df.to_csv(output_dir / "frequency_selection_scores.csv", index=False)
        train_idx = val_idx = test_idx = np.asarray([], dtype=np.int64)
        if not args.prepare_only:
            raise ValueError(
                "Cannot train a recording-independent classifier: every class needs at least "
                "3 separate CSV recordings (one or more for train, validation, and test)."
            )
    else:
        train_idx, val_idx, test_idx, split_assignment = split_result
        split_assignment_json = split_assignment
        for split, idxs in (("train", train_idx), ("validation", val_idx), ("test", test_idx)):
            counts = {c: int(np.sum(y[idxs] == c)) for c in class_names}
            print(f"[SPLIT] {split}: {len(idxs)} windows; per-class={counts}")
        y_train_names = y[train_idx]
        selected_bins, score_df = anova_frequency_selection(
            X[train_idx], y_train_names, args.top_frequency_bins, freq_ref, output_dir
        )

    X_selected = X[:, selected_bins, :, :].astype(np.float32)
    np.savez_compressed(
        output_dir / "reduced_spectrogram_windows.npz",
        X=X_selected, labels=y, recording_ids=groups,
        selected_frequency_bins=selected_bins, selected_frequency_hz=freq_ref[selected_bins],
    )
    selected_info = {
        "selected_frequency_bins_original_indices": selected_bins.astype(int).tolist(),
        "selected_frequency_hz": freq_ref[selected_bins].astype(float).tolist(),
        "all_frequency_hz": freq_ref.astype(float).tolist(),
        "selection_method": "ANOVA F-statistic on training recordings; per-bin channel scores averaged",
        "requested_frequency_bin_count": int(args.top_frequency_bins),
        "actual_frequency_bin_count": int(len(selected_bins)),
    }
    save_json(output_dir / "selected_frequency_bins.json", selected_info)

    split_rows = []
    if split_result is not None:
        for split, idxs in (("train", train_idx), ("validation", val_idx), ("test", test_idx)):
            for i in idxs:
                split_rows.append({"window_index": int(i), "recording_id": groups[i], "label": y[i],
                                   "split": split, "window_start_sample": int(starts[i]),
                                   "sample_rate_hz": float(rates[i])})
        pd.DataFrame(split_rows).to_csv(output_dir / "recording_level_data_split.csv", index=False)

    prep_metadata = {
        "source_csvs": [str(Path(p).expanduser().resolve()) for p in args.csv],
        "label_source": args.label_source,
        "label_column": args.label_column,
        "timestamp_column": args.timestamp_column,
        "quaternion_columns_in_input_order": args.quat_cols,
        "class_names_in_output_index_order": class_names,
        "total_quaternion_windows": int(len(X)),
        "total_recordings": int(len(set(groups.tolist()))),
        "recordings_per_class": {c: int(len(set(groups[y == c].tolist()))) for c in class_names},
        "sample_rate_hz_median": global_fs,
        "sample_rate_hz_by_recording": sample_rates_by_recording,
        "window_size_samples": int(args.window_size),
        "window_step_samples": int(args.step_size),
        "stft_frame_length_samples": int(args.stft_frame_length),
        "stft_hop_length_samples": int(args.stft_hop_length),
        "n_fft": int(args.n_fft),
        "window_function": "symmetric Hann (numpy.hanning)",
        "spectrogram_definition": "one-sided PSD = abs(rFFT(frame * Hann))^2 / (sample_rate * sum(Hann^2)); interior bins doubled; tensor values = 10*log10(PSD + 1e-12)",
        "tensor_layout": "frequency x time x quaternion_channel",
        "raw_tensor_shape": [int(X.shape[1]), int(X.shape[2]), int(X.shape[3])],
        "selected_tensor_shape": [int(X_selected.shape[1]), int(X_selected.shape[2]), int(X_selected.shape[3])],
        "frequency_selection": selected_info,
        "recording_split": split_assignment_json,
        "split_window_counts": {
            "train": int(len(train_idx)), "validation": int(len(val_idx)), "test": int(len(test_idx))
        },
        "input_preprocessing_in_model": "global scalar standardization from training spectrogram values is embedded in first Rescaling layer; application supplies raw log-power spectrogram values",
    }
    save_json(output_dir / "spectrogram_metadata.json", prep_metadata)
    save_json(output_dir / "training_metadata.json", prep_metadata)

    if args.prepare_only:
        print(f"[DONE] Spectrogram preparation complete. Output folder: {output_dir}")
        print("Created: spectrogram_examples.png, class_mean_spectrograms.png, frequency_selection_scores.csv, "
              "spectrogram_windows.npz, reduced_spectrogram_windows.npz, spectrogram_metadata.json")
        return 0

    if split_result is None:
        raise RuntimeError("A valid recording-level split is required for training.")
    class_to_index = {name: i for i, name in enumerate(class_names)}
    y_idx = np.asarray([class_to_index[v] for v in y], dtype=np.int64)
    X_train, X_val, X_test = X_selected[train_idx], X_selected[val_idx], X_selected[test_idx]
    y_train, y_val, y_test = y_idx[train_idx], y_idx[val_idx], y_idx[test_idx]
    if len(np.unique(y_train)) < 2:
        raise ValueError("Training split contains fewer than two classes.")

    # Representative calibration data must come only from training recordings.
    representative = X_train[:min(200, len(X_train))].astype(np.float32)
    np.savez_compressed(
        output_dir / "cubeai_representative_spectrograms.npz",
        spectrograms=representative,
        selected_frequency_bins=selected_bins,
        selected_frequency_hz=freq_ref[selected_bins],
        class_names=np.asarray(class_names, dtype=str),
    )

    try:
        import tensorflow as tf
    except Exception as exc:
        raise RuntimeError(
            "TensorFlow is required for training and TFLite conversion. Install the packages listed in "
            "requirements_quat_tfr.txt, then rerun without --prepare-only."
        ) from exc

    print(f"[TRAIN] TensorFlow {tf.__version__}; training compact 2D CNN...")
    model = build_and_train_model(tf, X_train, y_train, X_val, y_val,
                                  n_classes=len(class_names), epochs=args.epochs,
                                  batch_size=args.batch_size, seed=args.seed)
    float_model_path = output_dir / "quaternion_tfr_float32.h5"
    model.save(float_model_path)
    with open(output_dir / "cnn_model_summary.txt", "w", encoding="utf-8") as f:
        model.summary(print_fn=lambda line: f.write(line + "\n"))

    metrics_rows: list[dict[str, Any]] = []
    prediction_frame = pd.DataFrame({
        "recording_id": groups[test_idx],
        "true_label": y[test_idx],
        "window_start_sample": starts[test_idx],
    })
    for split_name, X_split, y_split in (("Validation", X_val, y_val), ("Test", X_test, y_test)):
        pred_float = predict_float_model(model, X_split)
        metrics_rows.append(get_metrics(y_split, pred_float, "Float32", split_name))
        if split_name == "Test":
            y_names = np.asarray(class_names, dtype=str)[y_split]
            pred_names = np.asarray(class_names, dtype=str)[pred_float]
            plot_confusion(y_names, pred_names, class_names,
                           output_dir / "confusion_matrix_float32.png",
                           "Float32 CNN — recording-independent test set")
            pd.DataFrame(classification_report(y_names, pred_names, labels=class_names,
                                                output_dict=True, zero_division=0)).transpose().to_csv(
                output_dir / "classification_report_float32_test.csv")
            prediction_frame["float32_prediction"] = pred_names

    print("[QUANTIZE] Converting full-integer Int8 TFLite model...")
    tflite_path = output_dir / "quaternion_tfr_int8.tflite"
    interpreter = convert_full_int8(tf, model, representative, tflite_path)
    for split_name, X_split, y_split in (("Validation", X_val, y_val), ("Test", X_test, y_test)):
        pred_int8 = quantized_tflite_predict(interpreter, X_split)
        metrics_rows.append(get_metrics(y_split, pred_int8, "Int8 quantized", split_name))
        if split_name == "Test":
            y_names = np.asarray(class_names, dtype=str)[y_split]
            pred_names = np.asarray(class_names, dtype=str)[pred_int8]
            plot_confusion(y_names, pred_names, class_names,
                           output_dir / "confusion_matrix_int8.png",
                           "Int8 CNN — recording-independent test set")
            pd.DataFrame(classification_report(y_names, pred_names, labels=class_names,
                                                output_dict=True, zero_division=0)).transpose().to_csv(
                output_dir / "classification_report_int8_test.csv")
            prediction_frame["int8_prediction"] = pred_names

    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df["model_size_bytes"] = [float_model_path.stat().st_size if r["model"] == "Float32" else tflite_path.stat().st_size
                                      for r in metrics_rows]
    metrics_df.to_csv(output_dir / "float32_vs_int8_metrics.csv", index=False)
    prediction_frame.to_csv(output_dir / "test_predictions.csv", index=False)

    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    quant_params = {
        "input_name": input_detail["name"],
        "input_shape": [int(v) for v in input_detail["shape"]],
        "input_dtype": str(input_detail["dtype"]),
        "input_scale": float(input_detail["quantization"][0]),
        "input_zero_point": int(input_detail["quantization"][1]),
        "output_name": output_detail["name"],
        "output_shape": [int(v) for v in output_detail["shape"]],
        "output_dtype": str(output_detail["dtype"]),
        "output_scale": float(output_detail["quantization"][0]),
        "output_zero_point": int(output_detail["quantization"][1]),
        "class_names_in_output_index_order": class_names,
        "input_note": "The input is the selected raw log-power spectrogram; global standardization is included in the model graph.",
    }
    save_json(output_dir / "cubeai_model_io.json", quant_params)

    if not args.skip_importance:
        permutation_importance(model, X_test, y_test, selected_bins, freq_ref, output_dir, args.seed)

    prep_metadata.update({
        "tensorflow_version": str(tf.__version__),
        "model_architecture": "Conv2D(8)-MaxPool-Conv2D(16)-GlobalAveragePooling-Dense(16)-Softmax(3)",
        "model_input_shape_without_batch": [int(v) for v in X_train.shape[1:]],
        "model_output_class_order": class_names,
        "float32_model_file": float_model_path.name,
        "int8_model_file": tflite_path.name,
        "float32_model_size_bytes": int(float_model_path.stat().st_size),
        "int8_model_size_bytes": int(tflite_path.stat().st_size),
        "int8_input_dtype": str(input_detail["dtype"]),
        "int8_output_dtype": str(output_detail["dtype"]),
        "int8_input_scale": float(input_detail["quantization"][0]),
        "int8_input_zero_point": int(input_detail["quantization"][1]),
        "int8_output_scale": float(output_detail["quantization"][0]),
        "int8_output_zero_point": int(output_detail["quantization"][1]),
        "train_windows": int(len(train_idx)),
        "validation_windows": int(len(val_idx)),
        "test_windows": int(len(test_idx)),
    })
    save_json(output_dir / "training_metadata.json", prep_metadata)

    print("\n[DONE] Time-frequency CNN training and evaluation complete.")
    print(f"Output folder: {output_dir}")
    print(f"Models: {float_model_path.name}, {tflite_path.name}")
    print("Metrics: float32_vs_int8_metrics.csv")
    print("Confusion matrices: confusion_matrix_float32.png, confusion_matrix_int8.png")
    print("Importance: frequency_channel_importance.csv, frequency_importance.png, quaternion_channel_importance.png")
    print("CubeAI files: cubeai_model_io.json, cubeai_representative_spectrograms.npz")
    print(metrics_df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
