"""
data_preparation.py
Design Assignment 2 - Task 1: Data Preparation and Exploratory Analysis (DPEA)

Sensor : LSM6DSV16X on X-NUCLEO-IKS4A1, logged with MEMS Studio (Save to File)
Sampling is estimated from logged timestamps. Sensor settings require acquisition metadata.

What this script does
  1. Loads one MEMS Studio CSV per activity (label taken from the file name,
     or from a label column if you used "Set label").
  2. Converts units (mg -> g, mdps -> dps, timestamp -> seconds).
  3. Uses the quaternion q0..q3 if it is in the file (on-board sensor fusion);
     otherwise computes it offline with a Madgwick IMU filter.
  4. Exploratory analysis: per-class statistics, feature ranges, sampling-rate
     check (the logged timestamps are irregular), dominant frequency per class,
     time-series plots, class distribution.
  5. Stratified 70 / 15 / 15 train / validation / test split, saved to CSV
     for exploratory analysis. Model scripts use chronological splits.

Usage
  Put your recordings in ./data/raw/ named Curl.csv, LateralRaise.csv, LeftPunch.csv
  Keep the separate measured quaternion takes in ./data/quatlogs/.
  Then run:   python src/data_preparation.py
  Optional:   python data_preparation.py --raw-dir path/to/csvs --out-dir results
"""

import argparse
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
RANDOM_STATE = 42
TRAIN_FRAC, VAL_FRAC, TEST_FRAC = 0.70, 0.15, 0.15
TRIM_SECONDS = 0.0
SAMPLE_WINDOW_S = 5.0     # length of the "few seconds of each activity" plots
MADGWICK_BETA = 0.1       # Madgwick filter gain (only used if no quaternion in the file)
RESAMPLE_HZ = 100.0       # uniform grid used ONLY for frequency analysis (logs are irregular)

# File-name word -> class name. Matches the class names used on the board firmware.
LABEL_MAP = {"curl": "Curl", "lateralraise": "LateralRaise", "leftpunch": "LeftPunch"}

ACC_COLS = ["acc_x", "acc_y", "acc_z"]
GYRO_COLS = ["gyro_x", "gyro_y", "gyro_z"]
QUAT_COLS = ["q0", "q1", "q2", "q3"]          # q0 = scalar (w) part
FEATURES = ACC_COLS + GYRO_COLS + QUAT_COLS

# If auto-detection picks the wrong column, put the exact header text here,
# e.g. COLUMN_OVERRIDES = {"acc_x": "A_X [mg]", "time": "Timestamp [ms]"}
COLUMN_OVERRIDES = {}

# Regex patterns used to recognise MEMS Studio column names (case-insensitive).
# LSB columns are excluded so the physical-unit columns are used.
COLUMN_PATTERNS = {
    "time":   [r"time", r"tstamp"],
    "acc_x":  [r"\bacc\w*[\s_\-\[]*x", r"^a_?x\b"],
    "acc_y":  [r"\bacc\w*[\s_\-\[]*y", r"^a_?y\b"],
    "acc_z":  [r"\bacc\w*[\s_\-\[]*z", r"^a_?z\b"],
    "gyro_x": [r"\bgyr\w*[\s_\-\[]*x", r"^g_?x\b"],
    "gyro_y": [r"\bgyr\w*[\s_\-\[]*y", r"^g_?y\b"],
    "gyro_z": [r"\bgyr\w*[\s_\-\[]*z", r"^g_?z\b"],
    # SFLP / game rotation vector quaternion, if MEMS Studio logged it
    "q0": [r"\bq_?0\b", r"\bq_?w\b", r"(quat|rot|sflp|game)\w*[\s_\-\[]*w\b"],
    "q1": [r"\bq_?1\b", r"\bq_?x\b", r"(quat|rot|sflp|game)\w*[\s_\-\[]*x\b"],
    "q2": [r"\bq_?2\b", r"\bq_?y\b", r"(quat|rot|sflp|game)\w*[\s_\-\[]*y\b"],
    "q3": [r"\bq_?3\b", r"\bq_?z\b", r"(quat|rot|sflp|game)\w*[\s_\-\[]*z\b"],
    "label": [r"label", r"class", r"activity"],
}


