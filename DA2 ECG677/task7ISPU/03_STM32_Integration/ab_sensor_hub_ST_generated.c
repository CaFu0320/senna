/**
 ******************************************************************************
 * @file       ab_sensor_hub.c
 * @author     MEMS Application Team
 * @brief      AlgoBuilder sensor hub
 ******************************************************************************
 * @attention
 *
 * <h2><center>&copy; COPYRIGHT(c) 2019 STMicroelectronics</center></h2>
 *
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *   1. Redistributions of source code must retain the above copyright notice,
 *      this list of conditions and the following disclaimer.
 *   2. Redistributions in binary form must reproduce the above copyright notice,
 *      this list of conditions and the following disclaimer in the documentation
 *      and/or other materials provided with the distribution.
 *   3. Neither the name of STMicroelectronics nor the names of its contributors
 *      may be used to endorse or promote products derived from this software
 *      without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 ******************************************************************************
 */

/* Includes ------------------------------------------------------------------*/
#include "ab_sensor_hub.h"
#include "ab_fsm_mlc.h"
#include "ab_ispu.h"

/** @addtogroup AlgoBuilder_Firmware
  * @{
  */

/** @addtogroup AlgoBuilder_SensorHub
  * @{
  */

/* Private typedef -----------------------------------------------------------*/
/* Private defines -----------------------------------------------------------*/
#if (defined (USE_IKS02A1))
    #define ACC_ORIENTATION_X   'n'
    #define ACC_ORIENTATION_Y   'w'
    #define ACC_ORIENTATION_Z   'u'

    #define GYR_ORIENTATION_X   'n'
    #define GYR_ORIENTATION_Y   'w'
    #define GYR_ORIENTATION_Z   'u'

    #define MAG_ORIENTATION_X   'n'
    #define MAG_ORIENTATION_Y   'e'
    #define MAG_ORIENTATION_Z   'u'
#elif (defined (USE_IKS01A3))
    #if (defined (USE_LSM6DSO16IS))
      #define ACC_ORIENTATION_X   'n'
      #define ACC_ORIENTATION_Y   'w'
      #define ACC_ORIENTATION_Z   'u'

      #define GYR_ORIENTATION_X   'n'
      #define GYR_ORIENTATION_Y   'w'
      #define GYR_ORIENTATION_Z   'u'
    #else
      #define ACC_ORIENTATION_X   's'
      #define ACC_ORIENTATION_Y   'e'
      #define ACC_ORIENTATION_Z   'u'

      #define GYR_ORIENTATION_X   's'
      #define GYR_ORIENTATION_Y   'e'
      #define GYR_ORIENTATION_Z   'u'
    #endif
    
    #define MAG_ORIENTATION_X   'n'
    #define MAG_ORIENTATION_Y   'e'
    #define MAG_ORIENTATION_Z   'u'
#elif (defined (USE_IKS4A1))
    #if (defined (USE_LSM6DSO16IS))
      #define ACC_ORIENTATION_X   'e'
      #define ACC_ORIENTATION_Y   'n'
      #define ACC_ORIENTATION_Z   'u'

      #define GYR_ORIENTATION_X   'e'
      #define GYR_ORIENTATION_Y   'n'
      #define GYR_ORIENTATION_Z   'u'
    #else
      #define ACC_ORIENTATION_X   's'
      #define ACC_ORIENTATION_Y   'e'
      #define ACC_ORIENTATION_Z   'u'

      #define GYR_ORIENTATION_X   's'
      #define GYR_ORIENTATION_Y   'e'
      #define GYR_ORIENTATION_Z   'u'
    #endif
    
    #define MAG_ORIENTATION_X   'n'
    #define MAG_ORIENTATION_Y   'e'
    #define MAG_ORIENTATION_Z   'u'
#elif (defined (USE_IKS5A1))
    #if (defined (USE_ISM330IS))
      #define ACC_ORIENTATION_X   'e'
      #define ACC_ORIENTATION_Y   'n'
      #define ACC_ORIENTATION_Z   'u'

      #define GYR_ORIENTATION_X   'e'
      #define GYR_ORIENTATION_Y   'n'
      #define GYR_ORIENTATION_Z   'u'
    #else
      #define ACC_ORIENTATION_X   'n'
      #define ACC_ORIENTATION_Y   'w'
      #define ACC_ORIENTATION_Z   'u'

      #define GYR_ORIENTATION_X   'n'
      #define GYR_ORIENTATION_Y   'w'
      #define GYR_ORIENTATION_Z   'u'
    #endif
    
    #define MAG_ORIENTATION_X   'n'
    #define MAG_ORIENTATION_Y   'e'
    #define MAG_ORIENTATION_Z   'u'
#elif (defined (USE_SENSORTILEBOX))
    #define ACC_ORIENTATION_X   'n'
    #define ACC_ORIENTATION_Y   'w'
    #define ACC_ORIENTATION_Z   'u'

    #define GYR_ORIENTATION_X   'n'
    #define GYR_ORIENTATION_Y   'w'
    #define GYR_ORIENTATION_Z   'u'

    #define MAG_ORIENTATION_X   'w'
    #define MAG_ORIENTATION_Y   'n'
    #define MAG_ORIENTATION_Z   'u'
#elif (defined (USE_SENSORTILEBOXPRO))
    /* ToDo */
    #define ACC_ORIENTATION_X   'w'
    #define ACC_ORIENTATION_Y   's'
    #define ACC_ORIENTATION_Z   'u'

    #define GYR_ORIENTATION_X   'w'
    #define GYR_ORIENTATION_Y   's'
    #define GYR_ORIENTATION_Z   'u'

    #define MAG_ORIENTATION_X   'w'
    #define MAG_ORIENTATION_Y   'n'
    #define MAG_ORIENTATION_Z   'u'
#elif (defined (USE_STWIN))
    #define ACC_ORIENTATION_X   'e'
    #define ACC_ORIENTATION_Y   'n'
    #define ACC_ORIENTATION_Z   'u'

    #define GYR_ORIENTATION_X   'e'
    #define GYR_ORIENTATION_Y   'n'
    #define GYR_ORIENTATION_Z   'u'

    #define MAG_ORIENTATION_X   'e'
    #define MAG_ORIENTATION_Y   's'
    #define MAG_ORIENTATION_Z   'u'
#elif (defined (USE_STWINBOX))
    #define ACC_ORIENTATION_X   'e'
    #define ACC_ORIENTATION_Y   'n'
    #define ACC_ORIENTATION_Z   'u'

    #define GYR_ORIENTATION_X   'e'
    #define GYR_ORIENTATION_Y   'n'
    #define GYR_ORIENTATION_Z   'u'

    #define MAG_ORIENTATION_X   's'
    #define MAG_ORIENTATION_Y   'w'
    #define MAG_ORIENTATION_Z   'u'
#else
#error Not supported platform
#endif

#define FX_STATE_SIZE (size_t)(2432)
    
/* Private macro -------------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/

extern uint32_t sensor_read_request;
extern offline_data_t offline_data;

extern volatile uint32_t update_16Hz;
extern volatile uint32_t update_25Hz;
extern volatile uint32_t update_50Hz;
extern volatile uint32_t update_100Hz;

extern void *ACCELERO_handle;
extern void *GYRO_handle;
extern void *MAGNETO_handle;
extern void *HUMIDITY_handle;
extern void *TEMPERATURE_handle;
extern void *PRESSURE_handle;

sensor_hub_data_t sensor_hub_data;

#if (MotionFX_9X)
static uint8_t mfxstate_9x[FX_STATE_SIZE];
#endif

#if (MotionFX_6X)
static uint8_t mfxstate_6x[FX_STATE_SIZE];
#endif

float acc_odr_before_ucf;
uint32_t acc_fs_before_ucf;
float gyro_odr_before_ucf;
uint32_t gyro_fs_before_ucf;

/* Private function prototypes -----------------------------------------------*/
static void Set_Accelero_FS(uint32_t accel_fs);
static void Set_Gyro_FS(uint32_t gyro_fs);
static float Get_Accelero_ODR(void);
static uint32_t Get_Accelero_FS(void);
static float Get_Gyro_ODR(void);
static uint32_t Get_Gyro_FS(void);

#if (MotionEC)
static void Create_Rotation_Matrix(const char *orientation, float *matrix);
static void Axis_Transformation(float *o, float *i, float *matrix);
#endif

#if (MotionAC)
static void MotionAC_Update_Data(void);
#endif
#if (MotionAW)
static void MotionAW_Update_Data(void);
#endif
#if (MotionEC)
static void MotionEC_Update_Data(void);
#endif
#if (MotionFX_9X)
static void MotionFX_9X_Update_Data(void);
#endif
#if (MotionFX_6X)
static void MotionFX_6X_Update_Data(void);
#endif
#if (MotionGC)
static void MotionGC_Update_Data(void);
#endif
#if (MotionID)
static void MotionID_Update_Data(void);
#endif
#if (MotionMC)
static void MotionMC_Update_Data(void);
#endif
#if (MotionPM)
static void MotionPM_Update_Data(void);
#endif
#if (MotionPW)
static void MotionPW_Update_Data(void);
#endif
#if (MotionTL)
static void MotionTL_Update_Data(void);
#endif

/* Private functions ---------------------------------------------------------*/
static uint8_t meas_odr(float *odr_measured);

/**
 * @brief  Measure ODR of the sensor
 * @param  None
 * @retval 1 in case of success 0 otherwise
 */
static uint8_t meas_odr(float *odr_measured)
{
  uint8_t  odr_meas_enable = 1; 
  uint16_t odr_meas_iter = 0;
  uint16_t odr_meas_start_time = 0;
  uint16_t odr_meas_stop_time = 0;
  uint16_t odr_meas_samples = 150; /* number of measured samples for calculating ODR */
  uint32_t start = 0;
  
  /* Set DRDY pulsed mode */
#if (defined (USE_IKS02A1))
  (void)IKS02A1_MOTION_SENSOR_DRDY_Set_Mode(SELECTED_6AXIS_SENSOR, 1);
#elif (defined (USE_IKS01A3))
  (void)IKS01A3_MOTION_SENSOR_DRDY_Set_Mode(SELECTED_6AXIS_SENSOR, 1);
#elif (defined (USE_IKS4A1))
  (void)IKS4A1_MOTION_SENSOR_DRDY_Set_Mode(SELECTED_6AXIS_SENSOR, 1);
#elif (defined (USE_IKS5A1))
  (void)IKS5A1_MOTION_SENSOR_DRDY_Set_Mode(SELECTED_6AXIS_SENSOR, 1);
#elif (defined (USE_SENSORTILEBOX))
  (void)BSP_MOTION_SENSOR_Set_DRDY_Mode(LSM6DSOX_0, LSM6DSOX_DRDY_PULSED);
#elif (defined (USE_STWIN))
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(ISM330DHCX_0, ISM330DHCX_DRDY_PULSED);
#elif (defined (USE_SENSORTILEBOXPRO))
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(SELECTED_6AXIS_SENSOR, 1);
#elif (defined (USE_STWINBOX))
#if (defined (USE_ISM330IS))  
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(ISM330IS_0, ISM330IS_DRDY_PULSED);
#elif (defined (USE_ISM6HG256X))  
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(ISM6HG256X_0, ISM6HG256X_DRDY_PULSED);
#else
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(ISM330DHCX_0, ISM330DHCX_DRDY_PULSED);
#endif
#else
#error Not supported platform
#endif
      
  start = HAL_GetTick();
  
  while (odr_meas_enable)
  {
    if ((HAL_GetTick() - start) > 100000)
    {
      /* Timeout */
      return 0;
    }
    
    if (sensor_read_request)
    {
      sensor_read_request = 0;
      
      /* Get start time */
      if (odr_meas_iter == 0)
      {
        odr_meas_start_time = HAL_GetTick();
      }
      
      /* Get stop time */ 
      if (odr_meas_iter == (odr_meas_samples - 1))
      {
        odr_meas_stop_time = HAL_GetTick();
        odr_meas_enable = 0;        
      }
      
      /* Stop after measuring "odr_meas_samples" values */ 
      if (odr_meas_iter < odr_meas_samples)
      {
        odr_meas_iter++;
      }
    }    
  }
  
  /* Calculate measured ODR */
  *odr_measured = (float)(1000 * odr_meas_samples) / (odr_meas_stop_time - odr_meas_start_time);

#if(0)
  /* Set DRDY latched mode */
#if (defined (USE_IKS02A1))
  (void)IKS02A1_MOTION_SENSOR_DRDY_Set_Mode(SELECTED_6AXIS_SENSOR, 0);
#elif (defined (USE_IKS01A3))
  (void)IKS01A3_MOTION_SENSOR_DRDY_Set_Mode(SELECTED_6AXIS_SENSOR, 0);
#elif (defined (USE_SENSORTILEBOX))
  (void)BSP_MOTION_SENSOR_Set_DRDY_Mode(LSM6DSOX_0, LSM6DSOX_DRDY_LATCHED);
#elif (defined (USE_SENSORTILEBOXPRO))
  (void)BSP_MOTION_SENSOR_Set_DRDY_Mode(SELECTED_6AXIS_SENSOR, 0);
#elif (defined (USE_STWIN))
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(ISM330DHCX_0, ISM330DHCX_DRDY_LATCHED);
#elif (defined (USE_STWINBOX))
#if (defined (USE_ISM330IS))  
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(ISM330IS_0, ISM330IS_DRDY_LATCHED);
#elif (defined (USE_ISM6HG256X))
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(ISM6HG256X_0, ISM6HG256X_DRDY_LATCHED);
#else
  (void)BSP_MOTION_SENSOR_DRDY_Set_Mode(ISM330DHCX_0, ISM330DHCX_DRDY_LATCHED);
#endif
#else
#error Not supported platform
#endif
#endif
  
  return 1;
}

/* Public functions ----------------------------------------------------------*/
/**
 * @brief  SensorHub initialization, set data polling period and full scales
 */
