#!/usr/bin/env python3
"""DA3 required script #4: independent Float32 -> full-integer Int8 conversion.

The original trainers already quantized both original models. This script
REPRODUCES quantization as an independently executable deliverable, calibrating
from TRAINING data only and writing new results without overwriting models that
were previously used for CubeAI benchmarks.
Usage: python quantize_models.py --task both
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from data_prep import ROOT


def paths_for(task: str, source: str) -> tuple[Path, Path, Path, str]:
    """Resolve model and matching calibration arrays for each training run."""
    original = source == "original"
    base = (ROOT / f"models/{task}") if original else (ROOT / f"results/retrained/{task}")
    if task == "task1":
        model = base / "quaternion_float32.h5"
        calibration = (ROOT / "data/derived/task1_training_calibration.npz") if original else (base / "cubeai_quantization_dataset.npz")
        key = "x_test"  # Historical name: original trainer actually saves TRAINING calibration windows.
    else:
        model = base / "quaternion_tfr_float32.h5"
        calibration = (ROOT / "data/derived/task2_training_calibration.npz") if original else (base / "cubeai_representative_spectrograms.npz")
        key = "spectrograms"
    output = ROOT / f"results/requantized/{source}/{task}"
    return model, calibration, output, key


def quantize(task: str, source: str) -> None:
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise SystemExit("TensorFlow is required: python -m pip install -r requirements.txt") from exc
    path, calibration_path, folder, key = paths_for(task, source)
    if not path.exists() or not calibration_path.exists():
        raise FileNotFoundError(f"Missing model or calibration file: {path}, {calibration_path}")
    folder.mkdir(parents=True, exist_ok=True)
    data = np.load(calibration_path)[key].astype(np.float32)
    model = tf.keras.models.load_model(str(path), compile=False)
    expected_shape = tuple(int(v) for v in model.input_shape[1:])
    if data.ndim != len(expected_shape) + 1 or tuple(data.shape[1:]) != expected_shape:
        raise ValueError(f"Calibration data {data.shape} do not match model (batch, {expected_shape})")
    # Full-int8 post-training quantization. Only training recordings supply ranges.
    def representative_dataset():
        for one in data:
            yield [one[np.newaxis, ...].astype(np.float32)]
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    result = converter.convert()
    int8_path = folder / f"{task}_requantized_int8.tflite"
    int8_path.write_bytes(result)
    interpreter = tf.lite.Interpreter(model_content=result)
    interpreter.allocate_tensors()
    inp, out = interpreter.get_input_details()[0], interpreter.get_output_details()[0]
    if np.dtype(inp['dtype']) != np.dtype('int8') or np.dtype(out['dtype']) != np.dtype('int8'):
        raise RuntimeError("The new TFLite model does not have Int8 input and output.")
    info = {"task": task, "source": source, "original_model": str(path.relative_to(ROOT)),
            "representative_data": str(calibration_path.relative_to(ROOT)),
            "representative_count": int(len(data)), "model_file": int8_path.name,
            "model_size_bytes": len(result),
            "input_shape": inp['shape'].astype(int).tolist(),
            "output_shape": out['shape'].astype(int).tolist(),
            "input_scale_zero": [float(inp['quantization'][0]), int(inp['quantization'][1])],
            "output_scale_zero": [float(out['quantization'][0]), int(out['quantization'][1])]}
    (folder / "quantization_manifest.json").write_text(json.dumps(info, indent=2))
    print(f"[DONE] {task}: saved {int8_path} ({len(result)} bytes)")
    if task == "task2":
        # Floating-point TFLite is needed for ST Edge AI when H5 Rescaling is unsupported.
        fp_converter = tf.lite.TFLiteConverter.from_keras_model(model)
        float_bytes = fp_converter.convert()
        float_path = folder / "quaternion_tfr_float32_cubeai.tflite"
        float_path.write_bytes(float_bytes)
        print(f"[DONE] Float32 TFLite for ST Edge AI saved to {float_path}")
    print("Important: these are NEW model files; rerun STM32Cube AI if using them for hardware comparisons.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", choices=["task1", "task2", "both"], default="both")
    ap.add_argument("--source", choices=["original", "retrained"], default="original")
    args = ap.parse_args()
    for task in (["task1", "task2"] if args.task == "both" else [args.task]):
        quantize(task, args.source)


if __name__ == "__main__":
    main()
