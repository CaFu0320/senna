#!/usr/bin/env python3
"""DA3 required script #2: reproduce Task 1 statistical-quaternion NN training.

Runs the supplied, proven Task 1 backend with its original settings, including
ANOVA selection, float training, full-int8 calibration, and testing. New results
are stored separately to protect the models already benchmarked in CubeAI.
Usage: python nn_quat_train.py
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
from data_prep import ROOT, recordings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    output = ROOT / "results/retrained/task1"
    output.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROOT / "src/backends/task1_original.py"),
           "--csv", *map(str, recordings()), "--output-dir", str(output),
           "--timestamp-column", "elapsed_s", "--window-size", "128", "--step-size", "64",
           "--top-k", "16", "--selection", "anova", "--seed", "42",
           "--epochs", str(args.epochs), "--batch-size", str(args.batch_size)]
    print("[TRAIN] Task 1: quaternion statistical features -> Float32 + Int8", flush=True)
    subprocess.run(cmd, check=True)
    print(f"[DONE] New Task 1 models saved in {output}")


if __name__ == "__main__":
    main()
