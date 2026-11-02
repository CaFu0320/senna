/* OPTIONAL instrumentation reference for STM32F401RE Cortex-M4.
   INSERT the statements inside the generated project; DO NOT blindly compile
   this file as a standalone translation unit.
   It times Sensor_Hub_Handler (STM32 I2C/register acquisition), NOT ISPU inference.
   IMPORTANT: Any plain-text UART logging will conflict with the MEMS Studio
   framed binary protocol if you use the same USART2 at the same time. */
/* During startup, once: */
/* CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
   DWT->CYCCNT = 0;
   DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk; */
/* Inside AB_Handler, replace the existing Sensor_Hub_Handler call with:
   uint32_t t0 = DWT->CYCCNT;
   Sensor_Hub_Handler(&Sensor_Hub_1_out);
   uint32_t stm32_read_cycles = DWT->CYCCNT - t0;
   float stm32_read_us = 1e6f * (float)stm32_read_cycles / (float)SystemCoreClock;
   // Store for debugger/watch view or transmit only in a separate text-console mode.
*/
