# Feature extraction and RFE analysis (Tasks 3 and 5)

## Windows
- Window: **42 samples**, stride **21 samples** (50 % overlap). At the effective logging rate of about 71 Hz a window lasts about 0.59 s.
- Windows are cut inside each train / validation / test segment (chronological split), so no window crosses a segment boundary.

## The six statistics (per axis or quaternion component)
| Statistic | Definition |
|---|---|
| mean | average of the window |
| var | variance (divide by n) |
| max, min | extreme values |
| p2p | peak-to-peak = max - min |
| energy | mean of the squared values (sum of squares / n) |

- **Task 3 (RAW+FE):** 6 axes x 6 statistics = **36 features**, all given to the tree (no selection). `src/model_raw_fe.py`.
- **Task 5 (QUAT+FE):** 4 quaternion components x 6 statistics = **24 candidate features**; `src/model_quaternion_fe.py`.

## Feature selection for Task 5 (as in MEMS Studio's Automatic Filter & Feature Selection)
1. **ANOVA F-statistic** (`sklearn.feature_selection.f_classif`) of every candidate feature, computed on the training windows only (`docs/task5/anova_f_statistics.csv`).
2. **Recursive Feature Elimination (RFE)** with a **random-forest** estimator, removing one feature per round until one is left; the removal order ranks all 24 features (`docs/task5/rfe_feature_ranking.csv`). The top K = 8 are kept.
3. **Why a random forest:** RFE with a single decision tree gave importance 0 to 22 of 24 features and removed the features in plain column order (`tree_diagnostic` in `docs/task5/model_summary.json`).
4. The final classifier is a `DecisionTreeClassifier` with the same default hyperparameters as Tasks 2-4.

**Selected (8):** q3__var, q3__min, q3__p2p, q1__max, q1__energy, q3__mean, q3__max, q1__var

**Eliminated (16):** q2__var, q2__min, q0__var, q2__p2p, q0__p2p, q1__p2p, q2__energy, q1__mean, q2__mean, q1__min, q0__energy, q0__max, q3__energy, q0__min, q2__max, q0__mean

| RFE rank | Feature | ANOVA F | Outcome |
|---|---|---|---|
| 1 | q3__var | 2020 | kept |
| 2 | q3__min | 665 | kept |
| 3 | q3__p2p | 2959 | kept |
| 4 | q1__max | 936 | kept |
| 5 | q1__energy | 693 | kept |
| 6 | q3__mean | 517 | kept |
| 7 | q3__max | 415 | kept |
| 8 | q1__var | 101 | kept |
| 9 | q2__var | 129 | eliminated |
| 10 | q2__min | 143 | eliminated |
| 11 | q0__var | 403 | eliminated |
| 12 | q2__p2p | 335 | eliminated |
| 13 | q0__p2p | 862 | eliminated |
| 14 | q1__p2p | 510 | eliminated |
| 15 | q2__energy | 95 | eliminated |
| 16 | q1__mean | 622 | eliminated |
| 17 | q2__mean | 94 | eliminated |
| 18 | q1__min | 418 | eliminated |
| 19 | q0__energy | 233 | eliminated |
| 20 | q0__max | 328 | eliminated |
| 21 | q3__energy | 99 | eliminated |
| 22 | q0__min | 77 | eliminated |
| 23 | q2__max | 48 | eliminated |
| 24 | q0__mean | 159 | eliminated |

## Result and caveat
- The final tree uses only q1__energy, q3__max (level statistics) and reaches 80.49 % on the test windows.
- `docs/robustness/` shows that **motion-only statistics (variance, peak-to-peak)** reach 100 % on the same windows, whereas level statistics (mean, max, min, energy) fail when the board orientation drifts. Feature selection on a single training block can therefore pick non-robust features.