void Sensor_Hub_Init(uint32_t data_rate_control, uint32_t data_rate, uint32_t accel_fs, uint32_t gyro_fs)
{
  sensor_hub_data.data_rate_control = (data_rate_control_t)data_rate_control;
    
  if (data_rate_control == DRC_OFFLINE)
  {
    sensor_hub_data.data_rate_Hz = data_rate;
    sensor_hub_data.meas_data_rate_Hz = data_rate;
    sensor_hub_data.iteration_counter = 0;
    
    offline_data.timestamp_ms = 0;
  }
  else
  {
    float real_odr = 0;
    
  #if (defined (USE_IKS02A1))
    uint8_t reg = 0;    
    uint8_t int1_drdy_xl = 0;
    uint8_t int1_drdy_g = 0;
  #elif (defined (USE_IKS01A3))
    uint8_t reg = 0;
    uint8_t int1_drdy_xl = 0;
    uint8_t int1_drdy_g = 0;
  #elif (defined (USE_IKS4A1))
    uint8_t reg = 0;
    uint8_t int1_drdy_xl = 0;
    uint8_t int1_drdy_g = 0;
  #elif (defined (USE_IKS5A1))
    uint8_t reg = 0;
    uint8_t int1_drdy_xl = 0;
    uint8_t int1_drdy_g = 0;
  #elif (defined (USE_SENSORTILEBOX))
    lsm6dsox_pin_int1_route_t int1_route;
  #elif (defined (USE_SENSORTILEBOXPRO))
    uint8_t reg = 0;    
    uint8_t int1_drdy_xl = 0;
    uint8_t int1_drdy_g = 0;
  #elif (defined (USE_STWIN))
    uint8_t reg = 0;
    uint8_t int1_drdy_xl = 0;
    uint8_t int1_drdy_g = 0;
  #elif (defined (USE_STWINBOX))
    uint8_t reg = 0;
    uint8_t int1_drdy_xl = 0;
    uint8_t int1_drdy_g = 0;
  #else
    #error Not supported platform
  #endif
    
    sensor_hub_data.motion_ac_enable = 0;
    sensor_hub_data.motion_aw_enable = 0;
    sensor_hub_data.motion_ec_enable = 0;
    sensor_hub_data.motion_fx_6x_enable = 0;
    sensor_hub_data.motion_fx_9x_enable = 0;
    sensor_hub_data.motion_gc_enable = 0;
    sensor_hub_data.motion_id_enable = 0;
    sensor_hub_data.motion_mc_enable = 0;
    sensor_hub_data.motion_pm_enable = 0;
    sensor_hub_data.motion_pw_enable = 0;
    sensor_hub_data.motion_tl_enable = 0;

    sensor_hub_data.data_rate_Hz = data_rate;
    
    switch (data_rate_control)
    {
      case DRC_TIMER:  
        TIM_AB_Config(data_rate);
  #if (defined (USE_IKS02A1))  
        int1_drdy_xl = 0;
        int1_drdy_g = 0;
  #elif (defined (USE_IKS01A3))
        int1_drdy_xl = 0;
        int1_drdy_g = 0;
  #elif (defined (USE_IKS4A1))
        int1_drdy_xl = 0;
        int1_drdy_g = 0;
  #elif (defined (USE_IKS5A1))
        int1_drdy_xl = 0;
        int1_drdy_g = 0;
  #elif (defined (USE_SENSORTILEBOX))
        int1_route.drdy_xl = 0;
        int1_route.drdy_g = 0;
  #elif (defined (USE_SENSORTILEBOXPRO))
        int1_drdy_xl = 0;
        int1_drdy_g = 0;
  #elif (defined (USE_STWIN))
        int1_drdy_xl = 0;
        int1_drdy_g = 0;
  #elif (defined (USE_STWINBOX))
        int1_drdy_xl = 0;
        int1_drdy_g = 0;
  #else
    #error Not supported platform
  #endif
      break;
        
      case DRC_ACCELEROMETER:
        sensor_hub_data.acceleration_enable = 1;
  #if (defined (USE_IKS02A1))  
        int1_drdy_xl = 1;
        int1_drdy_g = 0;
  #elif (defined (USE_IKS01A3))
        int1_drdy_xl = 1;
        int1_drdy_g = 0;
  #elif (defined (USE_IKS4A1))
        int1_drdy_xl = 1;
        int1_drdy_g = 0;
  #elif (defined (USE_IKS5A1))
        int1_drdy_xl = 1;
        int1_drdy_g = 0;
  #elif (defined (USE_SENSORTILEBOX))
        int1_route.drdy_xl = 1;
        int1_route.drdy_g = 0;
  #elif (defined (USE_SENSORTILEBOXPRO))
        int1_drdy_xl = 1;
        int1_drdy_g = 0;
  #elif (defined (USE_STWIN))
        int1_drdy_xl = 1;
        int1_drdy_g = 0;
  #elif (defined (USE_STWINBOX))
        int1_drdy_xl = 1;
        int1_drdy_g = 0;
  #else
    #error Not supported platform
  #endif
      break;
      
      case DRC_GYROSCOPE:
        sensor_hub_data.angular_rate_enable = 1;
  #if (defined (USE_IKS02A1))  
        int1_drdy_xl = 0;
        int1_drdy_g = 1;
  #elif (defined (USE_IKS01A3))
        int1_drdy_xl = 0;
        int1_drdy_g = 1;
  #elif (defined (USE_IKS4A1))
        int1_drdy_xl = 0;
        int1_drdy_g = 1;
  #elif (defined (USE_IKS5A1))
        int1_drdy_xl = 0;
        int1_drdy_g = 1;
  #elif (defined (USE_SENSORTILEBOX))
        int1_route.drdy_xl = 0;
        int1_route.drdy_g = 1;
  #elif (defined (USE_SENSORTILEBOXPRO))
        int1_drdy_xl = 0;
        int1_drdy_g = 1;
  #elif (defined (USE_STWIN))
        int1_drdy_xl = 0;
        int1_drdy_g = 1;
  #elif (defined (USE_STWINBOX))
        int1_drdy_xl = 0;
        int1_drdy_g = 1;
  #else
    #error Not supported platform
  #endif
      break;  
    }

  #if (defined (USE_IKS02A1))
     #if (defined (USE_ISM330IS))
       (void)IKS02A1_MOTION_SENSOR_Read_Register(IKS02A1_ISM330IS_0, ISM330IS_INT1_CTRL, &reg);
       if (int1_drdy_xl == 1)
       {
         reg = reg | 0x01;
       }
       else
       {
         reg = reg & ~0x01;
       }
       (void)IKS02A1_MOTION_SENSOR_Write_Register(IKS02A1_ISM330IS_0, ISM330IS_INT1_CTRL, reg);
       
       (void)IKS02A1_MOTION_SENSOR_Read_Register(IKS02A1_ISM330IS_0, ISM330IS_INT1_CTRL, &reg);
       if (int1_drdy_g == 1)
       {
         reg = reg | 0x02;
       }
       else
       {
         reg = reg & ~0x02;
       }
       (void)IKS02A1_MOTION_SENSOR_Write_Register(IKS02A1_ISM330IS_0, ISM330IS_INT1_CTRL, reg);
    #else
       (void)IKS02A1_MOTION_SENSOR_Read_Register(IKS02A1_ISM330DHCX_0, ISM330DHCX_INT1_CTRL, &reg);
       if (int1_drdy_xl == 1)
       {
         reg = reg | 0x01;
       }
       else
       {
         reg = reg & ~0x01;
       }
       (void)IKS02A1_MOTION_SENSOR_Write_Register(IKS02A1_ISM330DHCX_0, ISM330DHCX_INT1_CTRL, reg);
       
       (void)IKS02A1_MOTION_SENSOR_Read_Register(IKS02A1_ISM330DHCX_0, ISM330DHCX_INT1_CTRL, &reg);
       if (int1_drdy_g == 1)
       {
         reg = reg | 0x02;
       }
       else
       {
         reg = reg & ~0x02;
       }
       (void)IKS02A1_MOTION_SENSOR_Write_Register(IKS02A1_ISM330DHCX_0, ISM330DHCX_INT1_CTRL, reg);
    #endif
  #elif (defined (USE_IKS01A3))
    #if (defined (USE_LSM6DSO16IS))
      (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, reg);
      
      (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, reg);
    #else
      (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO_0, LSM6DSO_INT1_CTRL, reg);
      
      (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO_0, LSM6DSO_INT1_CTRL, reg);
    #endif
  #elif (defined (USE_IKS4A1))
    #if (defined (USE_LSM6DSO16IS))
      (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, reg);
      
      (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, reg);
    #else
      (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_INT1_CTRL, reg);
      
      (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_INT1_CTRL, reg);
    #endif
 #elif (defined (USE_IKS5A1))
    #if (defined (USE_ISM330IS))
      (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM330IS_0, ISM330IS_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM330IS_0, ISM330IS_INT1_CTRL, reg);
      
      (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM330IS_0, ISM330IS_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM330IS_0, ISM330IS_INT1_CTRL, reg);
    #else
      (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_INT1_CTRL, reg);
      
      (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_INT1_CTRL, reg);
    #endif
  #elif (defined (USE_SENSORTILEBOX))
     (void)BSP_MOTION_SENSOR_Set_Pin_INT1_Route(LSM6DSOX_0, int1_route);
  #elif (defined (USE_SENSORTILEBOXPRO))
    #if (defined (USE_LSM6DSO16IS))
      (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, reg);
      
      (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSO16IS_0, LSM6DSO16IS_INT1_CTRL, reg);
     #elif (defined (USE_LSM6DSV320X))
      (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV320X_0, LSM6DSV320X_INT1_CTRL, reg);
      
      (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV320X_0, LSM6DSV320X_INT1_CTRL, reg);
    #else
      (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_INT1_CTRL, &reg);
      if (int1_drdy_xl == 1)
      {
        reg = reg | 0x01;
      }
      else
      {
        reg = reg & ~0x01;
      }
      (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV16X_0, LSM6DSV16X_INT1_CTRL, reg);
      
      (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_INT1_CTRL, &reg);
      if (int1_drdy_g == 1)
      {
        reg = reg | 0x02;
      }
      else
      {
        reg = reg & ~0x02;
      }
      (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV16X_0, LSM6DSV16X_INT1_CTRL, reg);
    #endif
  #elif (defined (USE_STWIN))
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_INT1_CTRL, &reg);
    if (int1_drdy_xl == 1)
    {
      reg = reg | 0x01;
    }
    else
    {
      reg = reg & ~0x01;
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_INT1_CTRL, reg);
    
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_INT1_CTRL, &reg);
    if (int1_drdy_g == 1)
    {
      reg = reg | 0x02;
    }
    else
    {
      reg = reg & ~0x02;
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_INT1_CTRL, reg);
  #elif (defined (USE_STWINBOX))
  #if (defined (USE_ISM330IS))
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330IS_0, ISM330IS_INT1_CTRL, &reg);
    if (int1_drdy_xl == 1)
    {
      reg = reg | 0x01;
    }
    else
    {
      reg = reg & ~0x01;
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330IS_0, ISM330IS_INT1_CTRL, reg);
    
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330IS_0, ISM330IS_INT1_CTRL, &reg);
    if (int1_drdy_g == 1)
    {
      reg = reg | 0x02;
    }
    else
    {
      reg = reg & ~0x02;
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330IS_0, ISM330IS_INT1_CTRL, reg);
  #elif (defined (USE_ISM6HG256X))
    (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_INT1_CTRL, &reg);
    if (int1_drdy_xl == 1)
    {
      reg = reg | 0x01;
    }
    else
    {
      reg = reg & ~0x01;
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM6HG256X_0, ISM6HG256X_INT1_CTRL, reg);
    
    (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_INT1_CTRL, &reg);
    if (int1_drdy_g == 1)
    {
      reg = reg | 0x02;
    }
    else
    {
      reg = reg & ~0x02;
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM6HG256X_0, ISM6HG256X_INT1_CTRL, reg);
  #else
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_INT1_CTRL, &reg);
    if (int1_drdy_xl == 1)
    {
      reg = reg | 0x01;
    }
    else
    {
      reg = reg & ~0x01;
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_INT1_CTRL, reg);
    
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_INT1_CTRL, &reg);
    if (int1_drdy_g == 1)
    {
      reg = reg | 0x02;
    }
    else
    {
      reg = reg & ~0x02;
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_INT1_CTRL, reg);
  #endif
  #else
    #error Not supported platform
  #endif
        
    Set_Accelero_FS(accel_fs);
    Set_Gyro_FS(gyro_fs);
    
  #if (defined (USE_IKS02A1))
    (void)IKS02A1_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS02A1_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS02A1_MOTION_SENSOR_SetOutputDataRate(IKS02A1_IIS2MDC_0, MOTION_MAGNETO, (float) sensor_hub_data.data_rate_Hz);
  #elif (defined (USE_IKS01A3))
    (void)IKS01A3_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS01A3_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS01A3_MOTION_SENSOR_SetOutputDataRate(IKS01A3_LIS2MDL_0, MOTION_MAGNETO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS01A3_ENV_SENSOR_SetOutputDataRate(IKS01A3_HTS221_0, ENV_TEMPERATURE, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS01A3_ENV_SENSOR_SetOutputDataRate(IKS01A3_HTS221_0, ENV_HUMIDITY, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS01A3_ENV_SENSOR_SetOutputDataRate(IKS01A3_LPS22HH_0, ENV_PRESSURE, (float) sensor_hub_data.data_rate_Hz);
  #elif (defined (USE_IKS4A1))
    (void)IKS4A1_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS4A1_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS4A1_MOTION_SENSOR_SetOutputDataRate(IKS4A1_LIS2MDL_0, MOTION_MAGNETO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS4A1_ENV_SENSOR_SetOutputDataRate(IKS4A1_SHT40AD1B_0, ENV_TEMPERATURE, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS4A1_ENV_SENSOR_SetOutputDataRate(IKS4A1_SHT40AD1B_0, ENV_HUMIDITY, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS4A1_ENV_SENSOR_SetOutputDataRate(IKS4A1_LPS22DF_0, ENV_PRESSURE, (float) sensor_hub_data.data_rate_Hz);
  #elif (defined (USE_IKS5A1))
    (void)IKS5A1_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS5A1_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS5A1_MOTION_SENSOR_SetOutputDataRate(IKS5A1_IIS2MDC_0, MOTION_MAGNETO, (float) sensor_hub_data.data_rate_Hz);
    (void)IKS5A1_ENV_SENSOR_SetOutputDataRate(IKS5A1_ILPS22QS_0, ENV_PRESSURE, (float) sensor_hub_data.data_rate_Hz);
     #if (defined (USE_ISM6HG256X))
      (void)IKS5A1_MOTION_SENSOR_ACC_HG_SetOutputDataRate(IKS5A1_ISM6HG256X_0, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    #endif
  #elif (defined (USE_SENSORTILEBOX))
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(LSM6DSOX_0, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(LSM6DSOX_0, MOTION_GYRO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(LIS2MDL_0, MOTION_MAGNETO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(HTS221_0, ENV_TEMPERATURE, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(HTS221_0, ENV_HUMIDITY, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(LPS22HH_0, ENV_PRESSURE, (float) sensor_hub_data.data_rate_Hz);
  #elif (defined (USE_SENSORTILEBOXPRO))
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, (float) sensor_hub_data.data_rate_Hz);
    #if (defined (USE_LSM6DSV320X))
      (void)BSP_MOTION_SENSOR_ACC_HG_SetOutputDataRate(LSM6DSV320X_0, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    #endif
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(LIS2MDL_0, MOTION_MAGNETO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(STTS22H_0, ENV_TEMPERATURE, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(LPS22DF_0, ENV_PRESSURE, (float) sensor_hub_data.data_rate_Hz);
  #elif (defined (USE_STWIN))
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(ISM330DHCX_0, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(ISM330DHCX_0, MOTION_GYRO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(IIS2MDC_0, MOTION_MAGNETO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(HTS221_0, ENV_TEMPERATURE, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(HTS221_0, ENV_HUMIDITY, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(LPS22HH_0, ENV_PRESSURE, (float) sensor_hub_data.data_rate_Hz);
   #elif (defined (USE_STWINBOX))
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, (float) sensor_hub_data.data_rate_Hz);
    #if (defined (USE_ISM6HG256X))
      (void)BSP_MOTION_SENSOR_ACC_HG_SetOutputDataRate(ISM6HG256X_0, MOTION_ACCELERO, (float) sensor_hub_data.data_rate_Hz);
    #endif
    (void)BSP_MOTION_SENSOR_SetOutputDataRate(IIS2MDC_0, MOTION_MAGNETO, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(STTS22H_0, ENV_TEMPERATURE, (float) sensor_hub_data.data_rate_Hz);
    (void)BSP_ENV_SENSOR_SetOutputDataRate(ILPS22QS_0, ENV_PRESSURE, (float) sensor_hub_data.data_rate_Hz);
  #else
    #error Not supported platform
  #endif

    if ((data_rate_control == DRC_ACCELEROMETER) || (data_rate_control == DRC_GYROSCOPE))
    {
      if (meas_odr(&real_odr) == 1) 
      {
        sensor_hub_data.meas_data_rate_Hz = (uint32_t) real_odr;
      }
    }
    else
    {
      sensor_hub_data.meas_data_rate_Hz = data_rate;
    }
    
    sensor_hub_data.sdcard_enable = 0;
    sensor_hub_data.iteration_counter = 0;
  }
}

/**
 * @brief  SensorHub hander, read data from sensors
 */
void Sensor_Hub_Handler(void **pdata)
{
  *pdata = (void *) &sensor_hub_data;

  if (sensor_hub_data.data_rate_control == DRC_OFFLINE)
  {
    /* Accelerometer Data */  
    if(sensor_hub_data.acceleration_enable == 1)
    {
      sensor_hub_data.acceleration[0] = offline_data.acceleration_x_mg * FROM_MG_TO_G;
      sensor_hub_data.acceleration[1] = offline_data.acceleration_y_mg * FROM_MG_TO_G;
      sensor_hub_data.acceleration[2] = offline_data.acceleration_z_mg * FROM_MG_TO_G;
    }

    /* Gyroscope Data */
    if(sensor_hub_data.angular_rate_enable == 1)
    {
      sensor_hub_data.angular_rate[0] = offline_data.angular_rate_x_mdps * FROM_MDPS_TO_DPS;
      sensor_hub_data.angular_rate[1] = offline_data.angular_rate_y_mdps * FROM_MDPS_TO_DPS;
      sensor_hub_data.angular_rate[2] = offline_data.angular_rate_z_mdps * FROM_MDPS_TO_DPS;
    }

    /* Magnetometer Data */
    if(sensor_hub_data.magnetic_field_enable == 1)
    {
      sensor_hub_data.magnetic_field[0] = offline_data.magnetic_field_x_mgauss * FROM_MGAUSS_TO_UT;
      sensor_hub_data.magnetic_field[1] = offline_data.magnetic_field_y_mgauss * FROM_MGAUSS_TO_UT;
      sensor_hub_data.magnetic_field[2] = offline_data.magnetic_field_z_mgauss * FROM_MGAUSS_TO_UT;
    }

    /* Pressure Sensor Data */
    if(sensor_hub_data.pressure_enable == 1)
    {
      sensor_hub_data.pressure = offline_data.pressure;
    }

    /* Humidity Sensor Data */
    if(sensor_hub_data.humidity_enable == 1)
    {
      sensor_hub_data.humidity = offline_data.humidity;
    }

    /* Temperature Sensor Data */
    if(sensor_hub_data.temperature_enable == 1)
    {
      sensor_hub_data.temperature = offline_data.temperature;
    }
  }
  else
  {
    /* Accelerometer Data */  
    if(sensor_hub_data.acceleration_enable == 1)
    {
  #if (defined (USE_IKS02A1))
      (void)IKS02A1_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif (defined (USE_IKS01A3))
      (void)IKS01A3_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif (defined (USE_IKS4A1))
      (void)IKS4A1_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif (defined (USE_IKS5A1))
      (void)IKS5A1_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif (defined (USE_SENSORTILEBOX))
      (void)BSP_MOTION_SENSOR_GetAxes(LSM6DSOX_0, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif (defined (USE_SENSORTILEBOXPRO))
      (void)BSP_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif (defined (USE_STWIN))
      (void)BSP_MOTION_SENSOR_GetAxes(ISM330DHCX_0, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif (defined (USE_STWINBOX))
      (void)BSP_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #else
    #error Not supported platform
  #endif
    
      sensor_hub_data.acceleration[0] = (&sensor_hub_data.acc)->x * FROM_MG_TO_G;
      sensor_hub_data.acceleration[1] = (&sensor_hub_data.acc)->y * FROM_MG_TO_G;
      sensor_hub_data.acceleration[2] = (&sensor_hub_data.acc)->z * FROM_MG_TO_G;
    }
    
    /* Accelerometer High-g Data */  
    if(sensor_hub_data.acceleration_enable == 1)
    {
  #if (defined (USE_SENSORTILEBOXPRO))
      (void)BSP_MOTION_SENSOR_ACC_HG_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif ((defined (USE_IKS5A1)) && defined (USE_ISM6HG256X))
      (void)IKS5A1_MOTION_SENSOR_ACC_HG_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #elif ((defined (USE_STWINBOX)) && defined (USE_ISM6HG256X))
      (void)BSP_MOTION_SENSOR_ACC_HG_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &sensor_hub_data.acc);
  #endif
    
      sensor_hub_data.acceleration_hg[0] = (&sensor_hub_data.acc)->x * FROM_MG_TO_G;
      sensor_hub_data.acceleration_hg[1] = (&sensor_hub_data.acc)->y * FROM_MG_TO_G;
      sensor_hub_data.acceleration_hg[2] = (&sensor_hub_data.acc)->z * FROM_MG_TO_G;
    }

    /* Gyroscope Data */
    if(sensor_hub_data.angular_rate_enable == 1)
    {
  #if (defined (USE_IKS02A1))
      (void)IKS02A1_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &sensor_hub_data.gyr);
  #elif (defined (USE_IKS01A3))
      (void)IKS01A3_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &sensor_hub_data.gyr);
  #elif (defined (USE_IKS4A1))
      (void)IKS4A1_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &sensor_hub_data.gyr);
  #elif (defined (USE_IKS5A1))
      (void)IKS5A1_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &sensor_hub_data.gyr);
  #elif (defined (USE_SENSORTILEBOX))
      (void)BSP_MOTION_SENSOR_GetAxes(LSM6DSOX_0, MOTION_GYRO, &sensor_hub_data.gyr);
  #elif (defined (USE_SENSORTILEBOXPRO))
      (void)BSP_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &sensor_hub_data.gyr);
  #elif (defined (USE_STWIN))
      (void)BSP_MOTION_SENSOR_GetAxes(ISM330DHCX_0, MOTION_GYRO, &sensor_hub_data.gyr);
  #elif (defined (USE_STWINBOX))
      (void)BSP_MOTION_SENSOR_GetAxes(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &sensor_hub_data.gyr);
  #else
    #error Not supported platform
  #endif

      sensor_hub_data.angular_rate[0] = (&sensor_hub_data.gyr)->x * FROM_MDPS_TO_DPS;
      sensor_hub_data.angular_rate[1] = (&sensor_hub_data.gyr)->y * FROM_MDPS_TO_DPS;
      sensor_hub_data.angular_rate[2] = (&sensor_hub_data.gyr)->z * FROM_MDPS_TO_DPS;
    }

    /* Magnetometer Data */
    if(sensor_hub_data.magnetic_field_enable == 1)
    {
  #if (defined (USE_IKS02A1))
      (void)IKS02A1_MOTION_SENSOR_GetAxes(IKS02A1_IIS2MDC_0, MOTION_MAGNETO, &sensor_hub_data.mag);
  #elif (defined (USE_IKS01A3))
      (void)IKS01A3_MOTION_SENSOR_GetAxes(IKS01A3_LIS2MDL_0, MOTION_MAGNETO, &sensor_hub_data.mag);
  #elif (defined (USE_IKS4A1))
      (void)IKS4A1_MOTION_SENSOR_GetAxes(IKS4A1_LIS2MDL_0, MOTION_MAGNETO, &sensor_hub_data.mag);
  #elif (defined (USE_IKS5A1))
      (void)IKS5A1_MOTION_SENSOR_GetAxes(IKS5A1_IIS2MDC_0, MOTION_MAGNETO, &sensor_hub_data.mag);
  #elif (defined (USE_SENSORTILEBOX))
      (void)BSP_MOTION_SENSOR_GetAxes(LIS2MDL_0, MOTION_MAGNETO, &sensor_hub_data.mag);
  #elif (defined (USE_SENSORTILEBOXPRO))
      (void)BSP_MOTION_SENSOR_GetAxes(LIS2MDL_0, MOTION_MAGNETO, &sensor_hub_data.mag);
  #elif (defined (USE_STWIN))
      (void)BSP_MOTION_SENSOR_GetAxes(IIS2MDC_0, MOTION_MAGNETO, &sensor_hub_data.mag);
  #elif (defined (USE_STWINBOX))
      (void)BSP_MOTION_SENSOR_GetAxes(IIS2MDC_0, MOTION_MAGNETO, &sensor_hub_data.mag);
  #else
    #error Not supported platform
  #endif

      sensor_hub_data.magnetic_field[0] = (&sensor_hub_data.mag)->x * FROM_MGAUSS_TO_UT;
      sensor_hub_data.magnetic_field[1] = (&sensor_hub_data.mag)->y * FROM_MGAUSS_TO_UT;
      sensor_hub_data.magnetic_field[2] = (&sensor_hub_data.mag)->z * FROM_MGAUSS_TO_UT;
    }

    /* Pressure Sensor Data */
    if(sensor_hub_data.pressure_enable == 1)
    {
  #if (defined (USE_IKS02A1))
      /* No pressure sensor */
  #elif (defined (USE_IKS01A3))
      (void)IKS01A3_ENV_SENSOR_GetValue(IKS01A3_LPS22HH_0, ENV_PRESSURE, &sensor_hub_data.pressure);
  #elif (defined (USE_IKS4A1))
      (void)IKS4A1_ENV_SENSOR_GetValue(IKS4A1_LPS22DF_0, ENV_PRESSURE, &sensor_hub_data.pressure);
  #elif (defined (USE_IKS5A1))
      (void)IKS5A1_ENV_SENSOR_GetValue(IKS5A1_ILPS22QS_0, ENV_PRESSURE, &sensor_hub_data.pressure);
  #elif (defined (USE_SENSORTILEBOX))
      (void)BSP_ENV_SENSOR_GetValue(LPS22HH_0, ENV_PRESSURE, &sensor_hub_data.pressure);
  #elif (defined (USE_SENSORTILEBOXPRO))
      (void)BSP_ENV_SENSOR_GetValue(LPS22DF_0, ENV_PRESSURE, &sensor_hub_data.pressure);
  #elif (defined (USE_STWIN))
      (void)BSP_ENV_SENSOR_GetValue(LPS22HH_0, ENV_PRESSURE, &sensor_hub_data.pressure);
  #elif (defined (USE_STWINBOX))
      (void)BSP_ENV_SENSOR_GetValue(ILPS22QS_0, ENV_PRESSURE, &sensor_hub_data.pressure);
  #else
    #error Not supported platform
  #endif
      
    }

    /* Humidity Sensor Data */
    if(sensor_hub_data.humidity_enable == 1)
    {
  #if (defined (USE_IKS02A1))
      /* No humidity sensor */
  #elif (defined (USE_IKS01A3))
      (void)IKS01A3_ENV_SENSOR_GetValue(IKS01A3_HTS221_0, ENV_HUMIDITY, &sensor_hub_data.humidity);
  #elif (defined (USE_IKS4A1))
      (void)IKS4A1_ENV_SENSOR_GetValue(IKS4A1_SHT40AD1B_0, ENV_HUMIDITY, &sensor_hub_data.humidity);
  #elif (defined (USE_IKS5A1))
      /* No humidity sensor */
  #elif (defined (USE_SENSORTILEBOX))
      (void)BSP_ENV_SENSOR_GetValue(HTS221_0, ENV_HUMIDITY, &sensor_hub_data.humidity);
  #elif (defined (USE_SENSORTILEBOXPRO))
      /* No humidity sensor */
  #elif (defined (USE_STWIN))
      (void)BSP_ENV_SENSOR_GetValue(HTS221_0, ENV_HUMIDITY, &sensor_hub_data.humidity);
  #elif (defined (USE_STWINBOX))
      /* No humidity sensor */
  #else
    #error Not supported platform
  #endif
    }

    /* Temperature Sensor Data */
    if(sensor_hub_data.temperature_enable == 1)
    {
  #if (defined (USE_IKS02A1))
      /* No temperature sensor */
  #elif (defined (USE_IKS01A3))
      (void)IKS01A3_ENV_SENSOR_GetValue(IKS01A3_HTS221_0, ENV_TEMPERATURE, &sensor_hub_data.temperature);
  #elif (defined (USE_IKS4A1))
      (void)IKS4A1_ENV_SENSOR_GetValue(IKS4A1_SHT40AD1B_0, ENV_TEMPERATURE, &sensor_hub_data.temperature);
  #elif (defined (USE_IKS5A1))
      /* No temperature sensor */
  #elif (defined (USE_SENSORTILEBOX))
      (void)BSP_ENV_SENSOR_GetValue(HTS221_0, ENV_TEMPERATURE, &sensor_hub_data.temperature);
  #elif (defined (USE_SENSORTILEBOXPRO))
      (void)BSP_ENV_SENSOR_GetValue(STTS22H_0, ENV_TEMPERATURE, &sensor_hub_data.temperature);
  #elif (defined (USE_STWIN))
      (void)BSP_ENV_SENSOR_GetValue(HTS221_0, ENV_TEMPERATURE, &sensor_hub_data.temperature);
  #elif (defined (USE_STWINBOX))
      (void)BSP_ENV_SENSOR_GetValue(STTS22H_0, ENV_TEMPERATURE, &sensor_hub_data.temperature);
  #else
    #error Not supported platform
  #endif
    }
  }
  
  /* FSM, MLC, ISPU */
  int i;
  
  if (sensor_hub_data.fsm_enable == 1)
  {
    for (i = 0; i < 16; i++)
    {
      sensor_hub_data.fsm_data[i] = 0;
    }
  }
  
  if (sensor_hub_data.mlc_enable == 1)
  {
    for (i = 0; i < 8; i++)
    {
      sensor_hub_data.mlc_data[i] = 0;
    }
  }
  #if (defined (USE_IKS02A1))
    #if (defined (USE_ISM330IS))
    if (sensor_hub_data.ispu_enable == 1)
    {
      (void)IKS02A1_MOTION_SENSOR_Write_Register(IKS02A1_ISM330IS_0, ISM330IS_FUNC_CFG_ACCESS, 0x80);
      for (i = 0; i < sensor_hub_data.ispu_data_size; i++)
      {
        (void)IKS02A1_MOTION_SENSOR_Read_Register(IKS02A1_ISM330IS_0, ISM330IS_ISPU_DOUT_00_L + i, &sensor_hub_data.ispu_data[i]);
      }
      (void)IKS02A1_MOTION_SENSOR_Write_Register(IKS02A1_ISM330IS_0, ISM330IS_FUNC_CFG_ACCESS, 0x00);
    }
    #endif
  #elif (defined (USE_IKS01A3))
    #if (defined (USE_LSM6DSO16IS))
    if (sensor_hub_data.ispu_enable == 1)
    {
      (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO16IS_0, LSM6DSO16IS_FUNC_CFG_ACCESS, 0x80);
      for (i = 0; i < sensor_hub_data.ispu_data_size; i++)
      {
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO16IS_0, LSM6DSO16IS_ISPU_DOUT_00_L + i, &sensor_hub_data.ispu_data[i]);
      }
      (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO16IS_0, LSM6DSO16IS_FUNC_CFG_ACCESS, 0x00);
    }
    #else
      if (sensor_hub_data.fsm_enable == 1)
      {
        (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FUNC_CFG_ACCESS, 0x80);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS9, &sensor_hub_data.fsm_data[8]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS10, &sensor_hub_data.fsm_data[9]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS11, &sensor_hub_data.fsm_data[10]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS12, &sensor_hub_data.fsm_data[11]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS13, &sensor_hub_data.fsm_data[12]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS14, &sensor_hub_data.fsm_data[13]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS15, &sensor_hub_data.fsm_data[14]);
        (void)IKS01A3_MOTION_SENSOR_Read_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FSM_OUTS16, &sensor_hub_data.fsm_data[15]);
        (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO_0, LSM6DSO_FUNC_CFG_ACCESS, 0x00);
      }
    #endif
  #elif (defined (USE_IKS4A1))
    #if (defined (USE_LSM6DSO16IS))
    if (sensor_hub_data.ispu_enable == 1)
    {
      (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSO16IS_0, LSM6DSO16IS_FUNC_CFG_ACCESS, 0x80);
      for (i = 0; i < sensor_hub_data.ispu_data_size; i++)
      {
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSO16IS_0, LSM6DSO16IS_ISPU_DOUT_00_L + i, &sensor_hub_data.ispu_data[i]);
      }
      (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSO16IS_0, LSM6DSO16IS_FUNC_CFG_ACCESS, 0x00);
    }
    #else
      if (sensor_hub_data.fsm_enable == 1)
      {
        (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FUNC_CFG_ACCESS, 0x80);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
        (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FUNC_CFG_ACCESS, 0x00);
      }
      
      if (sensor_hub_data.mlc_enable == 1)
      {
        (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FUNC_CFG_ACCESS, 0x80);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_MLC1_SRC, &sensor_hub_data.mlc_data[0]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_MLC2_SRC, &sensor_hub_data.mlc_data[1]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_MLC3_SRC, &sensor_hub_data.mlc_data[2]);
        (void)IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_MLC4_SRC, &sensor_hub_data.mlc_data[3]);
        (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSV16X_0, LSM6DSV16X_FUNC_CFG_ACCESS, 0x00);
      }
  
    #endif
  #elif (defined (USE_IKS5A1))
    #if (defined (USE_ISM330IS))
    if (sensor_hub_data.ispu_enable == 1)
    {
      (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM330IS_0, ISM330IS_FUNC_CFG_ACCESS, 0x80);
      for (i = 0; i < sensor_hub_data.ispu_data_size; i++)
      {
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM330IS_0, ISM330IS_ISPU_DOUT_00_L + i, &sensor_hub_data.ispu_data[i]);
      }
      (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM330IS_0, ISM330IS_FUNC_CFG_ACCESS, 0x00);
    }
    #else
      if (sensor_hub_data.fsm_enable == 1)
      {
        (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FUNC_CFG_ACCESS, 0x80);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
        (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FUNC_CFG_ACCESS, 0x00);
      }
      
      if (sensor_hub_data.mlc_enable == 1)
      {
        (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FUNC_CFG_ACCESS, 0x80);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_MLC1_SRC, &sensor_hub_data.mlc_data[0]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_MLC2_SRC, &sensor_hub_data.mlc_data[1]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_MLC3_SRC, &sensor_hub_data.mlc_data[2]);
        (void)IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_MLC4_SRC, &sensor_hub_data.mlc_data[3]);
        (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0, ISM6HG256X_FUNC_CFG_ACCESS, 0x00);
      }
  
    #endif
  #elif (defined (USE_SENSORTILEBOX))
  if (sensor_hub_data.fsm_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSOX_0, LSM6DSOX_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS9, &sensor_hub_data.fsm_data[8]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS10, &sensor_hub_data.fsm_data[9]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS11, &sensor_hub_data.fsm_data[10]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS12, &sensor_hub_data.fsm_data[11]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS13, &sensor_hub_data.fsm_data[12]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS14, &sensor_hub_data.fsm_data[13]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS15, &sensor_hub_data.fsm_data[14]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_FSM_OUTS16, &sensor_hub_data.fsm_data[15]);
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSOX_0, LSM6DSOX_FUNC_CFG_ACCESS, 0x00);
  }
  
  if (sensor_hub_data.mlc_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSOX_0, LSM6DSOX_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_MLC0_SRC, &sensor_hub_data.mlc_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_MLC1_SRC, &sensor_hub_data.mlc_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_MLC2_SRC, &sensor_hub_data.mlc_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_MLC3_SRC, &sensor_hub_data.mlc_data[3]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_MLC4_SRC, &sensor_hub_data.mlc_data[4]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_MLC5_SRC, &sensor_hub_data.mlc_data[5]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_MLC6_SRC, &sensor_hub_data.mlc_data[6]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSOX_0, LSM6DSOX_MLC7_SRC, &sensor_hub_data.mlc_data[7]);
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSOX_0, LSM6DSOX_FUNC_CFG_ACCESS, 0x00);
  }
  #elif (defined (USE_SENSORTILEBOXPRO))
  #if (defined (USE_LSM6DSO16IS))
  if (sensor_hub_data.ispu_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSO16IS_0, LSM6DSO16IS_FUNC_CFG_ACCESS, 0x80);
    for (i = 0; i < sensor_hub_data.ispu_data_size; i++)
    {
      (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSO16IS_0, LSM6DSO16IS_ISPU_DOUT_00_L + i, &sensor_hub_data.ispu_data[i]);
    }
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSO16IS_0, LSM6DSO16IS_FUNC_CFG_ACCESS, 0x00);
  }
  #elif (defined (USE_LSM6DSV320X))
  if (sensor_hub_data.fsm_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV320X_0, LSM6DSV320X_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV320X_0, LSM6DSV320X_FUNC_CFG_ACCESS, 0x00);
  }
  
  if (sensor_hub_data.mlc_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV320X_0, LSM6DSV320X_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_MLC1_SRC, &sensor_hub_data.mlc_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_MLC2_SRC, &sensor_hub_data.mlc_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_MLC3_SRC, &sensor_hub_data.mlc_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV320X_0, LSM6DSV320X_MLC4_SRC, &sensor_hub_data.mlc_data[3]);
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV320X_0, LSM6DSV320X_FUNC_CFG_ACCESS, 0x00);
  }
  #else  
  if (sensor_hub_data.fsm_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV16X_0, LSM6DSV16X_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV16X_0, LSM6DSV16X_FUNC_CFG_ACCESS, 0x00);
  }
  
  if (sensor_hub_data.mlc_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV16X_0, LSM6DSV16X_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_MLC1_SRC, &sensor_hub_data.mlc_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_MLC2_SRC, &sensor_hub_data.mlc_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_MLC3_SRC, &sensor_hub_data.mlc_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(LSM6DSV16X_0, LSM6DSV16X_MLC4_SRC, &sensor_hub_data.mlc_data[3]);
    (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV16X_0, LSM6DSV16X_FUNC_CFG_ACCESS, 0x00);
  }
  #endif
  #elif (defined (USE_STWIN))
  if (sensor_hub_data.fsm_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS9, &sensor_hub_data.fsm_data[8]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS10, &sensor_hub_data.fsm_data[9]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS11, &sensor_hub_data.fsm_data[10]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS12, &sensor_hub_data.fsm_data[11]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS13, &sensor_hub_data.fsm_data[12]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS14, &sensor_hub_data.fsm_data[13]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS15, &sensor_hub_data.fsm_data[14]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS16, &sensor_hub_data.fsm_data[15]);
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_FUNC_CFG_ACCESS, 0x00);
  }
  
  if (sensor_hub_data.mlc_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC0_SRC, &sensor_hub_data.mlc_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC1_SRC, &sensor_hub_data.mlc_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC2_SRC, &sensor_hub_data.mlc_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC3_SRC, &sensor_hub_data.mlc_data[3]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC4_SRC, &sensor_hub_data.mlc_data[4]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC5_SRC, &sensor_hub_data.mlc_data[5]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC6_SRC, &sensor_hub_data.mlc_data[6]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC7_SRC, &sensor_hub_data.mlc_data[7]);
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_FUNC_CFG_ACCESS, 0x00);
  }
  #elif (defined (USE_STWINBOX))
  #if (defined (USE_ISM330IS))
  if (sensor_hub_data.ispu_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330IS_0, ISM330IS_FUNC_CFG_ACCESS, 0x80);
    for (i = 0; i < sensor_hub_data.ispu_data_size; i++)
    {
      (void)BSP_MOTION_SENSOR_Read_Register(ISM330IS_0, ISM330IS_ISPU_DOUT_00_L + i, &sensor_hub_data.ispu_data[i]);
    }
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330IS_0, ISM330IS_FUNC_CFG_ACCESS, 0x00);
  }
  #elif (defined (USE_ISM6HG256X))
  	if (sensor_hub_data.fsm_enable == 1)
	{
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
	  (void)BSP_MOTION_SENSOR_Write_Register(ISM6HG256X_0, ISM6HG256X_FUNC_CFG_ACCESS, 0x80);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
	  (void)BSP_MOTION_SENSOR_Write_Register(ISM6HG256X_0, ISM6HG256X_FUNC_CFG_ACCESS, 0x00);
	}

	if (sensor_hub_data.mlc_enable == 1)
	{
	  (void)BSP_MOTION_SENSOR_Write_Register(ISM6HG256X_0, ISM6HG256X_FUNC_CFG_ACCESS, 0x80);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_MLC1_SRC, &sensor_hub_data.mlc_data[0]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_MLC2_SRC, &sensor_hub_data.mlc_data[1]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_MLC3_SRC, &sensor_hub_data.mlc_data[2]);
	  (void)BSP_MOTION_SENSOR_Read_Register(ISM6HG256X_0, ISM6HG256X_MLC4_SRC, &sensor_hub_data.mlc_data[3]);
	  (void)BSP_MOTION_SENSOR_Write_Register(ISM6HG256X_0, ISM6HG256X_FUNC_CFG_ACCESS, 0x00);
	}
  #else
  uint8_t dummy_byte;
  if (sensor_hub_data.fsm_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_WHO_AM_I, &dummy_byte);
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS1, &sensor_hub_data.fsm_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS2, &sensor_hub_data.fsm_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS3, &sensor_hub_data.fsm_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS4, &sensor_hub_data.fsm_data[3]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS5, &sensor_hub_data.fsm_data[4]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS6, &sensor_hub_data.fsm_data[5]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS7, &sensor_hub_data.fsm_data[6]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS8, &sensor_hub_data.fsm_data[7]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS9, &sensor_hub_data.fsm_data[8]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS10, &sensor_hub_data.fsm_data[9]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS11, &sensor_hub_data.fsm_data[10]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS12, &sensor_hub_data.fsm_data[11]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS13, &sensor_hub_data.fsm_data[12]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS14, &sensor_hub_data.fsm_data[13]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS15, &sensor_hub_data.fsm_data[14]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_FSM_OUTS16, &sensor_hub_data.fsm_data[15]);
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_FUNC_CFG_ACCESS, 0x00);
  }
  
  if (sensor_hub_data.mlc_enable == 1)
  {
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_WHO_AM_I, &dummy_byte);
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_FUNC_CFG_ACCESS, 0x80);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC0_SRC, &sensor_hub_data.mlc_data[0]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC1_SRC, &sensor_hub_data.mlc_data[1]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC2_SRC, &sensor_hub_data.mlc_data[2]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC3_SRC, &sensor_hub_data.mlc_data[3]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC4_SRC, &sensor_hub_data.mlc_data[4]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC5_SRC, &sensor_hub_data.mlc_data[5]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC6_SRC, &sensor_hub_data.mlc_data[6]);
    (void)BSP_MOTION_SENSOR_Read_Register(ISM330DHCX_0, ISM330DHCX_MLC7_SRC, &sensor_hub_data.mlc_data[7]);
    (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, ISM330DHCX_FUNC_CFG_ACCESS, 0x00);
  }
  #endif
  #else
    #error Not supported platform
  #endif
  
  /* Execute algorithms at 16Hz */
  if (update_16Hz == 1)
  {
    update_16Hz = 0;
    Algo_16Hz_Handler();
  }

  /* Execute algorithms at 25Hz */
  if (update_25Hz == 1)
  {
    update_25Hz = 0;
    Algo_25Hz_Handler();
  }

  /* Execute algorithms at 50Hz */
  if (update_50Hz == 1)
  {
    update_50Hz = 0;
    Algo_50Hz_Handler();
  }

  /* Execute algorithms at 100Hz */
  if (update_100Hz == 1)
  {
    update_100Hz = 0;
    Algo_100Hz_Handler();
  }
  
  sensor_hub_data.iteration_counter = sensor_hub_data.iteration_counter + 1;
}