# --------------------------------------------------------------------------
# 1. Loading
# --------------------------------------------------------------------------
# Find the sensor header after the metadata rows in the MEMS Studio export.
def _find_header_row(path):
    """MEMS Studio may put info lines above the header; find the real header."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            low = line.lower()
            if ("acc" in low or "a_x" in low) and ("gyr" in low or "g_x" in low):
                return i
            if i > 50:
                break
    return 0


def _match_columns(columns):
    mapping = {}
    for target, patterns in COLUMN_PATTERNS.items():
        if target in COLUMN_OVERRIDES:
            mapping[target] = COLUMN_OVERRIDES[target]
            continue
        for col in columns:
            name = col.strip().lower()
            if "lsb" in name or col in mapping.values():
                continue
            is_quat_col = re.search(r"quat|rot|sflp|game", name)
            if target in ACC_COLS + GYRO_COLS + ["time"] and is_quat_col:
                continue  # keep quaternion columns out of acc/gyro matches
            if any(re.search(p, name) for p in patterns):
                mapping[target] = col
                break
    return mapping


def _time_to_seconds(t):
    """Convert a timestamp column to seconds starting at 0, whatever its unit."""
    t = pd.to_numeric(t, errors="coerce").astype(float).to_numpy()
    # Infer the timestamp unit from typical spacing before resetting the time origin.
    dt = np.nanmedian(np.diff(t))
    if dt > 1000:        # microseconds
        t = t / 1e6
    elif dt > 1:         # milliseconds (60 Hz -> ~16.7 ms)
        t = t / 1e3
    return t - t[0]


def load_recording(path):
    """Load one MEMS Studio CSV and return a clean DataFrame in g / dps / s."""
    header_row = _find_header_row(path)
    raw = pd.read_csv(path, sep=None, engine="python", skiprows=header_row)
    raw = raw.loc[:, ~raw.columns.astype(str).str.startswith("Unnamed")]
    mapping = _match_columns([str(c) for c in raw.columns])

    missing = [c for c in ["time"] + ACC_COLS + GYRO_COLS if c not in mapping]
    if missing:
        raise ValueError(
            f"{path.name}: could not find columns {missing}.\n"
            f"Columns in file: {list(raw.columns)}\n"
            f"Add them to COLUMN_OVERRIDES at the top of the script.")

    # MEMS Studio writes a row whenever ANY sensor updates. The data_changed
    # bitmask says which values are new (0x07 = acc x/y/z, 0x38 = gyro x/y/z).
    # Keep one row per accelerometer update so every sample is counted once
    # (gyro values on that row are the latest reading); drop 0x00 duplicates.
    rows_in = len(raw)
    flag_col = next((c for c in raw.columns if "data_changed" in str(c).lower()), None)
    if flag_col is not None:
        flags = raw[flag_col].apply(
            lambda s: int(str(s), 16) if str(s).lower().startswith("0x") else int(s))
        keep = (flags & 0x07) != 0 if ((flags & 0x07) != 0).any() else flags != 0
        raw = raw[keep.to_numpy()].reset_index(drop=True)
    print(f"  {path.name}: {rows_in} rows in file -> {len(raw)} unique samples")

    df = pd.DataFrame({"t": _time_to_seconds(raw[mapping["time"]])})
    for c in ACC_COLS + GYRO_COLS:
        df[c] = pd.to_numeric(raw[mapping[c]], errors="coerce")

    # Units: MEMS Studio logs mg and mdps. Use the header if it says so,
    # otherwise fall back on magnitude (|a| at rest is ~1000 mg vs ~1 g).
    acc_name = mapping["acc_x"].lower()
    acc_mag = np.nanmedian(np.linalg.norm(df[ACC_COLS].to_numpy(), axis=1))
    if "mg" in acc_name or acc_mag > 50:
        df[ACC_COLS] = df[ACC_COLS] / 1000.0
    gyro_name = mapping["gyro_x"].lower()
    if "mdps" in gyro_name or np.nanmax(np.abs(df[GYRO_COLS].to_numpy())) > 5000:
        df[GYRO_COLS] = df[GYRO_COLS] / 1000.0

    has_sflp = all(q in mapping for q in QUAT_COLS)
    if has_sflp:
        for q in QUAT_COLS:
            df[q] = pd.to_numeric(raw[mapping[q]], errors="coerce")

    if "label" in mapping:
        df["label"] = raw[mapping["label"]].astype(str).str.strip().str.lower()
    else:
        word = re.split(r"[_.\-\s]", path.stem)[0].lower()
        df["label"] = LABEL_MAP.get(word, word)

    df = df.dropna(subset=["t"] + ACC_COLS + GYRO_COLS).reset_index(drop=True)
    df["source_file"] = path.name

    # Sanity check: a sensor that was powered down logs only zeros.
    problems = []
    if np.allclose(df[ACC_COLS].to_numpy(), 0):
        problems.append("accelerometer is all zeros (was it set to Power-Down?)")
    if np.allclose(df[GYRO_COLS].to_numpy(), 0):
        problems.append("gyroscope is all zeros (was it set to Power-Down?)")
    return df, has_sflp, mapping, problems


# --------------------------------------------------------------------------
# 2. Quaternions (Madgwick IMU filter, used only if SFLP was not logged)
# --------------------------------------------------------------------------
def _quat_from_gravity(ax, ay, az):
    """Initial orientation aligning the sensor z-axis with measured gravity."""
    n = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
    ax, ay, az = ax / n, ay / n, az / n
    roll = math.atan2(ay, az)
    pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az))
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    return np.array([cr * cp, sr * cp, cr * sp, -sr * sp])


def madgwick_quaternions(t, acc_g, gyro_dps, beta=MADGWICK_BETA):
    """6-axis Madgwick filter. Returns an (N, 4) array [q0, q1, q2, q3]."""
    n = len(t)
    out = np.zeros((n, 4))
    q0, q1, q2, q3 = _quat_from_gravity(*acc_g[0])
    gyro = np.radians(gyro_dps)
    # Use actual sample intervals for integration and a nominal interval at startup or across long gaps.
    dts = np.diff(t, prepend=t[0])
    nominal_dt = np.median(np.diff(t)) if n > 1 else 1 / 60
    for i in range(n):
        dt = dts[i] if 0 < dts[i] < 5 * nominal_dt else nominal_dt
        gx, gy, gz = gyro[i]
        ax, ay, az = acc_g[i]
        # Rate of change of quaternion from gyroscope
        qd0 = 0.5 * (-q1 * gx - q2 * gy - q3 * gz)
        qd1 = 0.5 * (q0 * gx + q2 * gz - q3 * gy)
        qd2 = 0.5 * (q0 * gy - q1 * gz + q3 * gx)
        qd3 = 0.5 * (q0 * gz + q1 * gy - q2 * gx)
        norm_a = math.sqrt(ax * ax + ay * ay + az * az)
        if norm_a > 0:
            ax, ay, az = ax / norm_a, ay / norm_a, az / norm_a
            # Gradient-descent correction towards measured gravity
            f1 = 2 * (q1 * q3 - q0 * q2) - ax
            f2 = 2 * (q0 * q1 + q2 * q3) - ay
            f3 = 2 * (0.5 - q1 * q1 - q2 * q2) - az
            s0 = -2 * q2 * f1 + 2 * q1 * f2
            s1 = 2 * q3 * f1 + 2 * q0 * f2 - 4 * q1 * f3
            s2 = -2 * q0 * f1 + 2 * q3 * f2 - 4 * q2 * f3
            s3 = 2 * q1 * f1 + 2 * q2 * f2
            norm_s = math.sqrt(s0 * s0 + s1 * s1 + s2 * s2 + s3 * s3)
            if norm_s > 0:
                qd0 -= beta * s0 / norm_s
                qd1 -= beta * s1 / norm_s
                qd2 -= beta * s2 / norm_s
                qd3 -= beta * s3 / norm_s
        # Integrate the corrected rate and renormalize so the quaternion remains a unit rotation.
        q0 += qd0 * dt
        q1 += qd1 * dt
        q2 += qd2 * dt
        q3 += qd3 * dt
        norm_q = math.sqrt(q0 * q0 + q1 * q1 + q2 * q2 + q3 * q3)
        q0, q1, q2, q3 = q0 / norm_q, q1 / norm_q, q2 / norm_q, q3 / norm_q
        out[i] = (q0, q1, q2, q3)
    return out


def load_dataset(raw_dir):
    files = sorted(Path(raw_dir).glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {raw_dir}")
    frames, quat_source, rejected = [], {}, {}
    for path in files:
        df, has_sflp, mapping, problems = load_recording(path)
        if problems:
            rejected[path.name] = problems
            print(f"  !! SKIPPING {path.name}: " + "; ".join(problems))
            continue
        fs = 1 / np.mean(np.diff(df["t"]))   # effective rate (steps are irregular)
        print(f"     label='{df['label'].iloc[0]}', fs={fs:.1f} Hz, "
              f"columns used: { {k: v for k, v in mapping.items() if k != 'label'} }")
        if not has_sflp:
            df[QUAT_COLS] = madgwick_quaternions(
                df["t"].to_numpy(), df[ACC_COLS].to_numpy(), df[GYRO_COLS].to_numpy())
        quat_source[path.name] = "logged in file (on-board fusion)" if has_sflp else "Madgwick (offline)"
        # Trim transitions at start/end of each recording
        keep = (df["t"] >= TRIM_SECONDS) & (df["t"] <= df["t"].iloc[-1] - TRIM_SECONDS)
        df = df[keep].copy()
        df["t"] = df["t"] - df["t"].iloc[0]
        frames.append(df)
    if not frames:
        raise RuntimeError("Every recording was rejected - see messages above.")
    data = pd.concat(frames, ignore_index=True)
    fs_files = data.groupby("source_file")["t"].apply(lambda t: 1 / np.mean(np.diff(t)))
    if fs_files.max() > 1.2 * fs_files.min():
        print("  !! WARNING: recordings have different sampling rates:\n"
              + fs_files.round(1).to_string()
              + "\n     Record every activity with the same ODR.")
    if rejected:
        print("\n  !! WARNING: these files were NOT used and must be re-recorded:")
        for name, probs in rejected.items():
            print(f"     {name}: {'; '.join(probs)}")
    return data, quat_source


# --------------------------------------------------------------------------
# 3. Exploratory analysis
# --------------------------------------------------------------------------
def sampling_report(data):
    rows = []
    for fname, g in data.groupby("source_file"):
        dt = np.diff(g["t"].to_numpy())
        rows.append({
            # Report active sampling separately from effective sampling, which includes pauses.
            "active_rate_Hz": round(1 / np.mean(dt[(dt > 0) & (dt <= 0.1)]), 2),
            "gaps_over_100ms": int((dt > 0.1).sum()),
            "file": fname, "label": g["label"].iloc[0], "samples": len(g),
            "duration_s": round(g["t"].iloc[-1], 2),
            "effective_rate_Hz": round(1 / dt.mean(), 2),
            "dt_min_ms": round(dt.min() * 1e3, 1),
            "dt_median_ms": round(np.median(dt) * 1e3, 1),
            "dt_max_ms": round(dt.max() * 1e3, 1),
            "pct_steps_over_1p5x_median": round(100 * np.mean(dt > 1.5 * np.median(dt)), 1),
        })
    return pd.DataFrame(rows)


def per_class_stats(data):
    stats = data.groupby("label")[FEATURES].agg(["mean", "std", "min", "max"])
    return stats.round(4)


def feature_ranges(data):
    return pd.DataFrame({
        "unit": ["g"] * 3 + ["dps"] * 3 + ["-"] * 4,
        "min": data[FEATURES].min(), "max": data[FEATURES].max(),
        "mean": data[FEATURES].mean(), "std": data[FEATURES].std(),
    }).round(4)


def _uniform_signals(g, cols):
    """Interpolate each recording of a class onto a uniform RESAMPLE_HZ grid.
    Needed because logged timestamps are irregular (10 ms / 20 ms steps), and an
    FFT assumes evenly spaced samples. Returns a list of 1-D magnitude signals."""
    out = []
    for _, f in g.groupby("source_file"):
        t = f["t"].to_numpy()
        steps = np.diff(t)
        # Interpolate within contiguous segments to avoid inventing signal across a logging gap.
        breaks = np.flatnonzero((steps > 0.1) | (steps <= 0)) + 1
        for idx in np.split(np.arange(len(t)), breaks):
            if len(idx) < 4:
                continue
            grid = np.arange(t[idx[0]], t[idx[-1]], 1 / RESAMPLE_HZ)
            comp = [np.interp(grid, t[idx], f[c].to_numpy()[idx]) for c in cols]
            out.append(np.linalg.norm(np.vstack(comp), axis=0))
    return out


def _welch_mean(signals, nperseg=256):
    from scipy.signal import welch
    psds = []
    for x in signals:
        x = x - x.mean()
        n = min(nperseg, len(x))
        f, pxx = welch(x, fs=RESAMPLE_HZ, window="hann", nperseg=n)
        # Align the segment spectra on one frequency grid before averaging them.
        psds.append(np.interp(np.linspace(0, RESAMPLE_HZ / 2, 129), f, pxx))
    return np.linspace(0, RESAMPLE_HZ / 2, 129), np.mean(psds, axis=0)


def dominant_frequencies(data):
    """Dominant frequency of |acc| and |gyro| per class (temporal dynamics)."""
    rows = []
    for label, g in data.groupby("label"):
        row = {"label": label}
        for name, cols in [("acc_mag", ACC_COLS), ("gyro_mag", GYRO_COLS)]:
            sigs = _uniform_signals(g, cols)
            freqs, psd = _welch_mean(sigs)
            band = freqs > 0.5                    # ignore DC / slow drift
            row[f"{name}_peak_Hz"] = round(freqs[band][np.argmax(psd[band])], 2)
            row[f"{name}_rms"] = round(float(np.mean([np.std(x) for x in sigs])), 4)
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 4. Visualisation
# --------------------------------------------------------------------------
def _sample_segment(g, seconds):
    g = g[g["source_file"] == g["source_file"].iloc[0]].reset_index(drop=True)
    mid = g["t"].iloc[len(g) // 2]
    seg = g[(g["t"] >= mid - seconds / 2) & (g["t"] < mid + seconds / 2)]
    return seg.assign(t=seg["t"] - seg["t"].iloc[0])


def plot_full_timeseries(data, out_dir):
    """Full 6-axis recording for every file (Acc top, Gyro bottom)."""
    for fname, g in data.groupby("source_file"):
        fig, ax = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
        for c in ACC_COLS:
            ax[0].plot(g["t"], g[c], lw=0.7, label=c)
        for c in GYRO_COLS:
            ax[1].plot(g["t"], g[c], lw=0.7, label=c)
        ax[0].set_ylabel("Acceleration [g]")
        ax[1].set_ylabel("Angular rate [dps]")
        ax[1].set_xlabel("Time [s]")
        for a in ax:
            a.legend(loc="upper right", ncol=3, fontsize=8)
            a.grid(alpha=0.3)
        fig.suptitle(f"6-axis IMU - {g['label'].iloc[0]} ({fname})")
        fig.tight_layout()
        fig.savefig(out_dir / f"timeseries_{Path(fname).stem}.png", dpi=150)
        plt.close(fig)


def plot_activity_samples(data, out_dir, seconds=SAMPLE_WINDOW_S):
    """A few seconds of every activity side by side: Acc, Gyro, Quaternion."""
    labels = sorted(data["label"].unique())
    fig, ax = plt.subplots(len(labels), 3, figsize=(16, 2.8 * len(labels)),
                           squeeze=False, sharex=True)
    for r, label in enumerate(labels):
        seg = _sample_segment(data[data["label"] == label], seconds)
        for c, (cols, ylab) in enumerate([(ACC_COLS, "Acc [g]"),
                                          (GYRO_COLS, "Gyro [dps]"),
                                          (QUAT_COLS, "Quaternion")]):
            for col in cols:
                ax[r, c].plot(seg["t"], seg[col], lw=0.9, label=col)
            ax[r, c].set_ylabel(f"{label}\n{ylab}" if c == 0 else ylab)
            ax[r, c].grid(alpha=0.3)
            if r == 0:
                ax[r, c].legend(loc="upper right", ncol=4, fontsize=7)
    for c in range(3):
        ax[-1, c].set_xlabel("Time [s]")
    fig.suptitle(f"{seconds:.0f}-second sample of each activity")
    fig.tight_layout()
    fig.savefig(out_dir / "activity_samples.png", dpi=150)
    plt.close(fig)


def plot_class_distribution(data, out_dir):
    counts = data["label"].value_counts().sort_index()
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    bars = ax[0].bar(counts.index, counts.values, color="steelblue")
    ax[0].bar_label(bars)
    ax[0].set_ylabel("Samples")
    ax[0].set_title("Samples per class")
    ax[0].grid(axis="y", alpha=0.3)
    ax[1].pie(counts.values, labels=counts.index, autopct="%1.1f%%", startangle=90)
    ax[1].set_title("Class proportion")
    fig.tight_layout()
    fig.savefig(out_dir / "class_distribution.png", dpi=150)
    plt.close(fig)


def plot_feature_boxplots(data, out_dir):
    """Feature ranges per class - shows how separable the raw features are."""
    labels = sorted(data["label"].unique())
    fig, ax = plt.subplots(2, 5, figsize=(18, 7))
    for a, feat in zip(ax.ravel(), FEATURES):
        a.boxplot([data.loc[data["label"] == l, feat] for l in labels],
                  tick_labels=labels, showfliers=False)
        a.set_title(feat)
        a.tick_params(axis="x", rotation=45)
        a.grid(alpha=0.3)
    fig.suptitle("Feature distribution per class (outliers hidden)")
    fig.tight_layout()
    fig.savefig(out_dir / "feature_boxplots.png", dpi=150)
    plt.close(fig)


def plot_spectra(data, out_dir):
    """Spectrum of |acc| per class - temporal dynamics."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for label, g in data.groupby("label"):
        freqs, psd = _welch_mean(_uniform_signals(g, ACC_COLS))
        ax.plot(freqs, np.sqrt(psd), lw=1.1, label=label)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("Acc magnitude spectrum (sqrt of PSD) [g/sqrt(Hz)]")
    ax.set_title("Frequency content per activity")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "spectrum_per_class.png", dpi=150)
    plt.close(fig)


