#!/usr/bin/env python3
"""Export DA3 Task 2 Float32 CNN in STM32Cube AI Studio-friendly formats.

Run this script from the root of DA3_Task2_Start_Package after training:
    py fix_cubeai_float32.py

Does not retrain or modify the original model.

Primary output:
    results/training/quaternion_tfr_float32_cubeai.tflite
    - The existing Rescaling operation is represented as TFLite operators.
    - Input is the ORIGINAL raw log-power STFT tensor (12, 13, 4).

Fallback output:
    results/training/quaternion_tfr_float32_no_rescaling.h5
    - The unsupported Keras Rescaling layer has been removed.
    - IMPORTANT: Input now MUST be standardized externally using saved
      values in cubeai_float32_input_scaling.json.

The script also exports held-out test inputs for the two model variants.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf


def main() -> None:
    package_root = Path(__file__).resolve().parent
    training = package_root / "results" / "training"
    original_file = training / "quaternion_tfr_float32.h5"
    raw_data_file = training / "reduced_spectrogram_windows.npz"
    split_file = training / "recording_level_data_split.csv"

    if not original_file.is_file():
        raise FileNotFoundError(
            f"Cannot find {original_file}\n"
            "Put this script in the DA3_Task2_Start_Package root directory, "
            "alongside run_task2.py."
        )
    model = tf.keras.models.load_model(original_file, compile=False)
    print(f"[LOAD] {original_file}")
    print(f"[MODEL] input={model.input_shape}, output={model.output_shape}")

    rescaling_layers = [
        layer for layer in model.layers
        if isinstance(layer, tf.keras.layers.Rescaling)
    ]
    if len(rescaling_layers) != 1:
        raise RuntimeError(
            "Expected exactly one Keras Rescaling layer as in the supplied Task 2 "
            f"training script, found {len(rescaling_layers)}. Aborting so outputs "
            "cannot be mislabeled."
        )
    rescaling = rescaling_layers[0]
    scale = float(rescaling.scale)
    offset = float(rescaling.offset)

    # Preferred: keep original model's exact input preprocessing inside the
    # exported model, but encode it in TFLite rather than as a Keras Rescaling.
    print("[EXPORT] Converting original Float32 model to TFLite ...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = []  # Float32, not quantized.
    tflite_bytes = converter.convert()
    tflite_path = training / "quaternion_tfr_float32_cubeai.tflite"
    tflite_path.write_bytes(tflite_bytes)
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()
    in_details = interpreter.get_input_details()[0]
    out_details = interpreter.get_output_details()[0]
    if in_details["dtype"] != np.float32 or out_details["dtype"] != np.float32:
        raise RuntimeError("Float32 TFLite conversion did not retain Float32 input/output.")
    print(f"[OK] {tflite_path.name} ({tflite_path.stat().st_size:,} bytes)")
    print(f"     TFLite input: {in_details['shape'].tolist()} {in_details['dtype']}")

    # Fallback: rewire the already-trained layers around Rescaling. This
    # preserves original trained weights; NO retraining takes place.
    new_input = tf.keras.Input(
        shape=tuple(model.input_shape[1:]), name="externally_standardized_spectrogram"
    )
    x = new_input
    for layer in model.layers:
        if isinstance(layer, (tf.keras.layers.InputLayer, tf.keras.layers.Rescaling)):
            continue
        x = layer(x)
    fallback_model = tf.keras.Model(new_input, x, name="quat_tfr_cnn_no_rescaling")
    fallback_path = training / "quaternion_tfr_float32_no_rescaling.h5"
    fallback_model.save(fallback_path)
    print(f"[OK] {fallback_path.name} ({fallback_path.stat().st_size:,} bytes)")

    scaling_path = training / "cubeai_float32_input_scaling.json"
    scaling_path.write_text(
        json.dumps(
            {
                "primary_tflite_model": tflite_path.name,
                "primary_tflite_input": "raw log-power spectrogram, as with original .h5",
                "fallback_h5_model": fallback_path.name,
                "fallback_h5_input": "pre-standardized log-power spectrogram",
                "fallback_h5_input_formula": "X_standardized = X_raw * scale + offset",
                "scale": scale,
                "offset": offset,
                "input_layout": "frequency x time x quaternion channel",
                "note": "Use the same preprocessing for deployment and validation. "
                        "The fallback .h5 requires external scaling; TFLite does not.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Verify mathematical equivalence against held-out test windows when available.
    if raw_data_file.is_file() and split_file.is_file():
        with np.load(raw_data_file, allow_pickle=False) as data:
            all_X = data["X"].astype(np.float32)
        table = pd.read_csv(split_file)
        test_indices = table.loc[
            table["split"].astype(str).str.lower() == "test", "window_index"
        ].to_numpy(dtype=int)
        if not len(test_indices):
            print("[WARN] No test indices found; skipping data-backed comparison.")
            return
        X = all_X[test_indices]
        X_norm = (X * np.float32(scale) + np.float32(offset)).astype(np.float32)
        raw_samples_path = training / "cubeai_float32_tflite_test_inputs.npy"
        normalized_samples_path = training / "cubeai_float32_h5_normalized_test_inputs.npy"
        np.save(raw_samples_path, X)
        np.save(normalized_samples_path, X_norm)

        y_original = model.predict(X, verbose=0)
        y_fallback = fallback_model.predict(X_norm, verbose=0)
        tflite_out = []
        for sample in X:
            interpreter.set_tensor(in_details["index"], sample[np.newaxis, ...])
            interpreter.invoke()
            tflite_out.append(interpreter.get_tensor(out_details["index"])[0])
        y_tflite = np.stack(tflite_out)
        delta_tflite = float(np.max(np.abs(y_original - y_tflite)))
        delta_h5 = float(np.max(np.abs(y_original - y_fallback)))
        labels_match_tflite = bool(
            np.array_equal(np.argmax(y_original, axis=1), np.argmax(y_tflite, axis=1))
        )
        labels_match_h5 = bool(
            np.array_equal(np.argmax(y_original, axis=1), np.argmax(y_fallback, axis=1))
        )
        print(f"[VERIFY] {len(X)} held-out test windows")
        print(f"         Float32 TFLite max probability difference: {delta_tflite:.8g}")
        print(f"         No-Rescaling .h5 max probability difference: {delta_h5:.8g}")
        print(f"         Identical predicted labels? TFLite={labels_match_tflite}, H5={labels_match_h5}")
        print(f"[DATA] {raw_samples_path.name} -> use with .tflite")
        print(f"[DATA] {normalized_samples_path.name} -> use with no_rescaling.h5")
        if not labels_match_tflite or not labels_match_h5:
            raise RuntimeError("New model predictions differ from the original on test data.")
    else:
        print("[NOTE] Training dataset not present; conversion succeeded but data comparison skipped.")

    print("\n[NEXT] Import quaternion_tfr_float32_cubeai.tflite into STM32Cube AI Studio.")
    print("       If it fails, try quaternion_tfr_float32_no_rescaling.h5")
    print("       using external input scaling described in the JSON file.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