/**
 * @brief 
 */
void Accelero_Init(void)
{
  sensor_hub_data.acceleration_enable = 1;
}

/**
 * @brief 
 */
void Accelero_HG_Init(void)
{
  sensor_hub_data.acceleration_hg_enable = 1;
}

/**
 * @brief 
 */
void Gyro_Init(void)
{
  sensor_hub_data.angular_rate_enable = 1;
}

/**
 * @brief 
 */
void Magneto_Init(void)
{
  sensor_hub_data.magnetic_field_enable = 1;
}

/**
 * @brief 
 */
void Pressure_Init(void)
{
  sensor_hub_data.pressure_enable = 1;
}

/**
 * @brief 
 */
void Temperature_Init(void)
{
  sensor_hub_data.temperature_enable = 1;
}

/**
 * @brief 
 */
void Humidity_Init(void)
{
  sensor_hub_data.humidity_enable = 1;
}

/**
 * @brief  Configure high-g accelerometer
 */
void Accelero_HG_Config(uint32_t hg_accel_fs)
{
  #if (defined (USE_LSM6DSV320X))
  BSP_MOTION_SENSOR_ACC_HG_SetFullScale(LSM6DSV320X_0, MOTION_ACCELERO, hg_accel_fs); 
  #endif

  #if (defined (USE_ISM6HG256X))
    #if (defined (USE_IKS5A1))
    IKS5A1_MOTION_SENSOR_ACC_HG_SetFullScale(IKS5A1_ISM6HG256X_0, MOTION_ACCELERO, hg_accel_fs);
    #elif (defined (USE_STWINBOX))
    BSP_MOTION_SENSOR_ACC_HG_SetFullScale(ISM6HG256X_0, MOTION_ACCELERO, hg_accel_fs);
    #endif
  #endif   
}

