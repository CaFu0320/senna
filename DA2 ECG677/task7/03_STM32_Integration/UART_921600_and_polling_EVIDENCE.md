# STM32F401RE integration: source evidence

From the user-provided generated `com.c` and `ab_sensor_hub.c` (MEMS Studio 2.4.1). These are source-code verification excerpts, not independently compiled by this package.

## UART in `com.c`

```c
volatile uint32_t Usart_BaudRate = 921600;
UartHandle.Instance        = USARTx;
UartHandle.Init.BaudRate   = Usart_BaudRate;
UartHandle.Init.WordLength = UART_WORDLENGTH_8B;
UartHandle.Init.StopBits   = UART_STOPBITS_1;
UartHandle.Init.Parity     = UART_PARITY_NONE;
UartHandle.Init.HwFlowCtl  = UART_HWCONTROL_NONE;
UartHandle.Init.Mode       = UART_MODE_TX_RX;
HAL_UART_Init(&UartHandle);
HAL_UART_Transmit(&UartHandle, (uint8_t *)UART_TxBuffer, CountOut, 5000);
```

## Polling in `ab_sensor_hub.c`, approx. lines 1259-1269

```c
#if (defined (USE_IKS4A1))
 #if (defined (USE_LSM6DSO16IS))
  if (sensor_hub_data.ispu_enable == 1) {
    (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSO16IS_0,
       LSM6DSO16IS_FUNC_CFG_ACCESS, 0x80);
    for (i = 0; i < sensor_hub_data.ispu_data_size; i++) {
      (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSO16IS_0,
          LSM6DSO16IS_ISPU_DOUT_00_L + i, &sensor_hub_data.ispu_data[i]);
    }
    (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSO16IS_0,
       LSM6DSO16IS_FUNC_CFG_ACCESS, 0x00);
  }
 #endif
#endif
```

`algo_builder.c` sets `Sensor_Hub_Init(0, 120, 2, 3)`, `ISPU_Init(64)`, copies `Activity_class_id` from buffer byte offset 40, and calls `Display_Update` to send the result through the MEMS Studio protocol. UART sends *encoded binary messages*, not plain ASCII by default.

**Not included:** the complete generated and buildable STM32CubeIDE workspace, so STM32 FLASH/RAM usage cannot yet be measured from its ELF/MAP.
