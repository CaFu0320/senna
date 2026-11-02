# Task 7 — Retrained QUAT+FE at measured 120 Hz

## What this package is

An **experimental** activity classifier for the LSM6DSO16IS ISPU based on new recordings from the *stable 208-Hz 6-axis Madgwick filter*. A 120-Hz STM32/MEMS Studio timer stream was independently confirmed from CSV timestamps. It is **not** an externally validated or hardware-benchmarked classifier yet.

Your original Task 5 model is not overwritten. This is the **Task 7 adaptation**.

## Training data

Each uploaded CSV contained **two sessions appended together**: an earlier ~100 Hz recording and a later ~120 Hz recording. The training script uses **only the last ~120 Hz session** in each file. Clean versions are in `data/*_clean_120hz.csv`.

| Label | New samples | Duration | Measured Hz |
|---|---:|---:|---:|
| Horizontal (0) | 3,655 | 30.321 s | 120.51 |
| Static (1) | 3,653 | 30.312 s | 120.48 |
| Vertical (2) | 3,659 | 30.361 s | 120.48 |

A single corrupted-norm sample in Horizontal caused **two overlapping 42-sample windows** to be excluded. The CSVs are rounded to three decimals; that rounding reduces precision for very small features.

## Model and evaluation

- Sensor quaternions are **q1=x, q2=y, q3=z, q4=w** in the recording; model uses **q0=w, q1=x, q2=y, q3=z**.
- Window: **42 samples**, stride **21 samples** (about 0.35 s per window / a new decision every 0.175 s at 120 Hz).
- All original **24 Task 5 statistical features** are computed (`mean,var,max,min,p2p,energy` × 4).
- Standard **random-forest RFE → 8 features** is retained as a baseline. That model scored **53/78 = 67.95%** on the last chronological portion of the same recordings.
- The recommended *motion-sensitive feature-selection adaptation* keeps **eight quaternion-only features**: population variance and peak-to-peak for q0, q1, q2, q3. The tree uses a subset of these eight features.
- Selected adaptation: **17 nodes, 9 leaves, depth 4**. Training **288/307 = 93.81%**, validation **75/78 = 96.15%**, final chronological test **75/78 = 96.15%**.
- **WARNING:** There is only one new 120-Hz recording per class. Validation and test windows are different, time-separated portions of the same recordings, *not independent sessions*. The candidate features and models were explored using this data. These figures **do not demonstrate robust deployment accuracy**. Fresh trials in different orientations are essential.
- Window feature calculation and decision tree have been tested with desktop GCC; **463/463** windows had the same decisions as JSON/Python when using C-equivalent float32 feature arithmetic. **The ISPU STRED compilation and on-board predictions remain unverified.**

## What to build in MEMS Studio

1. Open **Advanced Features → ISPU IDE**.
2. Open the **`ISPU_208hz`** top-level directory as an ISPU project (not just the `make` folder). Confirm `src/main.c`, `src/fusion_core.c`, `src/madgwick.c`, `src/quat_fe_tree.c`, `meta.txt`, `conf.txt` and `make/Makefile` are present.
3. Open `make/Makefile` and click **Build**. Successful compilation generates `ISPU_208hz/make/bin/ispu.json`.
4. In **AlgoBuilder**, make a copy of the working stable Madgwick design. Change the ISPU block's **Configuration File** to the new `make/bin/ispu.json` and refresh the block's output pins.
5. Reconnect the four quaternions (`Quat x`, `Quat y`, `Quat z`, `Quat w scalar`) to your float Mux and Graph. Connect **`Activity class id`** to a **Value** block. Connect **`Prediction counter`** to a separate Value block if you want to check updates.
6. In Sensor Hub, keep **Timer, 120 Hz, 8 g, 2000 dps**. Generate the STM32F401RE firmware, program, and reconnect.
7. Leave the board still until **Calibration status = 2**, then allow 42 exported samples (~0.35 seconds) before expecting an activity ID. `255` = not ready; `0` = Horizontal, `1` = Static, `2` = Vertical.
8. Test motion without deliberately changing the board's orientation, then repeat static in multiple different orientations. Save logs **with ground-truth activity labels** for each independent trial.

The ISPU processes motion samples at native **208 Hz**. A 120/208 phase accumulator inside this C program selects approximately **120 quaternion samples per second for the decision-tree window**, while the **STM32 Sensor Hub timer at 120 Hz** exports the latest quaternion and class ID. This is **not** a claim of native 120-Hz ISPU operation or guaranteed phase alignment between independent clocks.

## Data and code files

- `data/`: original appended CSV files and extracted clean 120-Hz sessions.
- `src/retrain_task7.py`: reproduce segmentation, feature extraction, training, model conversion, and plots. Run `python src/retrain_task7.py` from any directory with numpy, pandas, matplotlib, scikit-learn installed.
- `models/decision_tree_task7_120hz_motion_fe.json`: recommended model with compact nodes and feature ordering.
- `models/decision_tree_task7_120hz_rfe_baseline.json`: baseline comparison model (not deployed).
- `ISPU_208hz/src/`: stable calibration-aware Madgwick from your successful project, plus the new `quat_fe_tree.c/.h` and integrated `main.c`.
- `tests/verify_c_matches_python.py`: desktop host test, requires GCC, numpy, pandas.
- `docs/`: confusion matrices, tree image, feature-window CSV, JSON metrics, and report text.

## Still required to satisfy the full Task 7

- Successful **STRED ISPU compilation** and hardware activity classifications on all three ground-truth motions.
- **STM32 UART 921600-baud** configuration verification, and explicit polling/interrupt evidence.
- Fresh **labeled** test sessions and confusion matrix / agreement percentage under changed orientations.
- Measured or defensibly estimated **ISPU latency, memory (from stred-size), power, CPU cycles**, STM32 cost and a reference benchmark.
- Submission evidence, GitHub source files, screenshots, report insertion and required demonstration videos.

A high same-session score does not establish recognition of pure translation: quaternion values represent orientation. Translation without orientation change may be indistinguishable from static movement using only quaternions. The output `Leaf training purity` is **not calibrated confidence**.
