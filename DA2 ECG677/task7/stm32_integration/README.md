# Optional STM32 UART example — NOT the complete board firmware

- The ISPU firmware is in `ISPU_208hz/src/main.c` and `quat_fe_tree.c`.
- MEMS Studio AlgoBuilder generates a board-specific NUCLEO-F401RE Sensor Hub firmware project that reads the ISPU outputs.
- If you additionally need the assignment's UART output at **921600 baud**, configure the appropriate UART hardware in that **generated STM32 CubeIDE project** first. Connect its TX to the correct receiver and share a common ground. Do not assume USART2 is wired to your log connection without verifying the board.
- Copy the helper C/H into the generated STM32 project. After its generated Sensor Hub code reads `Activity class id`, `Prediction counter` and `Calibration status`, call:

```c
/* Example only; 'huart' and data fields must come from your generated code. */
Task7_UART_Send(&huart2, activity_class_id, prediction_counter, calibration_status);
```

Example output CSV rows: `1,52,2` means predicted lateral raise, 52nd prediction, calibration valid. Do NOT call 120 times/s if you only want one line per new model decision; check if `prediction_counter` changed first.

**This helper alone will not read the ISPU registers** and it does not constitute a compiled, flashed STM32 project. Use AlgoBuilder's generated Sensor Hub project as the integration base. If you provide that generated STM32 project, this UART integration can be placed in the exact callback.
