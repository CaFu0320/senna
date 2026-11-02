Task 7 - ST ISPU Madgwick quaternion getter: 208 Hz NATIVE processing

Open THIS folder in MEMS Studio 2.4.1 > Advanced Features > ISPU IDE.
Open make/Makefile and Build. New files appear under make/bin/ispu.json and ispu.h.
Then open your working AlgoBuilder design, save a COPY, change the ISPU block
Configuration File to this project's new make/bin/ispu.json, reconnect qx,qy,qz,qw
to your 4-channel float Mux, rebuild and program the NUCLEO-F401RE.
Do not use an older ispu.json from another project's make/bin.

ON STARTUP: set the board flat or in any fixed orientation, RESET, keep perfectly
still for 2-3 seconds. Calibration status output: 0 = waiting for stillness,
1 = accumulating, 2 = valid/calibrated. If it never reaches 2, check gyro
range, accelerometer norm and hold the board still.

Output channel order: x,y,z,w (scalar LAST). For CSV machine learning, map
q0=w,q1=x,q2=y,q3=z. Only record after calibration status becomes 2.
Use 30 seconds of stationary testing to ensure q is stable and norm^2 about 1.
Inspect Gyro bias z (dps), Raw gyro z (dps), Accel norm (g) and Stationary flag.
The initial q after calibration is aligned with the measured gravity direction.
Absolute yaw cannot be corrected without a magnetometer.

No classifier is included in THIS project; there is no Activity ID output.
This isolates the filter from the model and is intentionally a quaternion getter.

IMPORTANT: 208 Hz is ISPU native processing, NOT proof that MEMS Studio exported
at 208 Hz. The independent request for exactly 120 Hz LOGGED quaternions remains
unverified. Check CSV timestamps: 120 Hz -> approximately 8.333 ms per row.

We use +/-8g (ACC_SENS=0.000244 g/LSB), +/-2000dps (GYR_SENS=0.070 dps/LSB).
This matches the original working MotionFX ISPU source. If sensor settings
are different in AlgoBuilder, regenerate with matching full-scale settings.

Algorithms source: original implementation of 6-DOF Madgwick gradient descent
(same published 2010 equations as Arduino MadgwickAHRS). This is NOT MotionFX,
and does not claim X-CUBE-MEMS1 contains a Madgwick template.

Test on PC (requires C compiler):
 gcc -std=c11 -Wall -Wextra -Werror -O2 -DISPU_SAMPLE_RATE_HZ=208 -Isrc src/madgwick.c src/fusion_core.c host_test/test_madgwick.c -lm -o test_madgwick
 ./test_madgwick

Host tests do not validate STRED compilation or hardware results.
