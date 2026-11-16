#!/usr/bin/env python3
"""DA3 required script #1: data quality, quaternion features, and 2D STFT preparation.

Reuses the ORIGINAL Task 1/Task 2 processing implementations. Preparing data
never retrains or changes any provided model, and the saved data stay untouched.
Usage: python data_prep.py --task both
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
ACTIVITIES = ("static", "leftrighttilt", "updowntilt")


def recordings() -> list[Path]:
    """Return the 15 original, separately labeled trials in a fixed order."""
    paths = [ROOT / "data" / "raw" / f"{activity}{trial}.csv"
             for activity in ACTIVITIES for trial in range(1, 6)]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing CSV recordings:\n" + "\n".join(map(str, missing)))
    return paths


def audit_csvs(paths: list[Path], destination: Path) -> None:
    """Write source-data quality metrics without modifying recordings."""
    rows = []
    for path in paths:
        df = pd.read_csv(path)
        if not set(("q0", "q1", "q2", "q3", "elapsed_s")).issubset(df.columns):
            raise ValueError(f"Invalid columns in {path.name}: {list(df.columns)}")
        q = df[["q0", "q1", "q2", "q3"]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        time = pd.to_numeric(df["elapsed_s"], errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(q).all(axis=1) & np.isfinite(time)
        dt = np.diff(time[valid]); positive = dt[dt > 0]
        rows.append({"recording": path.name, "label": path.stem.rstrip("0123456789"),
                     "rows": len(df), "valid_rows": int(valid.sum()),
                     "invalid_rows": int((~valid).sum()),
                     "nonincreasing_timestamps": int(np.sum(dt <= 0)),
                     "median_sample_rate_hz": float(1 / np.median(positive)) if len(positive) else None,
                     "median_quaternion_norm": float(np.median(np.linalg.norm(q[valid], axis=1))) if valid.any() else None})
    destination.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(destination / "source_quality_report.csv", index=False)
    print(f"[CHECK] {len(rows)} recordings, {sum(r['valid_rows'] for r in rows)} valid quaternion rows")


def run_task_preparation(task: str, paths: list[Path], base: Path) -> None:
    """Execute the same feature/STFT preparation code used for model training."""
    if task == "task1":
        original = ROOT / "src" / "backends" / "task1_original.py"
        command = [sys.executable, str(original), "--csv", *map(str, paths),
                   "--output-dir", str(base / task), "--timestamp-column", "elapsed_s",
                   "--window-size", "128", "--step-size", "64", "--top-k", "16",
                   "--selection", "anova", "--seed", "42", "--prepare-only"]
    else:
        original = ROOT / "src" / "backends" / "task2_original.py"
        command = [sys.executable, str(original), "--csv", *map(str, sorted(paths)),
                   "--output-dir", str(base / task), "--window-size", "128", "--step-size", "64",
                   "--stft-frame-length", "32", "--stft-hop-length", "8", "--n-fft", "32",
                   "--top-frequency-bins", "12", "--seed", "42",
                   "--no-pad-last-window", "--prepare-only"]
    print(f"\n[PREPARE] {task}", flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=["task1", "task2", "both"], default="both")
    args = parser.parse_args()
    data = recordings()
    destination = ROOT / "results" / "preprocessing"
    audit_csvs(data, destination)
    for task in (["task1", "task2"] if args.task == "both" else [args.task]):
        run_task_preparation(task, data, destination)
    print("\n[DONE] All requested preprocessing complete. Existing trained models were not changed.")


if __name__ == "__main__":
    main()
