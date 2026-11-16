# DA3 engineering comparison — supplied training results and STM32Cube AI reports

## Four-model numerical summary

| Metric | T1 Float32 | T1 Int8 | T2 Float32 | T2 Int8 |
|---|---:|---:|---:|---:|
| Test accuracy (held-out recorded trials) | 100% | 66.67% | 100% | 100% |
| On-target neural-network inference time (ms) | ~0.05* | ~0.06* | 5.30 | 2.27 |
| Internal RAM reported by AI Studio | ~160 B* | ~2 KB* | ~7 KB | ~6 KB |
| Internal Flash reported by AI Studio | ~6 KB* | ~9 KB* | ~15 KB | ~30 KB |
| Task 2 model weights in AI Studio | — | — | ~7 KB | ~2 KB |
| Task 2 library Flash in AI Studio | — | — | ~8 KB | ~28 KB |

* Task 1 memory and latency figures are copied from the **previous conversation's** comparison, not independently verified from CubeAI logs in this ZIP. Verify exact values against original Task 1 AI Studio report before submission. Task 2 values are read directly from screenshots supplied on November 15, 2026. Rounded memory values may not add exactly because of display rounding and allocations.

## What the data show

- Task 1 Float32 has the shortest inference time and lowest reported network-only memory footprint among the recorded configurations. Quantizing the small Task 1 model reduced test classification accuracy to 66.67%.
- Task 2 Int8 achieves the same 100% test classification accuracy as Task 2 Float32 on the supplied held-out recordings. Its 2.27 ms latency is ~57.2% below the 5.30 ms Float32 CNN latency, at ~2.33× the throughput.
- Task 2 Int8 requires about **30 KB** of reported internal Flash, **more** than the ~15 KB for Float32, despite smaller reported weights. The extra Flash comes from a larger generated runtime library (~28 KB vs ~8 KB).
- In the original Task 2 models, Float32 `quaternion_tfr_float32.h5` failed analysis because ST Edge AI rejected the `Rescaling` layer. A Float32 TFLite conversion (`quaternion_tfr_float32_cubeai.tflite`) subsequently passed on-target analysis and validation.

## Important boundaries and limitations

- On-target comparisons include **neural-network execution only**. Data collection, quaternion normalization, window extraction, ANOVA-selected features, STFT and log-power conversion are **not included in the measured timing**.
- STM32Cube AI used **random validation data** for the shown on-target output agreement tests. The 100% reported there is agreement between original and optimized implementations, not ground-truth classification accuracy.
- The Python test accuracy derives from 3 classes, 5 independent recordings per class, and 1 held-out recording per class. Many overlapping windows from a single recording do not constitute many independent tests. New sessions, hardware orientations, operators, and different speeds are needed to assess real-world generalization.
- The same trial identities were held out by Task 1 and Task 2, but Task 1 used 9 windows/held-out recording and Task 2 used 8, due to the different window-end policies. Compare accuracy results with this nuance.
- The original models should not be replaced by newly retrained/requantized files without **fresh** test and CubeAI reports.

## Recommendation

For simple motion recognition under these conditions, Task 1 Float32 is the computationally preferred candidate; Task 2 Int8 demonstrates that a more expressive time-frequency CNN can also fit and operate on the STM32, with faster inference than its Float32 CNN counterpart. Do not claim that either system is generally superior without end-to-end preprocessing and independent-trial tests.
