#!/usr/bin/env python3
"""DA3 required script #3: reproduce Task 2 2D STFT-CNN training.

Preserves the teammate's trained network architecture, ANOVA frequency ranking,
training/validation/test group splitting, and complete int8 conversion. The
--no-pad-last-window option matches the SUCCESSFUL saved Task 2 experiment.
Usage: python nn_tf_2d_train.py
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from data_prep import ROOT, recordings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    output = ROOT / "results/retrained/task2"
    output.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROOT / "src/backends/task2_original.py"),
           "--csv", *map(str, sorted(recordings())), "--output-dir", str(output),
           "--window-size", "128", "--step-size", "64", "--stft-frame-length", "32",
           "--stft-hop-length", "8", "--n-fft", "32", "--top-frequency-bins", "12",
           "--no-pad-last-window", "--seed", "42", "--epochs", str(args.epochs),
           "--batch-size", str(args.batch_size)]
    print("[TRAIN] Task 2: 4-channel quaternion STFT -> Float32 + Int8 CNN", flush=True)
    subprocess.run(cmd, check=True)
    print(f"[DONE] New Task 2 models saved in {output}")
    print("Note: to deploy a newly retrained Float32 CNN, convert that H5 model to Float32 TFLite.")


if __name__ == "__main__":
    main()
