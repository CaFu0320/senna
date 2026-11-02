# Outline for the six videos (playlist "EMBSEC&ML DA2", about 3-5 minutes each)

1. **Task 1 (DPEA)** - show `data/raw/*.csv` (columns, mg / mdps units, quaternion), run `python data_preparation.py ...`, show
   `docs/task1/` (time-series plots, statistics table, class distribution, split counts) and the trimming / stratified split code.
2. **Task 2 (RAW)** - run `model_raw.py`; console output (accuracy per set, depth, leaves), confusion matrix and importance
   plots in `docs/task2/`, `models/RAW/decision_tree_raw.json`.
3. **Task 3 (RAW+FE)** - the six window statistics (42-sample window, 36 features), run `model_raw_fe.py`, complexity comparison
   with Task 2 (`docs/task3/complexity_comparison.csv`), `models/RAW_FE/decision_tree_raw_fe.json`.
4. **Task 4 (QUAT)** - run `model_quaternion.py`; why 75 % on the test block (orientation drift, Table of class means),
   `models/QUAT/decision_tree_quaternion.json`.
5. **Task 5 (QUAT+FE)** - ANOVA table and RFE ranking (`docs/task5/`, `docs/feature_extraction_and_rfe.md`), run
   `model_quaternion_fe.py`, motion-only versus level features (`docs/robustness/`), `models/QUAT_FE/decision_tree_quaternion_fe.json`.
6. **Task 6 (comparison and insights)** - run `comparison_analysis.py`; `docs/comparison/` (confusion matrices, per-class heatmap,
   leave-one-block-out robustness, accuracy against memory), the insights and the recommendation.
