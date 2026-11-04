# ECG677 / CPE477 — Task 7: Curl, Lateral Raise, Left Punch (ISPU QUAT+FE)

## 1. What is ready and what is not

**Ready:** Retrained decision tree (JSON), embedded C decision tree (`quat_fe_tree.c/.h`), updated full **ISPU firmware source** in `ISPU_208hz/src`, sensor-fusion code, MEMS Studio metadata/config, a Python retraining script, model validation, and live-test evaluator. This archive contains **no old compiled `ispu.json`**; a previous firmware image would have the wrong model and labels. Compile this source yourself using the **MEMS Studio ISPU IDE's STRED toolchain**, then use the NEW resulting `make/bin/ispu.json` in AlgoBuilder.

**Not verified here:** STRED target build (compiler unavailable in this environment); flashing the STM32; live ISPU predictions; 921600-baud STM32 UART integration; real hardware latency/power. Host GCC C syntax and C-versus-Python tests passed, but do not prove that the board works.

## 2. Exact labels / output

| Activity | `Activity class id` |
|---|---:|
| Curl | **0** |
| Lateral raise | **1** |
| Left punch | **2** |
| Not ready (startup/calibration) | **255** |

- The `Activity Number` column in ALL THREE training CSVs is **stale output from the old classifier** (0s and 2s). It is ignored. Every training label is taken from the corresponding filename.
- 6-axis Madgwick quaternion output from the ISPU: `[q1=x, q2=y, q3=z, q4=w]` in MEMS Studio CSV. The classifier internally uses `[w,x,y,z]`.
- Sensors configured via `conf.txt`: LSM6DSO16IS native ISPU 208 Hz, accelerometer ±8 g, gyro ±2000 dps; software selects ~120 quaternion frames/s. MEMS Studio Sensor Hub CSV export was measured at **120.48 Hz**. Don't confuse exported rates with native ISPU rates.
- Window **42 samples (~0.35 s)**, hop **21 samples (~0.175 s)**. The first class prediction appears after successful calibration + 42 selected frames. A new decision then arrives every 21 selected frames.

## 3. Why the new model uses different features

The original 8 absolute-quaternion variance/peak-to-peak features tested poorly on these exercises (about 59.0% chronological test accuracy in an initial internal comparison). An absolute-component tree reached 97.1% by relying almost entirely on recording orientation (`q3__max` and `q3__mean`). That would be easy to break in a different initial pose or workout session, so **that shortcut model is NOT deployed**.

Instead the deployed model uses **relative quaternion dynamics**, explicitly subtracting/undoing the first sample's orientation in each 42-sample window. Candidate features are 36 statistics: mean, population variance, max, min, peak-to-peak and mean-square energy of four relative quaternion components, plus squared frame-to-frame change and squared change from the first quaternion. The decision tree actually uses only 8 of those candidate features. The tree is 19 nodes / 10 leaves / depth 4. The relative feature pipeline is invariant under a fixed global rotation (subject to float precision and quaternion sign continuity).

**Critical implementation detail:** Relative features require ordered samples! `main.c` now passes the **oldest ring index** to `quatfe_window_features()`. Do not replace it with the old 2-argument function; that function expected order-insensitive features.

## 4. What the recorded data really supports

Each provided file is just one 40-second session of a different activity. A time-ordered split *within each recording* was used: 60% train; 5% gap; 15% validation; 5% gap; 15% test. Neighboring overlapping windows do not cross these gaps. We discarded 8 windows containing rare abnormal quaternion norms (>5% from unity); no data was invented.

| Split | Correct / windows | Accuracy |
|---|---:|---:|
| Train | 405 / 410 | 98.78% |
| Validation | 98 / 100 | 98.00% |
| Test | **102 / 105** | **97.14%** |

Test confusion matrix (rows: actual, columns: predicted; Curl / Lateral / Punch):

```text
                  Curl  Lateral  Punch
True Curl           35       0      0
True Lateral         0      35      0
True Punch           2       1     32
```

**This is same-session holdout performance, NOT independent live accuracy.** Accuracy may drop on fresh repetitions, different users, different sensor mounts, faster movements, or quaternion sign changes. Please collect new independent recordings for a defensible confusion matrix.

## 5. Build NEW ISPU firmware in MEMS Studio (DO THIS FIRST)

1. Unzip this archive locally. Open **MEMS Studio → Advanced Features → ISPU IDE**.
2. Open `ISPU_208hz` as an **ISPU project** (the parent directory containing `src`, `meta.txt`, `conf.txt`, `make/Makefile` and `ispu_utils`), NOT the old project from last week.
3. Confirm the source contains `src/main.c`, `src/madgwick.c`, `src/fusion_core.c`, **`src/quat_fe_tree.c/.h`**. Verify in `quat_fe_tree.h` that labels say `0=Curl, 1=Lateral raise, 2=Left punch`.
4. In the ISPU IDE, **clean then Build** with the STRED GCC toolchain. Build success should produce **NEW** `ISPU_208hz/make/bin/ispu.json` (and `.h`, `.srec`, map). If you see compiler errors, copy the full console log rather than using the old `ispu.json`.
5. If successful, inspect generated file timestamp, and verify the new model metadata in the resulting output. No compiled bin is pre-supplied, to prevent accidental upload of the obsolete model.

