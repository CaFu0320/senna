# ECG 677 — Design Assignment 3 (Tasks 1 and 2)

## Submission package with the five requested Python scripts

This folder combines the two uploaded, previously working DA3 packages. **The original models, datasets, and their existing evaluation outputs are copied without retraining or overwriting them.** The five named scripts in the project root are independently executable and include comments/docstrings. For reproducibility, their model-training portions call the original, documented implementations preserved in `src/backends/`.

| Required file | What you can execute | Where new outputs go |
|---|---|---|
| `data_prep.py` | Data quality, Task 1 statistical features, Task 2 STFT plots and ANOVA bin selection | `results/preprocessing/` |
| `nn_quat_train.py` | Train the Task 1 16-input Float32 network, quantize it, and report its performance | `results/retrained/task1/` |
| `nn_tf_2d_train.py` | Train the Task 2 12×13×4 CNN, quantize it, and report its performance | `results/retrained/task2/` |
| `quantize_models.py` | Separately quantize saved Float32 models to full-Int8 TFLite (and export the Task 2 Float32 TFLite) | `results/requantized/` |
| `evaluation.py` | Run both networks on saved held-out sets, export metrics and side-by-side confusion matrices | `results/evaluation/` |

## Fastest way to verify everything without retraining

Open **Windows PowerShell** in the extracted `DA3_Submission_Organized` folder:

```powershell
python -m pip install -r requirements.txt
python data_prep.py --task both
python evaluation.py --verify-only
python evaluation.py --task both
```

The last command runs the **supplied, already-trained models**, not new models. It regenerates Float32/Int8 accuracy, precision/recall/F1, prediction CSVs, and confusion matrices from exactly the held-out windows used in each original training run.

### Optional: recreate training, then quantize independently

```powershell
python nn_quat_train.py
python nn_tf_2d_train.py
python quantize_models.py --task both --source original
python evaluation.py --task both --int8-source requantized
```

- The two trainers **also perform Int8 quantization internally**, as they did when you got the successful results in November 2026. `quantize_models.py` exists as the separately required *re-runnable quantization step*; it is not necessary to rerun the trainers to satisfy that step.
- Running the two trainers again can yield slightly different model accuracy, weights, and benchmarks because TensorFlow versions and training nondeterminism can change. Newly trained models go under `results/retrained/` and must be **rebenchmarked in AI Studio** if you intend to report their new hardware performance.
- `quantize_models.py --source original` writes fresh models without replacing the original 2026 on-target-tested model files. You can evaluate fresh quantization with `evaluation.py --int8-source requantized`. To quantize re-trained models instead, use `--source retrained` and evaluate using `evaluation.py --source retrained --int8-source requantized`.
- The original Task 2 H5 contains an embedded Keras `Rescaling` layer, which **was rejected by ST Edge AI Core**. Use the already-verified `models/task2/quaternion_tfr_float32_cubeai.tflite` for the original Float32 CubeAI result. Independent quantization also exports a Float32 TFLite for newly processed models.

### Preparation settings

- 15 CSV recordings: 5 × `static`, 5 × `leftrighttilt`, 5 × `updowntilt`.
- Quaternion columns `q0,q1,q2,q3`; `elapsed_s` timestamps, ~10.07 Hz.
- Both tasks use 128-sample windows, 64-sample step; **recording-level** train/validation/test splits, never random overlapping-window splits.
- Task 1 uses statistical quaternion/time-frequency features with **ANOVA top 16**; samples: 81 train, 27 validation, 27 test. The original Task 1 window extraction also includes each trial's trailing full window.
- Task 2 uses **Hann STFT, 32-sample frames, hop 8, FFT size 32**, with **12 of 17 frequency bins** selected by training-only ANOVA, giving a **12 × 13 × 4** input. `--no-pad-last-window` gives 72 train, 24 validation, 24 test windows.
- The Task 2 input is **precomputed STFT spectrograms**, NOT raw IMU or quaternion streams. Sensor acquisition and STFT preprocessing must be implemented separately for a live-board demonstration.

### Original artifacts and provenance

- `data/raw/`: the 15 uploaded original CSV files, one trial per recording.
- `models/task1/`: original Float32 and Int8 models from the uploaded Task 1 ZIP.
- `models/task2/`: original Float32 H5, CubeAI-compatible Float32 TFLite, and Int8 TFLite from the uploaded Task 2 ZIP.
- `data/derived/`: original training-only representative calibration arrays, original selected input features/frequencies, and reproducible held-out evaluation tensors (features calculated by the original backend; no model retraining).
- `results/original/task1` and `results/original/task2`: all existing training metrics, confusion plots, and selected-feature files from the provided ZIPs.
- `results/preprocessing`: executed preprocessing and plots from this organized package.
- `src/backends/task1_original.py`: untouched training implementation originally named `nn_quat_train_DA3_fixed.py`.
- `src/backends/task2_original.py`: untouched training implementation originally named `nn_tf_2d_train.py` in Task 2 source package.
- `src/tools/fix_cubeai_float32_original.py`: original fix used to export the Float32 ST-Edge-compatible model (historical reference).
- `docs/sha256_original_artifacts.json`: SHA256 integrity checks for models and derived tensors.
- `docs/hardware_comparison.csv` and `docs/engineering_comparison.md`: report-ready benchmark reference.

## What was verified when constructing this ZIP

1. All five scripts and the two original backends passed Python syntax compilation.
2. `python data_prep.py --task both` executed successfully and generated real Task 1 and Task 2 prepared outputs.
3. Task 1 feature values and its selected 16 features matched the supplied training artifact; Task 2 STFT tensor values, bin selections, and recording labels matched the supplied original data **exactly** in the available Python environment.
4. `python evaluation.py --verify-only` succeeded and confirmed no recording overlap between train, validation, and test for either task.
5. Model training, independent Int8 quantization, and TensorFlow-based reevaluation **were not rerun in the package-building environment** because TensorFlow is not installed there. Those steps are ready for execution in the Windows environment where you successfully trained the models.

## Still needed for complete assignment submission

Collect together the actual AI Studio screenshots/reports, final PDF report, Github repository URL, and YouTube playlist. The included Python package does not pretend to provide a live on-device sensor-to-STFT-to-CNN implementation. CubeAI's 100% random-input original/optimized agreement is **not** equivalent to 100% sensor classification accuracy.
