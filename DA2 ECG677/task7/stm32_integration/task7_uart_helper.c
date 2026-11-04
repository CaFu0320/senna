#include "task7_uart_helper.h"
#include <stdio.h>
HAL_StatusTypeDef Task7_UART_Send(UART_HandleTypeDef *huart,
            uint32_t activity_id,uint32_t prediction_counter,uint32_t calibration_status) {
    char buffer[80];
    int n=snprintf(buffer,sizeof(buffer),"%lu,%lu,%lu\r\n",
         (unsigned long)activity_id,(unsigned long)prediction_counter,
         (unsigned long)calibration_status);
    if (n<0 || n>=(int)sizeof(buffer))return HAL_ERROR;
    return HAL_UART_Transmit(huart,(uint8_t *)buffer,(uint16_t)n,10u);
}
