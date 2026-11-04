Task 7 — NEW ISPU PROJECT: Curl=0, Lateral raise=1, Left punch=2 (255=not ready)

Start with ../README_START_HERE.md (in the top level ZIP folder).

This is the complete ISPU *SOURCE* project. It contains quaternion generation,
42-frame relative-quaternion feature extraction, decision-tree inference, and
output registers for AlgoBuilder. The STM32 Sensor Hub firmware is generated
separately inside AlgoBuilder with your NUCLEO-F401RE board setup.

Open the ISPU_208hz folder in MEMS Studio > Advanced Features > ISPU IDE.
Build using make/Makefile. It compiles src/main.c, src/madgwick.c,
src/fusion_core.c and NEW src/quat_fe_tree.c. The build must generate a NEW
make/bin/ispu.json for import into the AlgoBuilder ISPU block.
No compiled pre-existing JSON or image is shipped with this archive.

Native ISPU processing 208 Hz (acc ±8g, gyro ±2000dps); classifier resamples
to ~120 Hz and predicts every 21 frames after a 42-frame warm-up.

Startup calibration: 0 waiting, 1 accumulating, 2 valid (~2s still).
Quaternion exported x,y,z,w (w scalar); internal C uses w,x,y,z.
The training dataset was exported at ~120.48 Hz. This does not imply the ISPU
natively executes at 120 Hz.

Check new classes and outputs in meta.txt:
Activity class id: 0 Curl, 1 Lateral raise, 2 Left punch, 255 not ready.
Prediction counter: increments once per classifier decision.
Leaf training purity is not a calibrated posterior probability.

Host Madgwick test from this project root:
gcc -std=c11 -Wall -Wextra -Werror -O2 -DISPU_SAMPLE_RATE_HZ=208 \
  -Isrc src/madgwick.c src/fusion_core.c host_test/test_madgwick.c -lm -o test_madgwick
./test_madgwick

STRED build, STM32 flashing, UART link, and hardware benchmarks require
the actual MEMS Studio/STM32 toolchain and board.