/**
 * @brief  Handler for algorithms which should be called at 16Hz
 */
void Algo_16Hz_Handler(void)
{
  #if (MotionAW)
  if (sensor_hub_data.motion_aw_enable == 1) MotionAW_Update_Data();
  #endif
  
  #if (MotionID)
  if (sensor_hub_data.motion_id_enable == 1) MotionID_Update_Data();
  #endif
}

/**
 * @brief  Handler for algorithms which should be called at 25Hz
 */
void Algo_25Hz_Handler(void)
{
  #if (MotionTL)
  if (sensor_hub_data.motion_tl_enable == 1) MotionTL_Update_Data();
  #endif
  #if (MotionMC)
  if (sensor_hub_data.motion_mc_enable == 1) MotionMC_Update_Data();
  #endif
}

/**
 * @brief  Handler for algorithms which should be called at 50Hz
 */
void Algo_50Hz_Handler(void)
{
  #if (MotionAC)
  if (sensor_hub_data.motion_ac_enable == 1) MotionAC_Update_Data();
  #endif
  #if (MotionGC)
  if (sensor_hub_data.motion_gc_enable == 1) MotionGC_Update_Data();
  #endif
  #if (MotionPM)
  if (sensor_hub_data.motion_pm_enable == 1) MotionPM_Update_Data();
  #endif
  #if (MotionPW)
  if (sensor_hub_data.motion_pw_enable == 1) MotionPW_Update_Data();
  #endif
}

