# DA2 ECG677

This package uses three activities: Curl, LateralRaise, and LeftPunch. It includes the six original CSV exports (renamed for consistent class labels), revised source scripts, and newly generated results and model exports.

## Reproduce

From this folder, run:

```sh
python -m pip install -r requirements.txt
python run_all.py
```

Task 1 code is in `src/data_preparation.py`. Task 6 software analysis is in `src/comparison_analysis.py`. Start with `docs/task1/task1_summary.md`, `docs/comparison/model_comparison.csv`, and `docs/comparison/decision_matrix.csv`. The model JSON and C/header pairs are in `models/`. Each training script also retains its outputs in its own task folder.

## Data and evaluation

- The files in `data/raw` contain six IMU channels. Task 1 converts mg and mdps to g and dps for analysis and computes an offline Madgwick quaternion for those rows. The raw classifiers retain the logged input units.
- The files in `data/quatlogs` are separate measured quaternion takes. Tasks 4 and 5 use the first copy of the exported q0–q3 columns, preserve their order, and drop zero-norm startup rows. The acquisition export's scalar/vector convention should be verified before connecting a firmware input.
- Task 1 exports class-stratified 70/15/15 splits for both streams. Tasks 2–5 train on chronological 70/15/15 blocks within each recording. Overlapping windows stay within their assigned partition. These tests evaluate held-out portions of the same recordings, with one take per class in each stream.
- The raw LeftPunch file has a 246.42 s discontinuity after the first 404 rows. Task 1 reports both elapsed and active sampling rates. Spectral interpolation is segmented at gaps above 100 ms. RAW+FE skips any window crossing those gaps, including in the block robustness analysis.
- Window size is 42 samples with a stride of 21. The window covers about 0.58 s at the raw stream's active rate near 73 Hz and about 0.42 s in the 100 Hz quaternion stream. Comparisons are across different takes, rates, and input units (rows versus windows).
- Task 5 uses ANOVA scores for reporting and random-forest RFE to keep eight of 24 quaternion features. RFE is fit on training windows and repeated inside each block holdout fold.
- JSON size describes the serialized model. The comparison's tree storage estimate assumes 20 bytes per generated C node under ordinary 32-bit alignment. Window RAM covers the float32 input buffer. These figures exclude code, stack, and other scratch storage. MCU tree traversal times are analytical estimates.
- Task 6 includes the software comparison and C exports.

## Report and AlgoBuilder projects

- `DA2 ECG677.pdf` is the submission report. `DA2_Exercise_Report.docx` is the editable version.
- `algobuilder/da2task4and5.json` and `algobuilder/da2task7.json` are the supplied MEMS Studio project exports. Both files are preserved as exported.
- The Task 7 graph refers to a compiled `ispu.json` via a path from the original computer. On another machine, build the ISPU project and select the generated `ispu.json` again in the graph's ISPU block.

## Task 7 ISPU project

- `task7/README_START_HERE.md` describes the build and verification workflow.
- `task7/ISPU_208hz/` contains the firmware source, generated C tree, and build configuration. The training inputs, model, and offline validation artifacts are in `task7/data/`, `task7/models/`, and `task7/docs/`.
- Add your Task 7 hardware results or demo link under `task7/docs/`.

Extract this ZIP, then upload the contents of the enclosed `DA2 ECG677` folder to the existing GitHub assignment folder.