def plot_split(split_counts, out_dir):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sets = ["train", "val", "test"]
    x = np.arange(len(split_counts))
    w = 0.27
    for i, s in enumerate(sets):
        b = ax.bar(x + (i - 1) * w, split_counts[s], w, label=s)
        ax.bar_label(b, fontsize=7)
    ax.set_xticks(x, split_counts.index)
    ax.set_ylabel("Samples")
    ax.set_title("Stratified split: samples per class per set")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "split_distribution.png", dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------
# 5. Stratified split
# --------------------------------------------------------------------------
# Preserve class proportions for exploratory exports. The model scripts split recordings chronologically.
def stratified_split(data):
    train, temp = train_test_split(
        data, test_size=VAL_FRAC + TEST_FRAC,
        stratify=data["label"], random_state=RANDOM_STATE)
    val, test = train_test_split(
        temp, test_size=TEST_FRAC / (VAL_FRAC + TEST_FRAC),
        stratify=temp["label"], random_state=RANDOM_STATE)
    counts = pd.DataFrame({
        "train": train["label"].value_counts(),
        "val": val["label"].value_counts(),
        "test": test["label"].value_counts(),
    }).sort_index()
    counts["total"] = counts.sum(axis=1)
    for s in ["train", "val", "test"]:
        counts[f"{s}_%"] = (100 * counts[s] / counts["total"]).round(1)
    counts.loc["ALL"] = counts[["train", "val", "test", "total"]].sum().tolist() + [
        round(100 * len(d) / len(data), 1) for d in (train, val, test)]
    return train, val, test, counts


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--out-dir", default="results/task1")
    parser.add_argument("--processed-dir", default="data/processed")
    parser.add_argument("--quat-dir", default="data/quatlogs")
    args = parser.parse_args()

    out_dir, proc_dir = Path(args.out_dir), Path(args.processed_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)

    print("Loading recordings ...")
    data, quat_source = load_dataset(args.raw_dir)

    # Quaternion exports are separate takes. Keep their timestamps and split independently.
    from model_quaternion_fe import load_recording as load_quat
    quaternion_frames = []
    for label in LABEL_MAP.values():
        path = Path(args.quat_dir) / f"{label}_Q.csv"
        measured = load_quat(path, label)
        original = pd.read_csv(path, comment="#")
        values = original[QUAT_COLS].apply(pd.to_numeric, errors="coerce")
        valid = np.isfinite(values).all(axis=1) & ((values ** 2).sum(axis=1) > 0)
        # Use the same valid rows for timestamps and quaternion values to keep them aligned.
        t = original.loc[valid, "time[us]"].to_numpy(dtype=float)
        measured["t"] = (t - t[0]) / 1e6
        quaternion_frames.append(measured)
    quaternion_data = pd.concat(quaternion_frames, ignore_index=True)
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), layout="constrained")
    for ax, (label, frame) in zip(axes, quaternion_data.groupby("label")):
        segment = frame[frame["t"] <= 5]
        ax.plot(segment["t"], segment[QUAT_COLS])
        ax.set(title=label, xlabel="Time (s)", ylabel="Logged quaternion")
        ax.legend(QUAT_COLS, ncol=4)
    fig.savefig(out_dir / "logged_quaternion_examples.png", dpi=150)
    plt.close(fig)
    q_train, q_val, q_test, q_counts = stratified_split(quaternion_data)
    q_counts.to_csv(out_dir / "quaternion_split_counts.csv")
    sampling_report(quaternion_data).to_csv(out_dir / "quaternion_sampling.csv", index=False)
    quaternion_data.groupby("label")[QUAT_COLS].agg(["mean", "std", "min", "max"]).to_csv(
        out_dir / "logged_quaternion_statistics.csv")
    for split, frame in zip(("full", "train", "val", "test"), (quaternion_data, q_train, q_val, q_test)):
        frame.to_csv(proc_dir / f"quaternion_{split}.csv", index=False)
    print("\nComputing statistics ...")
    sampling = sampling_report(data)
    sampling["quaternion_source"] = sampling["file"].map(quat_source)
    stats = per_class_stats(data)
    ranges = feature_ranges(data)
    dyn = dominant_frequencies(data)
    summary = data.groupby("label").agg(
        samples=("t", "size"), recordings=("source_file", "nunique"))
    span = data.groupby(["label", "source_file"])["t"].agg(lambda t: t.max() - t.min())
    summary["duration_s"] = span.groupby("label").sum().round(1)
    summary["percent"] = (100 * summary["samples"] / len(data)).round(1)

    sampling.to_csv(out_dir / "sampling_report.csv", index=False)
    stats.to_csv(out_dir / "per_class_statistics.csv")
    ranges.to_csv(out_dir / "feature_ranges.csv")
    dyn.to_csv(out_dir / "temporal_dynamics.csv", index=False)
    summary.to_csv(out_dir / "dataset_summary.csv")

    print("Plotting ...")
    plot_full_timeseries(data, out_dir)
    plot_activity_samples(data, out_dir)
    plot_class_distribution(data, out_dir)
    plot_feature_boxplots(data, out_dir)
    plot_spectra(data, out_dir)

    print("Splitting 70/15/15 (stratified) ...")
    train, val, test, split_counts = stratified_split(data)
    split_counts.to_csv(out_dir / "split_counts.csv")
    plot_split(split_counts.drop(index="ALL"), out_dir)
    cols = ["source_file", "t", "label"] + FEATURES
    data[cols].to_csv(proc_dir / "dataset_full.csv", index=False)
    train[cols].to_csv(proc_dir / "train.csv", index=False)
    val[cols].to_csv(proc_dir / "val.csv", index=False)
    test[cols].to_csv(proc_dir / "test.csv", index=False)

    # Markdown summary you can paste into the report
    with open(out_dir / "task1_summary.md", "w") as f:
        f.write("# Task 1 - Dataset summary\n\n")
        f.write(f"Total samples: **{len(data)}**, classes: "
                f"**{data['label'].nunique()}**, recordings: "
                f"**{data['source_file'].nunique()}**\n\n")
        for title, df in [("Per-class distribution", summary),
                          ("Sampling / timing check", sampling.set_index("file")),
                          ("Feature ranges (all data)", ranges),
                          ("Temporal dynamics", dyn.set_index("label")),
                          ("Stratified split", split_counts)]:
            f.write(f"## {title}\n\n{df.to_string()}\n\n")
        f.write("## Per-class statistics\n\n")
        for feat in FEATURES:
            f.write(f"### {feat}\n\n{stats[feat].to_string()}\n\n")

    pd.set_option("display.width", 160)
    print("\n=== Dataset summary ===\n", summary)
    print("\n=== Sampling check ===\n", sampling.to_string(index=False))
    print("\n=== Temporal dynamics ===\n", dyn.to_string(index=False))
    print("\n=== Stratified split ===\n", split_counts)
    print(f"\nFigures and tables -> {out_dir}/\nSplit CSVs         -> {proc_dir}/")


if __name__ == "__main__":
    main()