/**
 * @brief  Handler for algorithms which should be called at 100Hz
 */
void Algo_100Hz_Handler(void)
{
  #if (MotionEC)
  if (sensor_hub_data.motion_ec_enable == 1) MotionEC_Update_Data();
  #endif
  #if (MotionFX_9X)
  if (sensor_hub_data.motion_fx_9x_enable == 1) MotionFX_9X_Update_Data();
  #endif
  #if (MotionFX_6X)
  if (sensor_hub_data.motion_fx_6x_enable == 1) MotionFX_6X_Update_Data();
  #endif
}

#if (MotionAC)
/**
 * @brief  Accelerometer calibration initialization
 */
void MotionAC_Init(uint32_t mode, float threshold)
{
  if (sensor_hub_data.motion_ac_enable == 0)
  {
    MAC_knobs_t knobs;

    MotionAC_Initialize(1);
    
    MotionAC_GetKnobs(&knobs);
    
    knobs.Run6PointCal = mode;
    knobs.Sample_ms = 20;
    knobs.MoveThresh_g = threshold;
    
    MotionAC_SetKnobs(&knobs);

    sensor_hub_data.motion_ac_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
  }
}

/**
 * @brief  Accelerometer calibration data update
 */
void MotionAC_Update_Data(void)
{
  MAC_input_t data_in;
  uint8_t is_calibrated;

  data_in.Acc[0] = sensor_hub_data.acceleration[0];
  data_in.Acc[1] = sensor_hub_data.acceleration[1];
  data_in.Acc[2] = sensor_hub_data.acceleration[2];

  MotionAC_Update(&data_in, &is_calibrated);
  MotionAC_GetCalParams(&sensor_hub_data.mac);
}
#endif

#if (MotionAW)
/**
 * @brief  Activity recognition for wrist algorithm initialization
 */
void MotionAW_Init(void)
{
  if (sensor_hub_data.motion_aw_enable == 0)
  {
    char acc_orientation[3];

    MotionAW_Initialize();

    acc_orientation[0] = ACC_ORIENTATION_X;
    acc_orientation[1] = ACC_ORIENTATION_Y;
    acc_orientation[2] = ACC_ORIENTATION_Z;

    MotionAW_SetOrientation_Acc(acc_orientation);

    sensor_hub_data.motion_aw_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
  }
}

/**
 * @brief  Activity recognition for wrist data update
 */
void MotionAW_Update_Data(void)
{
  MAW_input_t data_in;
  static int64_t time_stamp;

  data_in.AccX = sensor_hub_data.acceleration[0];
  data_in.AccY = sensor_hub_data.acceleration[1];
  data_in.AccZ = sensor_hub_data.acceleration[2];

  MotionAW_Update(&data_in, &sensor_hub_data.maw, time_stamp);
  time_stamp = time_stamp + 63;
}
#endif

#if (MotionEC)
/**
 * @brief  ECompass algorithm initialization
 */
void MotionEC_Init(void)
{ 
  if (sensor_hub_data.motion_ec_enable == 0)
  {
    float freq = 100.0f;
    char acc_orientation[4];
    char mag_orientation[4];
    
    MotionEC_Initialize(MEC_MCU_STM32, &freq);
    MotionEC_SetOrientationEnable(MEC_ENABLE);
    MotionEC_SetVirtualGyroEnable(MEC_ENABLE);
    MotionEC_SetGravityEnable(MEC_ENABLE);
    MotionEC_SetLinearAccEnable(MEC_ENABLE);
    
    acc_orientation[0] = ACC_ORIENTATION_X;
    acc_orientation[1] = ACC_ORIENTATION_Y;
    acc_orientation[2] = ACC_ORIENTATION_Z;
    
    mag_orientation[0] = MAG_ORIENTATION_X;
    mag_orientation[1] = MAG_ORIENTATION_Y;
    mag_orientation[2] = MAG_ORIENTATION_Z;

    Create_Rotation_Matrix(acc_orientation, sensor_hub_data.acc_matrix);
    Create_Rotation_Matrix(mag_orientation, sensor_hub_data.mag_matrix);
  
    sensor_hub_data.motion_ec_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
    sensor_hub_data.magnetic_field_enable = 1;
    
    MotionMC_Init();
  }
}

/**
 * @brief  ECompass algorithm data update
 */
void MotionEC_Update_Data(void)
{
  MEC_input_t mec_data_in;
  float cal_mag_data[3];

  Axis_Transformation(mec_data_in.acc, sensor_hub_data.acceleration, sensor_hub_data.acc_matrix);

  cal_mag_data[0] = sensor_hub_data.magnetic_field[0] - sensor_hub_data.mmc.HI_Bias[0];
  cal_mag_data[1] = sensor_hub_data.magnetic_field[1] - sensor_hub_data.mmc.HI_Bias[1];
  cal_mag_data[2] = sensor_hub_data.magnetic_field[2] - sensor_hub_data.mmc.HI_Bias[2];
  
  Axis_Transformation(mec_data_in.mag, cal_mag_data, sensor_hub_data.mag_matrix);
  
  mec_data_in.deltatime_s = 10.0f;
    
  MotionEC_Run(&mec_data_in, &sensor_hub_data.mec);
}
#endif

#if (MotionFX_9X)
/**
 * @brief  Sensor fusion algorithm initialization
 */
void MotionFX_9X_Init(void)
{
  if (sensor_hub_data.motion_fx_9x_enable == 0)
  {
    MFX_knobs_t iKnobs;
    MFX_knobs_t *ipKnobs = &iKnobs;

    MotionFX_initialize((MFXState_t *)mfxstate_9x);

    MotionFX_getKnobs(mfxstate_9x, ipKnobs);

    ipKnobs->gbias_acc_th_sc = GBIAS_ACC_TH_SC_9X;
    ipKnobs->gbias_gyro_th_sc = GBIAS_GYRO_TH_SC_9X;
    ipKnobs->gbias_mag_th_sc = GBIAS_MAG_TH_SC_9X;

    ipKnobs->acc_orientation[0] = ACC_ORIENTATION_X;
    ipKnobs->acc_orientation[1] = ACC_ORIENTATION_Y;
    ipKnobs->acc_orientation[2] = ACC_ORIENTATION_Z;

    ipKnobs->gyro_orientation[0] = GYR_ORIENTATION_X;
    ipKnobs->gyro_orientation[1] = GYR_ORIENTATION_Y;
    ipKnobs->gyro_orientation[2] = GYR_ORIENTATION_Z;

    ipKnobs->mag_orientation[0] = MAG_ORIENTATION_X;
    ipKnobs->mag_orientation[1] = MAG_ORIENTATION_Y;
    ipKnobs->mag_orientation[2] = MAG_ORIENTATION_Z;  

    ipKnobs->output_type = MFX_ENGINE_OUTPUT_ENU;
    ipKnobs->LMode = 1;
    ipKnobs->modx = 1;

    MotionFX_setKnobs(mfxstate_9x, ipKnobs);

    MotionFX_enable_6X(mfxstate_9x, MFX_ENGINE_DISABLE);
    MotionFX_enable_9X(mfxstate_9x, MFX_ENGINE_ENABLE);

    MotionFX_MagCal_init(10, 1);

    sensor_hub_data.motion_fx_9x_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
    sensor_hub_data.angular_rate_enable = 1;
    sensor_hub_data.magnetic_field_enable = 1;
  }
}

/**
 * @brief  Sensor fusion algorithm data update
 */
void MotionFX_9X_Update_Data(void)
{
  static uint32_t time_stamp_index;

  /* Magnetometer Calibration */
  MFX_MagCal_input_t mag_data_in;

  mag_data_in.mag[0] = sensor_hub_data.magnetic_field[0] * FROM_UT_TO_UT50;
  mag_data_in.mag[1] = sensor_hub_data.magnetic_field[1] * FROM_UT_TO_UT50;
  mag_data_in.mag[2] = sensor_hub_data.magnetic_field[2] * FROM_UT_TO_UT50;
  mag_data_in.time_stamp = (int) (time_stamp_index * 10);
  time_stamp_index++;

  MotionFX_MagCal_run(&mag_data_in);
  MotionFX_MagCal_getParams(&sensor_hub_data.mfx_magcal);

  /* Sensor Fusion */
  MFX_input_t mfx_data_in;

  mfx_data_in.acc[0] = sensor_hub_data.acceleration[0];
  mfx_data_in.acc[1] = sensor_hub_data.acceleration[1];
  mfx_data_in.acc[2] = sensor_hub_data.acceleration[2];

  mfx_data_in.gyro[0] = sensor_hub_data.angular_rate[0];
  mfx_data_in.gyro[1] = sensor_hub_data.angular_rate[1];
  mfx_data_in.gyro[2] = sensor_hub_data.angular_rate[2];
  
  mfx_data_in.mag[0] = (sensor_hub_data.magnetic_field[0] - (sensor_hub_data.mfx_magcal.hi_bias[0] * FROM_UT50_TO_UT)) * FROM_UT_TO_UT50;
  mfx_data_in.mag[1] = (sensor_hub_data.magnetic_field[1] - (sensor_hub_data.mfx_magcal.hi_bias[1] * FROM_UT50_TO_UT)) * FROM_UT_TO_UT50;
  mfx_data_in.mag[2] = (sensor_hub_data.magnetic_field[2] - (sensor_hub_data.mfx_magcal.hi_bias[2] * FROM_UT50_TO_UT)) * FROM_UT_TO_UT50;

  float delta_time = 0.01f;
  
  MotionFX_propagate(mfxstate_9x, &sensor_hub_data.mfx_9x, &mfx_data_in, &delta_time);
  MotionFX_update(mfxstate_9x, &sensor_hub_data.mfx_9x, &mfx_data_in, &delta_time, NULL);
}
#endif

#if (MotionFX_6X)
/**
 * @brief  Sensor fusion algorithm initialization
 */
void MotionFX_6X_Init(void)
{
  if (sensor_hub_data.motion_fx_6x_enable == 0)
  {
    MFX_knobs_t iKnobs;
    MFX_knobs_t *ipKnobs = &iKnobs;

    MotionFX_initialize((MFXState_t *)mfxstate_6x);

    MotionFX_getKnobs(mfxstate_6x, ipKnobs);

    ipKnobs->gbias_acc_th_sc = GBIAS_ACC_TH_SC_9X;
    ipKnobs->gbias_gyro_th_sc = GBIAS_GYRO_TH_SC_9X;
    ipKnobs->gbias_mag_th_sc = GBIAS_MAG_TH_SC_9X;

    ipKnobs->acc_orientation[0] = ACC_ORIENTATION_X;
    ipKnobs->acc_orientation[1] = ACC_ORIENTATION_Y;
    ipKnobs->acc_orientation[2] = ACC_ORIENTATION_Z;

    ipKnobs->gyro_orientation[0] = GYR_ORIENTATION_X;
    ipKnobs->gyro_orientation[1] = GYR_ORIENTATION_Y;
    ipKnobs->gyro_orientation[2] = GYR_ORIENTATION_Z;

    ipKnobs->mag_orientation[0] = MAG_ORIENTATION_X;
    ipKnobs->mag_orientation[1] = MAG_ORIENTATION_Y;
    ipKnobs->mag_orientation[2] = MAG_ORIENTATION_Z;  

    ipKnobs->output_type = MFX_ENGINE_OUTPUT_ENU;
    ipKnobs->LMode = 1;
    ipKnobs->modx = 1;

    MotionFX_setKnobs(mfxstate_6x, ipKnobs);

    MotionFX_enable_6X(mfxstate_6x, MFX_ENGINE_ENABLE);
    MotionFX_enable_9X(mfxstate_6x, MFX_ENGINE_DISABLE);

    sensor_hub_data.motion_fx_6x_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
    sensor_hub_data.angular_rate_enable = 1;
  }
}

/**
 * @brief  Sensor fusion algorithm data update
 */
void MotionFX_6X_Update_Data(void)
{
  /* Sensor Fusion */
  MFX_input_t mfx_data_in;

  mfx_data_in.acc[0] = sensor_hub_data.acceleration[0];
  mfx_data_in.acc[1] = sensor_hub_data.acceleration[1];
  mfx_data_in.acc[2] = sensor_hub_data.acceleration[2];

  mfx_data_in.gyro[0] = sensor_hub_data.angular_rate[0];
  mfx_data_in.gyro[1] = sensor_hub_data.angular_rate[1];
  mfx_data_in.gyro[2] = sensor_hub_data.angular_rate[2];
  
  mfx_data_in.mag[0] = 0;
  mfx_data_in.mag[1] = 0;
  mfx_data_in.mag[2] = 0;

  float delta_time = 0.01f;
  
  MotionFX_propagate(mfxstate_6x, &sensor_hub_data.mfx_6x, &mfx_data_in, &delta_time);
  MotionFX_update(mfxstate_6x, &sensor_hub_data.mfx_6x, &mfx_data_in, &delta_time, NULL);
}
#endif

#if (MotionGC)
/**
 * @brief  Gyroscope calibration algorithm initialization
 */
void MotionGC_Init(float acc_thr, float gyro_thr, float filter_const, int fast_start, float max_acc, float max_gyro)
{
  float frequency = (float)sensor_hub_data.data_rate_Hz;
  
  if (sensor_hub_data.motion_gc_enable == 0)
  {
    MGC_knobs_t mgc_knobs;

    MotionGC_Initialize(MGC_MCU_STM32, &frequency);
    MotionGC_GetKnobs(&mgc_knobs);
    mgc_knobs.AccThr = acc_thr;
    mgc_knobs.GyroThr = gyro_thr;
    mgc_knobs.FilterConst = filter_const;
    mgc_knobs.FastStart = fast_start;
    mgc_knobs.MaxAcc = max_acc;
    mgc_knobs.MaxGyro = max_gyro;
    MotionGC_SetKnobs(&mgc_knobs);

    sensor_hub_data.motion_gc_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
    sensor_hub_data.angular_rate_enable = 1;
  }
}