## 6. Integrate in AlgoBuilder and program the board

1. Open the **working AlgoBuilder project** that previously exported the supplied `q1,q2,q3,q4,Activity Number` CSVs; **Save As** a new project name (e.g. `Task7_Curl_LatRaise_Punch`).
2. Select the **ISPU** block → set **Configuration File** to the **new** `ISPU_208hz/make/bin/ispu.json` → refresh the output pins.
3. Keep quaternion outputs in the CSV order **Quat x, Quat y, Quat z, Quat w scalar**. For predictions, route **Activity class id** (uint32) to a **Value** and **Data Log**/table output named `Activity Number` or `Activity class id`. Also expose **Calibration status** and **Prediction counter** in separate Values/Data Table columns.
4. Keep the known working **Sensor Hub / Timer ~120 Hz**, accelerometer full-scale **±8 g**, gyroscope **±2000 dps**. ISPU processing is still natively 208 Hz. Preserve the working NUCLEO-F401RE / X-NUCLEO-IKS4A1 interface configuration.
5. **Generate the STM32 firmware** from AlgoBuilder, build and flash it using the existing working STM32CubeIDE/ST-LINK procedure. If you need a standalone 921600-baud UART stream, see `stm32_integration/` for an integration helper (requires generated firmware connection).
6. Hold the sensor motionless at startup until **Calibration status = 2** (~2 s of stable input). The output remains **255** while calibration and the first 42-sample window are incomplete. **Prediction counter** should advance roughly every 0.175 s when active.
7. Perform curl, lateral raise and left punch, one at a time, with sensor **secured in the same place and orientation** as the training data. Check for 0, 1, and 2 respectively; note time lag and unstable predictions.
8. Record NEW videos/data for each activity in a separate take: include time, q1..q4, *new* activity prediction and preferably prediction counter. Record a ground-truth label **independently** from the firmware prediction; don't treat `Activity Number` itself as ground truth.

**Troubleshooting:**
- Always `255` → check Calibration status: must equal 2; hold sensor still, verify ±8 g/±2000 dps, then check prediction counter.
- Counter increases but old labels/no 1 → confirm the NEW `.json` was generated and set in the ISPU block; rebuild and reflash the AlgoBuilder firmware, not just the ISPU project.
- q values invalid or wildly changing → sensor wiring/scale/fusion issues; test basic quaternion stream before testing the tree.
- Class stays fixed despite changing exercise → model may be memorizing movement patterns specific to the training sessions. Collect independent recordings with multiple mixed exercises and retrain; do not claim success from the same-session 97.14% figure alone.

## 7. Desktop re-training and validation

Install Python dependencies:

```bash
python -m pip install numpy pandas scikit-learn matplotlib
python src/retrain_task7.py
python tests/verify_c_matches_python.py
```

The second command compiles C with **desktop GCC**, tests stored feature values against C using randomized ring starts, and confirms all JSON/C predictions. Results for the included data:

```text
615 recorded windows, 0 C-vs-JSON prediction mismatches
658 wrapped-ring checks; 0 feature mismatches beyond tolerance
123 global orientation rotations; 0 changed predictions
```

The Madgwick fusion core also passed the pre-existing desktop host tests (startup calibration, 90-degree yaw rotation and gravity alignment). GNU11 **syntax check** for all ISPU C files passed. **STRED hardware compilation and live tests remain necessary**.

Test fresh recordings with:

```bash
python tests/evaluate_live_recordings.py --curl curl_live.csv --lateral lateral_live.csv --punch punch_live.csv
```

That script compares logged predictions with independently known actual exercise classes. It defaults to discarding the first 2.5 s of each file; adjust for your test protocol.

## 8. Files to use

- `ISPU_208hz/src/main.c` — ISPU main loop, calibration and predictions.
- `ISPU_208hz/src/quat_fe_tree.c/.h` — new model and on-chip relative feature extraction.
- `ISPU_208hz/src/madgwick.c`, `fusion_core.c` — existing working six-axis quaternion fusion.
- `ISPU_208hz/conf.txt`, `meta.txt`, `make/Makefile` — sensor configuration, ISPU block outputs, build instructions.
- `src/retrain_task7.py` — reproduce the new model from exactly the three provided recordings.
- `models/decision_tree_task7_curl_lat_raise_punch.json` — portable model structure and class mapping.
- `docs/evaluation_results.json`, `docs/task7_confusion_matrix.png`, `docs/task7_decision_tree.png` — analysis/evidence.
- `tests/verify_c_matches_python.py`, `tests/evaluate_live_recordings.py` — desktop QA and live-validation scripts.
- `stm32_integration/task7_uart_helper.c/.h` — optional HAL UART formatter, *not a full STM32 firmware replacement*.

This is an experimental single-user activity model and should not be presented as externally validated or production-ready.
