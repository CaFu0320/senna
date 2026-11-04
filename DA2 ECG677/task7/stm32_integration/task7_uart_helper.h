#ifndef TASK7_UART_HELPER_H
#define TASK7_UART_HELPER_H
#include "stm32f4xx_hal.h"
#include <stdint.h>
/* Call after reading AlgoBuilder's generated ISPU 'Activity class id',
   'Prediction counter', and 'Calibration status' outputs.
   Does not include the generated Sensor Hub register-reading code. */
HAL_StatusTypeDef Task7_UART_Send(UART_HandleTypeDef *huart,
            uint32_t activity_id,uint32_t prediction_counter,uint32_t calibration_status);
#endif