/**
 * @brief  Gyroscope calibration algorithm data update
 */
void MotionGC_Update_Data(void)
{
  MGC_input_t mgc_data_in;
  int bias_update;

  mgc_data_in.Acc[0] = sensor_hub_data.acceleration[0];
  mgc_data_in.Acc[1] = sensor_hub_data.acceleration[1];
  mgc_data_in.Acc[2] = sensor_hub_data.acceleration[2];

  mgc_data_in.Gyro[0] = sensor_hub_data.angular_rate[0];
  mgc_data_in.Gyro[1] = sensor_hub_data.angular_rate[1];
  mgc_data_in.Gyro[2] = sensor_hub_data.angular_rate[2];

  MotionGC_Update(&mgc_data_in, &sensor_hub_data.mgc, &bias_update);
}
#endif

#if (MotionID)
/**
 * @brief  Motion intensity detection algorithm initialization
 */
void MotionID_Init(void)
{
  if (sensor_hub_data.motion_id_enable == 0)
  {
    MotionID_Initialize(MID_MCU_STM32);

    sensor_hub_data.motion_id_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
  }
}

/**
 * @brief  Motion intensity detection algorithm data update
 */
void MotionID_Update_Data(void)
{
  MID_input_t data_in;

  data_in.AccX = sensor_hub_data.acceleration[0];
  data_in.AccY = sensor_hub_data.acceleration[1];
  data_in.AccZ = sensor_hub_data.acceleration[2];

  MotionID_Update(&data_in, &sensor_hub_data.mid);
}
#endif

#if (MotionMC)
/**
 * @brief  Magnetometer calibration algorithm initialization
 */
void MotionMC_Init(void)
{
  if (sensor_hub_data.motion_mc_enable == 0)
  {
    MotionMC_Initialize(10, 1);

    sensor_hub_data.motion_mc_enable = 1;
    sensor_hub_data.magnetic_field_enable = 1;
  }
}

/**
 * @brief  Magnetometer calibration algorithm data update
 */
void MotionMC_Update_Data(void)
{
  static uint32_t time_stamp_index;

  MMC_Input_t data_in;

  data_in.Mag[0] = sensor_hub_data.magnetic_field[0];
  data_in.Mag[1] = sensor_hub_data.magnetic_field[1];
  data_in.Mag[2] = sensor_hub_data.magnetic_field[2];
  data_in.TimeStamp = (int) (time_stamp_index * 10);
  time_stamp_index++;

  MotionMC_Update(&data_in);
  MotionMC_GetCalParams(&sensor_hub_data.mmc);
}
#endif

#if (MotionPM)
/**
 * @brief  Pedometer for mobile algorithm initialization
 */
void MotionPM_Init(void)
{
  if (sensor_hub_data.motion_pm_enable == 0)
  {
    MotionPM_Initialize();

    sensor_hub_data.motion_pm_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
  }
}

/**
 * @brief  Pedometer for mobile algorithm data update
 */
void MotionPM_Update_Data(void)
{
  MPM_input_t data_in;

  data_in.AccX = sensor_hub_data.acceleration[0];
  data_in.AccY = sensor_hub_data.acceleration[1];
  data_in.AccZ = sensor_hub_data.acceleration[2];

  MotionPM_Update(&data_in, &sensor_hub_data.mpm);
}
#endif

#if (MotionPW)
/**
 * @brief  Pedometer for wrist algorithm initialization
 */
void MotionPW_Init(int32_t activity_recognition)
{
  if (sensor_hub_data.motion_pw_enable == 0)
  {
    MotionPW_Initialize();
    MotionPW_ResetStepCount();
    MotionPW_ResetPedometerLibrary();

    sensor_hub_data.motion_pw_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
    
    if (activity_recognition == 1)
    {
      sensor_hub_data.activity_recognition_enable = 1;
      MotionAW_Init();
    }
    else
    {
      sensor_hub_data.activity_recognition_enable = 0;
    }
  }
}

/**
 * @brief  Pedometer for wrist algorithm data update
 */
void MotionPW_Update_Data(void)
{
  MPW_input_t data_in;
  int32_t activity_conversion = 0;

  data_in.AccX = sensor_hub_data.acceleration[0];
  data_in.AccY = sensor_hub_data.acceleration[1];
  data_in.AccZ = sensor_hub_data.acceleration[2];
  
  if (sensor_hub_data.activity_recognition_enable == 1)
  {
    /* Convert current activity number */
    activity_conversion = (int32_t)sensor_hub_data.maw.current_activity - 4;
    
    if ((activity_conversion < (int32_t)MPW_UNKNOWN_ACTIVITY) || (activity_conversion > (int32_t)MPW_JOGGING))
    {
      activity_conversion = (int32_t)MPW_UNKNOWN_ACTIVITY;
    }
    
    data_in.CurrentActivity = (MPW_activity_t)activity_conversion;
  }
  else
  {
    data_in.CurrentActivity = MPW_WALKING;
  }
  
  MotionPW_Update(&data_in, &sensor_hub_data.mpw);
}
#endif

#if (MotionTL)
/**
 * @brief  Tilt sensing algorithm initialization
 */
void MotionTL_Init(int32_t mode)
{
  if (sensor_hub_data.motion_tl_enable == 0)
  {
    char acc_orientation[3];

    acc_orientation[0] = ACC_ORIENTATION_X;
    acc_orientation[1] = ACC_ORIENTATION_Y;
    acc_orientation[2] = ACC_ORIENTATION_Z;
    
    MotionTL_Initialize(MTL_MCU_STM32, acc_orientation);
    MotionTL_SetOrientation_Acc(acc_orientation);
    
    if (mode == 0)
    {
      sensor_hub_data.mtl_mode = MODE_PITCH_ROLL_GRAVITY_INCLINATION;
    }
    else if (mode == 1)
    {
      sensor_hub_data.mtl_mode = MODE_THETA_PSI_PHI;
    }
    else
    {
      sensor_hub_data.mtl_mode = MODE_THETA_PSI_PHI;
    }  
    
    sensor_hub_data.motion_tl_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
  }
}

/**
 * @brief  Tilt sensing algorithm data update
 */
void MotionTL_Update_Data(void)
{
  MTL_input_t data_in;
  static uint64_t timestamp = 0;

  data_in.acc_x = sensor_hub_data.acceleration[0];
  data_in.acc_y = sensor_hub_data.acceleration[1];
  data_in.acc_z = sensor_hub_data.acceleration[2];
  timestamp = timestamp + 40;

  MotionTL_Update(&data_in, timestamp, &sensor_hub_data.mtl);
}
#endif

/**
 * @brief  Get acceleration value
 */
void Accelero_Sensor_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->acceleration[0];
  data[1] = psensor_hub_data->acceleration[1];
  data[2] = psensor_hub_data->acceleration[2];
}

/**
 * @brief  Get high-g acceleration value
 */
void Accelero_HG_Sensor_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->acceleration_hg[0];
  data[1] = psensor_hub_data->acceleration_hg[1];
  data[2] = psensor_hub_data->acceleration_hg[2];
}

/**
 * @brief  Get angular rate value
 */
void Gyro_Sensor_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->angular_rate[0];
  data[1] = psensor_hub_data->angular_rate[1];
  data[2] = psensor_hub_data->angular_rate[2];
}

/**
 * @brief  Get magnetic field value
 */

void Magneto_Sensor_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->magnetic_field[0];
  data[1] = psensor_hub_data->magnetic_field[1];
  data[2] = psensor_hub_data->magnetic_field[2];
}

/**
 * @brief  Get pressure value
 */

void Pressure_Sensor_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  *data = psensor_hub_data->pressure;
}

/**
 * @brief  Get temperature value
 */

void Temperature_Sensor_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  *data = psensor_hub_data->temperature;
}

/**
 * @brief  Get humidity value
 */

void Humidity_Sensor_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  *data = psensor_hub_data->humidity;
}

#if (MotionAC)
/**
 * @brief  Get calibrated acceleration from accelerometer calibration library
 */
void AccCal_GetData(void *pdata, int32_t *reset, float *data1, int32_t *data2)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  
  data1[0] = (psensor_hub_data->acceleration[0] - psensor_hub_data->mac.AccBias[0]) * psensor_hub_data->mac.SF_Matrix[0][0];
  data1[1] = (psensor_hub_data->acceleration[1] - psensor_hub_data->mac.AccBias[1]) * psensor_hub_data->mac.SF_Matrix[1][1];
  data1[2] = (psensor_hub_data->acceleration[2] - psensor_hub_data->mac.AccBias[2]) * psensor_hub_data->mac.SF_Matrix[2][2];
  
  data2[0] = (int32_t) (psensor_hub_data->mac.CalQuality);

  if (*reset == 1)
  {
    MAC_knobs_t mac_knobs;
    MotionAC_GetKnobs(&mac_knobs);
    MotionAC_Initialize(0);
    MotionAC_Initialize(1);
    MotionAC_SetKnobs(&mac_knobs);
  }
}
#endif

#if (MotionAW)
/**
 * @brief  Get activity index from activity recognition for wrist library
 */
void ActivityWrist_GetData(void *pdata, int32_t *reset, int32_t *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = (int32_t) (psensor_hub_data->maw.current_activity);

  if (*reset == 1)
  {
    MotionAW_Reset();
  }
}
#endif

#if (MotionEC)
/**
 * @brief  Get quaternions from ecompass library
 */
void MotionEC_Quternions_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mec.quaternion[0];
  data[1] = psensor_hub_data->mec.quaternion[1];
  data[2] = psensor_hub_data->mec.quaternion[2];
  data[3] = psensor_hub_data->mec.quaternion[3];
}

/**
 * @brief  Get rotation vector from ecompass library
 */
void MotionEC_Rotation_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mec.euler[0];
  data[1] = psensor_hub_data->mec.euler[1];
  data[2] = psensor_hub_data->mec.euler[2];
}

/**
 * @brief  Get gravity vector from ecompass library
 */
void MotionEC_Gravity_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mec.gravity[0];
  data[1] = psensor_hub_data->mec.gravity[1];
  data[2] = psensor_hub_data->mec.gravity[2];
}

/**
 * @brief  Get linear acceleration from ecompass library
 */
void MotionEC_LinearAcceleration_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mec.linear[0];
  data[1] = psensor_hub_data->mec.linear[1];
  data[2] = psensor_hub_data->mec.linear[2];
}

/**
 * @brief  Get virtual gyroscope from ecompass library
 */
void MotionEC_VirtualGyroscope_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mec.i_gyro[0];
  data[1] = psensor_hub_data->mec.i_gyro[1];
  data[2] = psensor_hub_data->mec.i_gyro[2];
}
#endif

#if (MotionFX_9X)
/**
 * @brief  Get quaternions from sensor fusion library
 */
void Quaternions9X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_9x.quaternion[0];
  data[1] = psensor_hub_data->mfx_9x.quaternion[1];
  data[2] = psensor_hub_data->mfx_9x.quaternion[2];
  data[3] = psensor_hub_data->mfx_9x.quaternion[3];
}

/**
 * @brief  Get rotation vector from sensor fusion library
 */
void Rotation9X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_9x.rotation[0];
  data[1] = psensor_hub_data->mfx_9x.rotation[1];
  data[2] = psensor_hub_data->mfx_9x.rotation[2];
}

/**
 * @brief  Get gravity vector from sensor fusion library
 */
void Gravity9X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_9x.gravity[0];
  data[1] = psensor_hub_data->mfx_9x.gravity[1];
  data[2] = psensor_hub_data->mfx_9x.gravity[2];
}

/**
 * @brief  Get linear acceleration from sensor fusion library
 */
void LinearAcceleration9X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_9x.linear_acceleration[0];
  data[1] = psensor_hub_data->mfx_9x.linear_acceleration[1];
  data[2] = psensor_hub_data->mfx_9x.linear_acceleration[2];
}

/**
 * @brief  Get heading from sensor fusion library
 */
void Heading9X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  *data = psensor_hub_data->mfx_9x.heading;
}
#endif

#if (MotionFX_9X)
/**
 * @brief  Get calibrated magnetometer from sensor fusion library
 */
void MagnetoCal_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->magnetic_field[0] - (psensor_hub_data->mfx_magcal.hi_bias[0] * FROM_UT50_TO_UT);
  data[1] = psensor_hub_data->magnetic_field[1] - (psensor_hub_data->mfx_magcal.hi_bias[1] * FROM_UT50_TO_UT);
  data[2] = psensor_hub_data->magnetic_field[2] - (psensor_hub_data->mfx_magcal.hi_bias[2] * FROM_UT50_TO_UT);  
}

/**
 * @brief  Get calibration parameters from sensor fusion library
 */
void MagnetoCal_GetCalData(void *pdata, float *data, int32_t *quality)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_magcal.hi_bias[0] * FROM_UT50_TO_UT;
  data[1] = psensor_hub_data->mfx_magcal.hi_bias[1] * FROM_UT50_TO_UT;
  data[2] = psensor_hub_data->mfx_magcal.hi_bias[2] * FROM_UT50_TO_UT;

  *quality = (int32_t) (psensor_hub_data->mfx_magcal.cal_quality);
}
#endif

#if (MotionFX_6X)
/**
 * @brief  Get quaternions from sensor fusion library
 */
void Quaternions6X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_6x.quaternion[0];
  data[1] = psensor_hub_data->mfx_6x.quaternion[1];
  data[2] = psensor_hub_data->mfx_6x.quaternion[2];
  data[3] = psensor_hub_data->mfx_6x.quaternion[3];
}

/**
 * @brief  Get rotation vector from sensor fusion library
 */
void Rotation6X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_6x.rotation[0];
  data[1] = psensor_hub_data->mfx_6x.rotation[1];
  data[2] = psensor_hub_data->mfx_6x.rotation[2];
}

/**
 * @brief  Get gravity vector from sensor fusion library
 */
void Gravity6X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_6x.gravity[0];
  data[1] = psensor_hub_data->mfx_6x.gravity[1];
  data[2] = psensor_hub_data->mfx_6x.gravity[2];
}

/**
 * @brief  Get linear acceleration from sensor fusion library
 */
void LinearAcceleration6X_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->mfx_6x.linear_acceleration[0];
  data[1] = psensor_hub_data->mfx_6x.linear_acceleration[1];
  data[2] = psensor_hub_data->mfx_6x.linear_acceleration[2];
}
#endif

#if (MotionGC)
/**
 * @brief  Get calibrated angular rate from gyroscope calibration library
 */
