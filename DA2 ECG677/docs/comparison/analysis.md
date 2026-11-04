# Task 6 comparison for the exercise recordings

| Model | Correct / test | Accuracy | Macro F1 | Leaves | Window buffer (B) |
|---|---:|---:|---:|---:|---:|
| RAW | 1305 / 1334 | 97.83% | 0.978 | 83 | 0 |
| RAW+FE | 59 / 59 | 100.00% | 1.000 | 5 | 1008 |
| QUAT | 1590 / 1823 | 87.22% | 0.867 | 5 | 0 |
| QUAT+FE | 81 / 81 | 100.00% | 1.000 | 3 | 672 |

Both feature-engineered models classified every test window correctly. QUAT+FE used three leaves and a 672-byte window buffer, compared with five leaves and 1,008 bytes for RAW+FE. QUAT had the smallest JSON and avoided buffering, but its lateral raise recall was about 62%. The five-block check put QUAT+FE at 99.64% mean accuracy and RAW+FE at 98.51%.

These are within-recording results. Raw and quaternion logs are separate takes, and the test sets contain different numbers and types of observations. The comparison is descriptive and cannot isolate the effect of the representation from differences between takes.