void GyroCal_GetData(void *pdata, int32_t *reset, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = psensor_hub_data->angular_rate[0] - psensor_hub_data->mgc.GyroBiasX;
  data[1] = psensor_hub_data->angular_rate[1] - psensor_hub_data->mgc.GyroBiasY;
  data[2] = psensor_hub_data->angular_rate[2] - psensor_hub_data->mgc.GyroBiasZ;
  
  float frequency = (float)sensor_hub_data.data_rate_Hz;

  if (*reset == 1)
  {
    MGC_knobs_t mgc_knobs;
    MotionGC_GetKnobs(&mgc_knobs);
    MotionGC_Initialize(MGC_MCU_STM32, &frequency);
    MotionGC_SetKnobs(&mgc_knobs);
  }
}
#endif

#if (MotionID)
/**
 * @brief  Get motion intensity index from motion intensity detection library
 */
void MotionIntensity_GetData(void *pdata, int32_t *reset, int32_t *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data[0] = (int32_t) (psensor_hub_data->mid);

  if (*reset == 1)
  {
    MotionID_ResetLib();
  }
}
#endif

#if (MotionMC)
/**
 * @brief  Get calibrated magnetic field and calibration quality from magnetometer calibration library
 */
void MagCal_GetData(void *pdata, int32_t *reset, float *data1, int32_t *data2)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data1[0] = psensor_hub_data->magnetic_field[0] - psensor_hub_data->mmc.HI_Bias[0];
  data1[1] = psensor_hub_data->magnetic_field[1] - psensor_hub_data->mmc.HI_Bias[1];
  data1[2] = psensor_hub_data->magnetic_field[2] - psensor_hub_data->mmc.HI_Bias[2];

  data2[0] = (int32_t) (psensor_hub_data->mmc.CalQuality);

  if (*reset == 1)
  {
    MotionMC_Initialize(10, 0);
    MotionMC_Initialize(10, 1);
  }
}
#endif

#if (MotionPM)
/**
 * @brief  Get number of steps and cadency from pedometer for mobile library
 */
void PedometerMobile_GetData(void *pdata, int32_t *reset, int32_t *data1, int32_t *data2)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data1[0] = (int32_t) (psensor_hub_data->mpm.Nsteps);
  data2[0] = (int32_t) (psensor_hub_data->mpm.Cadence);

  if (*reset == 1)
  {
    MotionPM_Initialize();
  }
}
#endif

#if (MotionPW)
/**
 * @brief  Get number of steps and cadency from pedometer for wrist library
 */
void PedometerWrist_GetData(void *pdata, int32_t *reset, int32_t *data1, int32_t *data2)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  data1[0] = (int32_t) (psensor_hub_data->mpw.Nsteps);
  data2[0] = (int32_t) (psensor_hub_data->mpw.Cadence);

  if (*reset == 1)
  {
    MotionPW_ResetStepCount();
    MotionPW_ResetPedometerLibrary();
  }
}
#endif

#if (MotionTL)
/**
 * @brief  Get tilt angles from tilt sensing library
 */
void TiltSensing_GetData(void *pdata, float *data)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  
  if (psensor_hub_data->mtl_mode == MODE_PITCH_ROLL_GRAVITY_INCLINATION)
  {
    data[0] = psensor_hub_data->mtl.pitch_3x;
    data[1] = psensor_hub_data->mtl.roll_3x;
    data[2] = psensor_hub_data->mtl.phi_3x;  
  }
  else if (psensor_hub_data->mtl_mode == MODE_THETA_PSI_PHI)
  {
    data[0] = psensor_hub_data->mtl.theta_3x;
    data[1] = psensor_hub_data->mtl.psi_3x;
    data[2] = psensor_hub_data->mtl.phi_3x; 
  }
  else
  {
    data[0] = psensor_hub_data->mtl.theta_3x;
    data[1] = psensor_hub_data->mtl.psi_3x;
    data[2] = psensor_hub_data->mtl.phi_3x; 
  }  
}
#endif

/**
 * @brief  Convert microtesla to miligauss
 */
void TeslaToGauss(float *in, float *out)
{
  out[0] = in[0] * FROM_UT_TO_MGAUSS;
  out[1] = in[1] * FROM_UT_TO_MGAUSS;
  out[2] = in[2] * FROM_UT_TO_MGAUSS;
}

/**
 * @brief  Return iteration counter value
 */
void GetIterationCounter(void *pdata, int32_t *out)
{
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  out[0] = (int32_t) psensor_hub_data->iteration_counter;
}

/**
 * @brief  FSM, MLC init
 */
void FSM_MLC_Init(int32_t fsm_number, int32_t mlc_number)
{ 
  acc_odr_before_ucf = Get_Accelero_ODR();
  acc_fs_before_ucf = Get_Accelero_FS();
  gyro_odr_before_ucf = Get_Gyro_ODR();
  gyro_fs_before_ucf = Get_Gyro_FS();
   
  #if (defined (USE_IKS02A1))
  /* Not supported */
  #elif (defined (USE_IKS01A3))
    #if (defined (USE_LSM6DSO16IS))
      /* Not supported */
    #else
      int i;
      int length = 0;
      
      if (fsm_number > 0)
      {
        length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
        }
        
        sensor_hub_data.fsm_enable = 1;
      }
    #endif
  #elif (defined (USE_IKS4A1))
    #if (defined (USE_LSM6DSO16IS))
      /* Not supported */
    #else
      int i;
      int length = 0;
      
      if ((fsm_number > 0) || (mlc_number > 0))
      {
        length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSV16X_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
        }
        
        if (fsm_number > 0)
        {
          sensor_hub_data.fsm_enable = 1;
        }
        
        if (mlc_number > 0)
        {
          sensor_hub_data.mlc_enable = 1;
        }
      }
    #endif
   #elif (defined (USE_IKS5A1))
    #if (defined (USE_ISM330IS))
      /* Not supported */
    #else
      int i;
      int length = 0;
      
      if ((fsm_number > 0) || (mlc_number > 0))
      {
        length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
        }
        
        if (fsm_number > 0)
        {
          sensor_hub_data.fsm_enable = 1;
        }
        
        if (mlc_number > 0)
        {
          sensor_hub_data.mlc_enable = 1;
        }
      }
    #endif
  #elif (defined (USE_SENSORTILEBOX))
    int i;
    int length = 0;
    
    if ((fsm_number > 0) || (mlc_number > 0))
    {
      length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
      for (i = 0; i < length; i++)
      {
        (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSOX_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
      }
      
      if (fsm_number > 0)
      {
        sensor_hub_data.fsm_enable = 1;
      }
      
      if (mlc_number > 0)
      {
        sensor_hub_data.mlc_enable = 1;
      }
    }
  #elif (defined (USE_SENSORTILEBOXPRO))
    #if (defined (USE_LSM6DSO16IS))
      /* Not suported */
    #elif (defined (USE_LSM6DSV320X))
      int i;
      int length = 0;
      
      if ((fsm_number > 0) || (mlc_number > 0))
      {
        length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV320X_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
        }
        
        if (fsm_number > 0)
        {
          sensor_hub_data.fsm_enable = 1;
        }
        
        if (mlc_number > 0)
        {
          sensor_hub_data.mlc_enable = 1;
        }
      }
    #else
      int i;
      int length = 0;
      
      if ((fsm_number > 0) || (mlc_number > 0))
      {
        length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSV16X_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
        }
        
        if (fsm_number > 0)
        {
          sensor_hub_data.fsm_enable = 1;
        }
        
        if (mlc_number > 0)
        {
          sensor_hub_data.mlc_enable = 1;
        }
      }
    #endif
  #elif (defined (USE_STWIN))
    int i;
    int length = 0;
    
    if ((fsm_number > 0) || (mlc_number > 0))
    {
      length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
      for (i = 0; i < length; i++)
      {
        (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
      }
      
      if (fsm_number > 0)
      {
        sensor_hub_data.fsm_enable = 1;
      }
      
      if (mlc_number > 0)
      {
        sensor_hub_data.mlc_enable = 1;
      }
    }
  #elif (defined (USE_STWINBOX))
    #if (defined (USE_ISM330IS))
      /* Not supported */
    #elif (defined (USE_ISM6HG256X))
      int i;
	   int length = 0;

	   if ((fsm_number > 0) || (mlc_number > 0))
	   {
	     length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
	     for (i = 0; i < length; i++)
	     {
		   (void)BSP_MOTION_SENSOR_Write_Register(ISM6HG256X_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
	     }

	     if (fsm_number > 0)
	     {
		   sensor_hub_data.fsm_enable = 1;
	     }

	     if (mlc_number > 0)
	     {
		   sensor_hub_data.mlc_enable = 1;
	     }
	   }
    #else
      int i;
      int length = 0;
      
      if ((fsm_number > 0) || (mlc_number > 0))
      {
        length = sizeof(fsm_mlc_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          (void)BSP_MOTION_SENSOR_Write_Register(ISM330DHCX_0, fsm_mlc_config[i].address, fsm_mlc_config[i].data);
        }
        
        if (fsm_number > 0)
        {
          sensor_hub_data.fsm_enable = 1;
        }
        
        if (mlc_number > 0)
        {
          sensor_hub_data.mlc_enable = 1;
        }
      }
    #endif
  #else
  #error Not supported platform
  #endif
}

/**
 * @brief  FSM, MLC Check if ucf file loading changes initial value of ODR or FS
 */
void FSM_MLC_Check_ODR_FS_Change()
{ 
  if (sensor_hub_data.fsm_enable || sensor_hub_data.mlc_enable)
  {
    uint32_t gyro_fs = Get_Gyro_FS();
    float gyro_odr = Get_Gyro_ODR();
    uint32_t acc_fs = Get_Accelero_FS();
    float acc_odr = Get_Accelero_ODR();
    uint32_t ODR_changed = 0;
    uint32_t FS_changed = 0;
    
    if (acc_odr_before_ucf  > acc_odr)
    {
      ODR_changed = 1;
    }
    if (acc_fs_before_ucf  != acc_fs)
    {
      FS_changed = 1;
    }

    if (sensor_hub_data.angular_rate_enable)
    {
      if (gyro_odr_before_ucf > gyro_odr)
      {
        ODR_changed = 1;
      }
      if (gyro_fs_before_ucf != gyro_fs)
      {
        FS_changed = 1;
      }
    }
    if (ODR_changed)
    {
      Report_Init_Error(AB_ERROR_ODR_CHANGED);
    }
    if (FS_changed)
    {
      Report_Init_Error(AB_ERROR_FS_CHANGED);
    }
  }
}

/**
 * @brief  FSM, MLC get data
 */
void FSM_MLC_GetData(void *pdata, int32_t *fsm_data, int32_t *mlc_data, int32_t fsm_number, int32_t mlc_number)
{
  int i;
  sensor_hub_data_t *psensor_hub_data = (sensor_hub_data_t *) pdata;
  
  for (i = 0; i < fsm_number; i++)
  {
    fsm_data[i] = (int32_t) psensor_hub_data->fsm_data[i];
  }
  
  for (i = 0; i < mlc_number; i++)
  {
    mlc_data[i] = (int32_t) psensor_hub_data->mlc_data[i];
  }
}

/**
 * @brief  Set accelerometer full scale
 */
static void Set_Accelero_FS(uint32_t accel_fs)
{
  int32_t fs = 0;
  
  switch (accel_fs)
  {
    case 0: fs =  2; break;
    case 1: fs =  4; break;
    case 2: fs =  8; break;
    case 3: fs = 16; break;
    default: fs = 4; break;
  }
  
#if (defined (USE_IKS02A1))  
  IKS02A1_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, fs);
#elif (defined (USE_IKS01A3))
  IKS01A3_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, fs);
#elif (defined (USE_IKS4A1))
  IKS4A1_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, fs);
#elif (defined (USE_IKS5A1))
  IKS5A1_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, fs);
#elif (defined (USE_SENSORTILEBOX))
  BSP_MOTION_SENSOR_SetFullScale(LSM6DSOX_0, MOTION_ACCELERO, fs);
#elif (defined (USE_SENSORTILEBOXPRO))
  BSP_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, fs); 
  #if (defined (USE_LSM6DSV320X))
  int32_t fs_hg = 320;
  BSP_MOTION_SENSOR_ACC_HG_SetFullScale(LSM6DSV320X_0, MOTION_ACCELERO, fs_hg); 
  #endif    
#elif (defined (USE_STWIN))
  BSP_MOTION_SENSOR_SetFullScale(ISM330DHCX_0, MOTION_ACCELERO, fs);
#elif (defined (USE_STWINBOX))
  BSP_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, fs);
#else
#error Not supported platform
#endif
}

/**
 * @brief  Get accelerometer full scale
 */
static uint32_t Get_Accelero_FS()
{
  int32_t fs = 0;
  
#if (defined (USE_IKS02A1))  
  IKS02A1_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &fs);
#elif (defined (USE_IKS01A3))
  IKS01A3_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &fs);
#elif (defined (USE_IKS4A1))
  IKS4A1_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &fs);
#elif (defined (USE_IKS5A1))
  IKS5A1_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &fs);
#elif (defined (USE_SENSORTILEBOX))
  BSP_MOTION_SENSOR_GetFullScale(LSM6DSOX_0, MOTION_ACCELERO, &fs);
#elif (defined (USE_SENSORTILEBOXPRO))
  BSP_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &fs);
#elif (defined (USE_STWIN))
  BSP_MOTION_SENSOR_GetFullScale(ISM330DHCX_0, MOTION_ACCELERO, &fs);
#elif (defined (USE_STWINBOX))
  BSP_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &fs);
#else
#error Not supported platform
#endif

  return fs;
}

/**
 * @brief  Set gyroscope full scale
 */
static void Set_Gyro_FS(uint32_t gyro_fs)
{
  int32_t fs = 0;
  
  switch (gyro_fs)
  {
    case 0: fs =  245.0; break;
    case 1: fs =  500.0; break;
    case 2: fs = 1000.0; break;
    case 3: fs = 2000.0; break;
    default: fs = 500.0; break;
  }
  
#if (defined (USE_IKS02A1))  
  IKS02A1_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, fs);
#elif (defined (USE_IKS01A3))
  IKS01A3_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, fs);
#elif (defined (USE_IKS4A1))
  IKS4A1_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, fs);
#elif (defined (USE_IKS5A1))
  IKS5A1_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, fs);
#elif (defined (USE_SENSORTILEBOX))
  BSP_MOTION_SENSOR_SetFullScale(LSM6DSOX_0, MOTION_GYRO, fs);
#elif (defined (USE_SENSORTILEBOXPRO))
  BSP_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, fs);
#elif (defined (USE_STWIN))
  BSP_MOTION_SENSOR_SetFullScale(ISM330DHCX_0, MOTION_GYRO, fs);
#elif (defined (USE_STWINBOX))
  BSP_MOTION_SENSOR_SetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, fs);
#else
#error Not supported platform
#endif
}

/**
 * @brief  Get gyroscope full scale
 */
static uint32_t Get_Gyro_FS()
{
  int32_t fs = 0;

#if (defined (USE_IKS02A1))  
  IKS02A1_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &fs);
#elif (defined (USE_IKS01A3))
  IKS01A3_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &fs);
#elif (defined (USE_IKS4A1))
  IKS4A1_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &fs);
#elif (defined (USE_IKS5A1))
  IKS5A1_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &fs);
#elif (defined (USE_SENSORTILEBOX))
  BSP_MOTION_SENSOR_GetFullScale(LSM6DSOX_0, MOTION_GYRO, &fs);
#elif (defined (USE_SENSORTILEBOXPRO))
  BSP_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &fs);
#elif (defined (USE_STWIN))
  BSP_MOTION_SENSOR_GetFullScale(ISM330DHCX_0, MOTION_GYRO, &fs);
#elif (defined (USE_STWINBOX))
  BSP_MOTION_SENSOR_GetFullScale(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &fs);
#else
#error Not supported platform
#endif
  
  return fs;
}

/**
 * @brief  Get Accelero output data rate
 */
static float Get_Accelero_ODR()
{
  float odr = 0;

#if (defined (USE_IKS02A1))  
  IKS02A1_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &odr);
#elif (defined (USE_IKS01A3))
  IKS01A3_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &odr);
#elif (defined (USE_IKS4A1))
  IKS4A1_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &odr);
#elif (defined (USE_IKS5A1))
  IKS5A1_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &odr);
#elif (defined (USE_SENSORTILEBOX))
  BSP_MOTION_SENSOR_GetOutputDataRate(LSM6DSOX_0, MOTION_ACCELERO, &odr);
#elif (defined (USE_SENSORTILEBOXPRO))
  BSP_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &odr);
#elif (defined (USE_STWIN))
  BSP_MOTION_SENSOR_GetOutputDataRate(ISM330DHCX_0, MOTION_ACCELERO, &odr);
#elif (defined (USE_STWINBOX))
  BSP_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_ACCELERO, &odr);
#else
#error Not supported platform
#endif
  
  return odr;
}

/**
 * @brief  Get Gyro output data rate
 */
static float Get_Gyro_ODR()
{
  float odr = 0;

#if (defined (USE_IKS02A1))  
  IKS02A1_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &odr);
#elif (defined (USE_IKS01A3))
  IKS01A3_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &odr);
#elif (defined (USE_IKS4A1))
  IKS4A1_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &odr);
#elif (defined (USE_IKS5A1))
  IKS5A1_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &odr);
#elif (defined (USE_SENSORTILEBOX))
  BSP_MOTION_SENSOR_GetOutputDataRate(LSM6DSOX_0, MOTION_GYRO, &odr);
#elif (defined (USE_SENSORTILEBOXPRO))
  BSP_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &odr);
#elif (defined (USE_STWIN))
  BSP_MOTION_SENSOR_GetOutputDataRate(ISM330DHCX_0, MOTION_GYRO, &odr);
#elif (defined (USE_STWINBOX))
  BSP_MOTION_SENSOR_GetOutputDataRate(SELECTED_6AXIS_SENSOR, MOTION_GYRO, &odr);
#else
#error Not supported platform
#endif
  
  return odr;
}

#if (MotionAC)
/**
  * @brief Load the calibration parameters from storage
  * @param dataSize  size of data
  * @param data  pointer to data
  * @retval Will return 0 the if it is sucess and 1 if it is failure
 */
char MotionAC_LoadCalFromNVM(unsigned short int datasize, unsigned int *data)
{
  return 1; /* Read from NVM not implemented. */
}

/**
  * @brief Save the calibration parameters in storage
  * @param dataSize  size of data
  * @param data  pointer to data
  * @retval Will return 0 the if it is sucess and 1 if it is failure
 */
char MotionAC_SaveCalInNVM(unsigned short int datasize, unsigned int *data)
{
  return 1; /* Write to NVM not implemented. */
}
#endif

#if (MotionFX)
/**
 * @brief  Load calibration parameter from memory
 * @param  dataSize length ot the data
 * @param  data pointer to the data
 * @retval (1) fail, (0) success
 */
char MotionFX_LoadMagCalFromNVM(unsigned short int dataSize, unsigned int *data)
{
  return 1;  /* Write to NVM not implemented. */
}

/**
 * @brief  Save calibration parameter to memory
 * @param  dataSize length ot the data
 * @param  data pointer to the data
 * @retval (1) fail, (0) success
 */
char MotionFX_SaveMagCalInNVM(unsigned short int dataSize, unsigned int *data)
{
  return 1;  /* Write to NVM not implemented. */
}
#endif

#if (MotionMC)
/**
  * @brief Load the calibration parameters from storage
  * @param dataSize  size of data
  * @param data  pointer to data
  * @retval Will return 0 the if it is sucess and 1 if it is failure
 */
char MotionMC_LoadCalFromNVM(unsigned short int datasize, unsigned int *data)
{
  return 1; /* Read from NVM not implemented. */
}

/**
  * @brief Save the calibration parameters in storage
  * @param dataSize  size of data
  * @param data  pointer to data
  * @retval Will return 0 the if it is sucess and 1 if it is failure
 */
char MotionMC_SaveCalInNVM(unsigned short int datasize, unsigned int *data)
{
  return 1; /* Write to NVM not implemented. */
}
#endif

#if (MotionEC)
/**
  * @brief  Creates the rotation matrix that allows to change from original reference system to ENU
 */
static void Create_Rotation_Matrix(const char *orientation, float *matrix)
{
  uint8_t i;
  char ao[3];

  for (i = 0; i < 9; i++)
  {
    matrix[i] = 0;
  }

  for (i = 0; i < 3; i++)
  {
    if ((orientation[i] > 'A') && (orientation[i] < 'Z'))
    {
      ao[i] = orientation[i] + ('a' - 'A');
    }
    else
    {
      ao[i] = orientation[i];
    }
}

  switch (ao[0])
  {
  case 'e':
    matrix[0] = 1.0f;
    break;
  case 'n':
    matrix[3] = 1.0f;
    break;
  case 'w':
    matrix[0] = -1.0f;
    break;
  case 's':
    matrix[3] = -1.0f;
    break;
  case 'u':
    matrix[6] = 1.0f;
    break;
  case 'd':
    matrix[6] = -1.0f;
    break;
  }

  switch (ao[1])
  {
  case 'e':
    matrix[1] = 1.0f;
    break;
  case 'n':
    matrix[4] = 1.0f;
    break;
  case 'w':
    matrix[1] = -1.0f;
    break;
  case 's':
    matrix[4] = -1.0f;
    break;
  case 'u':
    matrix[7] = 1.0f;
    break;
  case 'd':
    matrix[7] = -1.0f;
    break;
  }

  switch (ao[2])
  {
  case 'e':
    matrix[2] = 1.0f;
    break;
  case 'n':
    matrix[5] = 1.0f;
    break;
  case 'w':
    matrix[2] = -1.0f;
    break;
  case 's':
    matrix[5] = -1.0f;
    break;
  case 'u':
    matrix[8] = 1.0f;
    break;
  case 'd':
    matrix[8] = -1.0f;
    break;
  }
}

/**
  * @brief  Performs the axis transformation
 */
static void Axis_Transformation(float *o, float *i, float *matrix)
{
  o[0] = matrix[0] * i[0] + matrix[1] * i[1] + matrix[2] * i[2];
  o[1] = matrix[3] * i[0] + matrix[4] * i[1] + matrix[5] * i[2];
  o[2] = matrix[6] * i[0] + matrix[7] * i[1] + matrix[8] * i[2];
}
#endif

/**
 * @brief  ISPU init
 */
void ISPU_Init(uint8_t data_size)
{ 
  acc_odr_before_ucf = Get_Accelero_ODR();
  acc_fs_before_ucf = Get_Accelero_FS();
  gyro_odr_before_ucf = Get_Gyro_ODR();
  gyro_fs_before_ucf = Get_Gyro_FS();
   
  #if (defined (USE_IKS02A1))
    #if (defined (USE_ISM330IS))
      int i;
      int length = 0;
      sensor_hub_data.ispu_data_size = data_size;
      
      if (data_size > 0)
      {
        length = sizeof(ispu_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          if (ispu_config[i].address != 0xFF)  /* register 0xFF used for just one sensor as read only register */
          {                                     /* here it is used as indication for wait operation */
            (void)IKS02A1_MOTION_SENSOR_Write_Register(IKS02A1_ISM330IS_0, ispu_config[i].address, ispu_config[i].data);
          }
          else
          {
            HAL_Delay(ispu_config[i].data);
          }
        }
        
        sensor_hub_data.ispu_enable = 1;
        sensor_hub_data.acceleration_enable = 1;
      }
    #endif
  #elif (defined (USE_IKS01A3))
    #if (defined (USE_LSM6DSO16IS))
      int i;
      int length = 0;
      sensor_hub_data.ispu_data_size = data_size;
      
      if (data_size > 0)
      {
        length = sizeof(ispu_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          if (ispu_config[i].address != 0xFF)  /* register 0xFF used for just one sensor as read only register */
          {                                     /* here it is used as indication for wait operation */
            (void)IKS01A3_MOTION_SENSOR_Write_Register(IKS01A3_LSM6DSO16IS_0, ispu_config[i].address, ispu_config[i].data);
          }
          else
          {
            HAL_Delay(ispu_config[i].data);
          }
        }
        
        sensor_hub_data.ispu_enable = 1;
        sensor_hub_data.acceleration_enable = 1;
      }
    #endif
  #elif (defined (USE_IKS4A1))
    #if (defined (USE_LSM6DSO16IS))
      int i;
      int length = 0;
      sensor_hub_data.ispu_data_size = data_size;
      
      if (data_size > 0)
      {
        length = sizeof(ispu_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          if (ispu_config[i].address != 0xFF)  /* register 0xFF used for just one sensor as read only register */
          {                                     /* here it is used as indication for wait operation */
            (void)IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LSM6DSO16IS_0, ispu_config[i].address, ispu_config[i].data);
          }
          else
          {
            HAL_Delay(ispu_config[i].data);
          }
        }
        
        sensor_hub_data.ispu_enable = 1;
        sensor_hub_data.acceleration_enable = 1;
      }
    #endif
  #elif (defined (USE_IKS5A1))
    #if (defined (USE_ISM330IS))
      int i;
      int length = 0;
      sensor_hub_data.ispu_data_size = data_size;
      
      if (data_size > 0)
      {
        length = sizeof(ispu_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          if (ispu_config[i].address != 0xFF)  /* register 0xFF used for just one sensor as read only register */
          {                                     /* here it is used as indication for wait operation */
            (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM330IS_0, ispu_config[i].address, ispu_config[i].data);
          }
          else
          {
            HAL_Delay(ispu_config[i].data);
          }
        }
        
        sensor_hub_data.ispu_enable = 1;
        sensor_hub_data.acceleration_enable = 1;
      }
    #endif
  #elif (defined (USE_SENSORTILEBOX))
  /* Not supported */
  #elif (defined (USE_SENSORTILEBOXPRO))
    #if (defined (USE_LSM6DSO16IS))
      int i;
      int length = 0;
      sensor_hub_data.ispu_data_size = data_size;
      
      if (data_size > 0)
      {
        length = sizeof(ispu_config)/sizeof(ucf_line_t);
        for (i = 0; i < length; i++)
        {
          if (ispu_config[i].address != 0xFF)  /* register 0xFF used for just one sensor as read only register */
          {                                     /* here it is used as indication for wait operation */
            (void)BSP_MOTION_SENSOR_Write_Register(LSM6DSO16IS_0, ispu_config[i].address, ispu_config[i].data);
          }
          else
          {
            HAL_Delay(ispu_config[i].data);
          }
        }
        
        sensor_hub_data.ispu_enable = 1;
        sensor_hub_data.acceleration_enable = 1;
      }
    #endif
  #elif (defined (USE_STWIN))
  /* Not supported */
  #elif (defined (USE_STWINBOX))
  #if (defined (USE_ISM330IS))
  int i;
  int length = 0;
  sensor_hub_data.ispu_data_size = data_size;
  
  if (data_size > 0)
  {
    length = sizeof(ispu_config)/sizeof(ucf_line_t);
    for (i = 0; i < length; i++)
    {
      if (ispu_config[i].address != 0xFF)  /* register 0xFF used for just one sensor as read only register */
      {                                     /* here it is used as indication for wait operation */
        (void)BSP_MOTION_SENSOR_Write_Register(ISM330IS_0, ispu_config[i].address, ispu_config[i].data);
      }
      else
      {
        HAL_Delay(ispu_config[i].data);
      }
    }
    
    sensor_hub_data.ispu_enable = 1;
    sensor_hub_data.acceleration_enable = 1;
  }
  #else
  /* Not supported */
  #endif
  #else
  #error Not supported platform
  #endif
}

/**
 * @brief  FSM, MLC Check if ucf file loading changes initial value of ODR or FS
 */
void ISPU_Check_ODR_FS_Change()
{ 
  if (sensor_hub_data.ispu_enable)
  {
    uint32_t gyro_fs = Get_Gyro_FS();
    float gyro_odr = Get_Gyro_ODR();
    uint32_t acc_fs = Get_Accelero_FS();
    float acc_odr = Get_Accelero_ODR();
    uint32_t ODR_changed = 0;
    uint32_t FS_changed = 0;
    
    if (acc_odr_before_ucf  != acc_odr)
    {
      ODR_changed = 1;
    }
    if (acc_fs_before_ucf  != acc_fs)
    {
      FS_changed = 1;
    }

    if (sensor_hub_data.angular_rate_enable)
    {
      if (gyro_odr_before_ucf != gyro_odr)
      {
        ODR_changed = 1;
      }
      if (gyro_fs_before_ucf != gyro_fs)
      {
        FS_changed = 1;
      }
    }
    if (ODR_changed)
    {
      Report_Init_Error(AB_ERROR_ODR_CHANGED);
    }
    if (FS_changed)
    {
      Report_Init_Error(AB_ERROR_FS_CHANGED);
    }
  }
}

void memcpy_int8_t(int32_t *dest, void *src)
{
  int8_t tmp;
  memcpy(&tmp, src, sizeof(int8_t));
  *dest = (int32_t)tmp;	
}

void memcpy_uint8_t(int32_t *dest, void *src)
{
  uint8_t tmp;
  memcpy(&tmp, src, sizeof(uint8_t));
  *dest = (int32_t)tmp;	
}

void memcpy_int16_t(int32_t *dest, void *src)
{
  int16_t tmp;
  memcpy(&tmp, src, sizeof(int16_t));
  *dest = (int32_t)tmp;	
}

void memcpy_uint16_t(int32_t *dest, void *src)
{
  uint16_t tmp;
  memcpy(&tmp, src, sizeof(uint16_t));
  *dest = (int32_t)tmp;	
}

void memcpy_int32_t(int32_t *dest, void *src)
{
  memcpy(dest, src, sizeof(int32_t));
}

void memcpy_uint32_t(int32_t *dest, void *src)
{
  uint32_t tmp;
  memcpy(&tmp, src, sizeof(uint32_t));
  *dest = (int32_t)tmp;	
}

void memcpy_float(float *dest, void *src)
{
  memcpy(dest, src, sizeof(float));
}

void memset_int32_t(int32_t *dest, int c, int n)
{
  memset(dest, c, sizeof(int32_t) * n);
}

void memset_float(float *dest, int c, int n)
{
  memset(dest, c, sizeof(float) * n);
}

/**
 * @}
 */

/**
 * @}
 */
 
/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
