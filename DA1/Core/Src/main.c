/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
#include <math.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* ---- Build mode -----------------------------------------------------------
 * CAL_MODE 1 : stream min/max/sum trackers for manual calibration
 * CAL_MODE 0 : stream full CSV (raw, Euler, quaternion) for data collection
 */
#define CAL_MODE            0

/* ---- LSM6DSV16X (accel + gyro) -------------------------------------------- */
#define LSM6DSV16X_ADDR         (0x6BU << 1)   /* 0xD4 */
#define LSM6DSV16X_WHO_AM_I     0x0FU
#define LSM6DSV16X_EXPECTED_ID  0x70U
#define LSM6DSV16X_INT1_CTRL    0x0DU
#define LSM6DSV16X_CTRL1_XL     0x10U   /* accel op-mode + ODR          */
#define LSM6DSV16X_CTRL2_G      0x11U   /* gyro  op-mode + ODR          */
#define LSM6DSV16X_CTRL3        0x12U   /* BDU, IF_INC                  */
#define LSM6DSV16X_CTRL6        0x15U   /* gyro  full-scale + LPF1 BW   */
#define LSM6DSV16X_CTRL8        0x17U   /* accel full-scale + filter BW */
#define LSM6DSV16X_STATUS_REG   0x1EU
#define LSM6DSV16X_OUTX_L_G     0x22U   /* gyro X..Z then accel X..Z    */

/* CTRL1_XL / CTRL2_G: bits[6:4] = op mode (000 = high-performance)
 *                     bits[3:0] = ODR
 *   0x07 = 240 Hz   0x08 = 480 Hz   0x09 = 960 Hz   0x0A = 1920 Hz
 *   0x0B = 3840 Hz  0x0C = 7680 Hz (HP mode only)                       */
#define LSM6DSV16X_ODR_HP_240HZ   0x07U
#define LSM6DSV16X_ODR_HP_480HZ   0x08U
#define LSM6DSV16X_ODR_HP_960HZ   0x09U
#define LSM6DSV16X_ODR_HP_1920HZ  0x0AU

#define IMU_ODR_REG_VALUE       LSM6DSV16X_ODR_HP_240HZ  /* raise later */

/* CTRL8 FS_XL[1:0]: 00=±2g 01=±4g 10=±8g 11=±16g */
#define LSM6DSV16X_FS_XL_8G     0x02U
/* CTRL6 FS_G[3:0]: 0000=±125 0001=±250 0010=±500 0011=±1000 0100=±2000 dps */
#define LSM6DSV16X_FS_G_2000DPS 0x04U

/* Sensitivities matching the full-scales above */
#define ACC_SENS_MS2_PER_LSB    (0.244e-3f * 9.80665f)  /* ±8 g    */
#define GYRO_SENS_DPS_PER_LSB   0.070f                  /* ±2000 dps */
#define MAG_SENS_UT_PER_LSB     0.15f                   /* LIS2MDL fixed */

/* ---- LIS2MDL (magnetometer) ----------------------------------------------- */
#define LIS2MDL_ADDR        (0x1EU << 1)  /* 0x3C */
#define LIS2MDL_WHO_AM_I    0x4FU
#define LIS2MDL_EXPECTED_ID 0x40U
#define LIS2MDL_CFG_REG_A   0x60U
#define LIS2MDL_CFG_REG_B   0x61U
#define LIS2MDL_CFG_REG_C   0x62U
#define LIS2MDL_STATUS_REG  0x67U
#define LIS2MDL_OUTX_L      0x68U
#define LIS2MDL_NEW_XYZ     0x08U
#define MAG_I2C_TIMEOUT_MS  100U

/* If no DRDY interrupt arrives within this many ms, fall back to polling
 * so the loop never hangs while you debug the INT1 wiring. */
#define DRDY_TIMEOUT_MS     20U

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
I2C_HandleTypeDef hi2c1;

TIM_HandleTypeDef htim2;

UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
#define PI    3.14159265f
#define ALPHA 0.98f
#define G_MS2 9.80665f

/* Interrupt bookkeeping (shared with ISR -> volatile) */
volatile uint8_t  imu_data_ready    = 0;
volatile uint32_t imu_irq_count     = 0;
volatile uint32_t drdy_timeout_count = 0;

float roll = 0.0f;
float pitch = 0.0f;
float yaw = 0.0f;
uint32_t lastTick = 0;

/* Initial state: no rotation (identity quaternion) */
float q_w = 1.0f;
float q_x = 0.0f;
float q_y = 0.0f;
float q_z = 0.0f;

float gyro_x_sum = 0.0f, gyro_y_sum = 0.0f, gyro_z_sum = 0.0f;
uint32_t gyro_sample_count = 0;

/* Accelerometer max/min trackers */
float ax_max = -999.0f, ax_min = 999.0f;
float ay_max = -999.0f, ay_min = 999.0f;
float az_max = -999.0f, az_min = 999.0f;

/* Magnetometer max/min trackers */
float mx_max = -9999.0f, mx_min = 9999.0f;
float my_max = -9999.0f, my_min = 9999.0f;
float mz_max = -9999.0f, mz_min = 9999.0f;

// ---- Calibration constants -----------------------------------------------

// s = (max - min)/2
// b = (max + min)/2
float acc_x_bias = -0.019;
float acc_x_scale = 0.088; // 1/11.337

float acc_y_bias = -0.153;
float acc_y_scale = 0.0964; // 1/10.373

float acc_z_bias = 0.250;
float acc_z_scale = 0.0798; // 1/12.53

float mag_x_bias = -38.025;
float mag_x_scale = 0.912; // 1/1.096

float mag_y_bias = 8.55;
float mag_y_scale = 1.019; // 1/0.981

float mag_z_bias = -7.275;
float mag_z_scale = 1.0835; // 1/0.9229

float gyro_x_bias = 2.89;
float gyro_y_bias = -4.43;
float gyro_z_bias = -3.63;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_I2C1_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_TIM2_Init(void);
/* USER CODE BEGIN PFP */
static HAL_StatusTypeDef IMU_WriteReg(uint16_t dev, uint8_t reg, uint8_t val);
static HAL_StatusTypeDef IMU_ReadReg(uint16_t dev, uint8_t reg, uint8_t *val);
static void UART_Print(const char *s);
static float WrapDeg(float a);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
static HAL_StatusTypeDef IMU_WriteReg(uint16_t dev, uint8_t reg, uint8_t val)
{
  return HAL_I2C_Mem_Write(&hi2c1, dev, reg, I2C_MEMADD_SIZE_8BIT, &val, 1, HAL_MAX_DELAY);
}

static HAL_StatusTypeDef IMU_ReadReg(uint16_t dev, uint8_t reg, uint8_t *val)
{
  return HAL_I2C_Mem_Read(&hi2c1, dev, reg, I2C_MEMADD_SIZE_8BIT, val, 1, HAL_MAX_DELAY);
}

static void UART_Print(const char *s)
{
  HAL_UART_Transmit(&huart2, (uint8_t*)s, strlen(s), HAL_MAX_DELAY);
}

static float WrapDeg(float a)
{
  while (a >  180.0f) a -= 360.0f;
  while (a < -180.0f) a += 360.0f;
  return a;
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */
  uint8_t raw_data[12];
  uint8_t mag_raw_data[7];          /* STATUS + 6 data bytes in one read */
  int16_t gyro_x, gyro_y, gyro_z;
  int16_t accel_x, accel_y, accel_z;
  int16_t mag_x = 0, mag_y = 0, mag_z = 0;
  char uart_buff[256];

  float gyro_x_dps, gyro_y_dps, gyro_z_dps;
  float accel_x_ms2, accel_y_ms2, accel_z_ms2;
  float mag_x_uT = 0.0f, mag_y_uT = 0.0f, mag_z_uT = 0.0f;
  uint8_t who = 0;
  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_I2C1_Init();
  MX_USART2_UART_Init();
  MX_TIM2_Init();
  /* USER CODE BEGIN 2 */
  HAL_TIM_Base_Start(&htim2);

  /* ---- Sanity check: are both sensors on the bus? ---- */
  if (IMU_ReadReg(LSM6DSV16X_ADDR, LSM6DSV16X_WHO_AM_I, &who) != HAL_OK || who != LSM6DSV16X_EXPECTED_ID)
  {
    snprintf(uart_buff, sizeof(uart_buff), "ERR: LSM6DSV16X WHO_AM_I = 0x%02X (expected 0x70)\r\n", who);
    UART_Print(uart_buff);
    Error_Handler();
  }
  if (IMU_ReadReg(LIS2MDL_ADDR, LIS2MDL_WHO_AM_I, &who) != HAL_OK || who != LIS2MDL_EXPECTED_ID)
  {
    snprintf(uart_buff, sizeof(uart_buff), "ERR: LIS2MDL WHO_AM_I = 0x%02X (expected 0x40)\r\n", who);
    UART_Print(uart_buff);
    Error_Handler();
  }

  /* ---- LSM6DSV16X configuration ----
   * Order matters: set full-scale and BDU first, then turn on ODR, then
   * route DRDY to INT1. */
  IMU_WriteReg(LSM6DSV16X_ADDR, LSM6DSV16X_CTRL3,    0x44);   /* BDU=1, IF_INC=1 (auto-increment) */
  IMU_WriteReg(LSM6DSV16X_ADDR, LSM6DSV16X_CTRL8,    LSM6DSV16X_FS_XL_8G);
  IMU_WriteReg(LSM6DSV16X_ADDR, LSM6DSV16X_CTRL6,    LSM6DSV16X_FS_G_2000DPS);
  IMU_WriteReg(LSM6DSV16X_ADDR, LSM6DSV16X_CTRL1_XL, IMU_ODR_REG_VALUE);   /* HP mode, 240 Hz */
  IMU_WriteReg(LSM6DSV16X_ADDR, LSM6DSV16X_CTRL2_G,  IMU_ODR_REG_VALUE);   /* HP mode, 240 Hz */
  HAL_Delay(50);   /* let the gyro settle */

  /* INT1_CTRL: bit0 = INT1_DRDY_XL, bit1 = INT1_DRDY_G */
  IMU_WriteReg(LSM6DSV16X_ADDR, LSM6DSV16X_INT1_CTRL, 0x03);

  /* ---- LIS2MDL configuration ----
   * CFG_REG_A = 0x8C : COMP_TEMP_EN=1, ODR=100 Hz, continuous mode
   * CFG_REG_C = 0x10 : BDU=1 */
  IMU_WriteReg(LIS2MDL_ADDR, LIS2MDL_CFG_REG_A, 0x8C);
  IMU_WriteReg(LIS2MDL_ADDR, LIS2MDL_CFG_REG_C, 0x10);
  HAL_Delay(50);

  /* Clear any stale interrupt/data, then start timing */
  HAL_I2C_Mem_Read(&hi2c1, LSM6DSV16X_ADDR, LSM6DSV16X_OUTX_L_G, I2C_MEMADD_SIZE_8BIT, raw_data, 12, HAL_MAX_DELAY);
  imu_data_ready = 0;
  lastTick = __HAL_TIM_GET_COUNTER(&htim2);

#if CAL_MODE
  UART_Print("ax_min,ax_max,ay_min,ay_max,az_min,az_max,mx_min,mx_max,my_min,my_max,mz_min,mz_max,gx_sum,gy_sum,gz_sum,n\r\n");
#else
  UART_Print("t_us,ax,ay,az,gx,gy,gz,mx,my,mz,roll,pitch,yaw,qw,qx,qy,qz\r\n");
#endif
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* ---- Blue button (PC13): reset calibration trackers ---- */
    if (HAL_GPIO_ReadPin(B1_GPIO_Port, B1_Pin) == GPIO_PIN_RESET)
    {
      ax_max = -999.0f;  ax_min = 999.0f;
      ay_max = -999.0f;  ay_min = 999.0f;
      az_max = -999.0f;  az_min = 999.0f;
      mx_max = -9999.0f; mx_min = 9999.0f;
      my_max = -9999.0f; my_min = 9999.0f;
      mz_max = -9999.0f; mz_min = 9999.0f;
      gyro_x_sum = 0.0f; gyro_y_sum = 0.0f; gyro_z_sum = 0.0f;
      gyro_sample_count = 0;
      HAL_Delay(200);   // debounce
    }

    /* ---- Wait for DRDY interrupt (with polling fallback) ---- */
    uint32_t wait_start = HAL_GetTick();
    while (!imu_data_ready)
    {
      if ((HAL_GetTick() - wait_start) >= DRDY_TIMEOUT_MS)
      {
        /* No interrupt arrived. Either INT1 is not wired to PB5, or the
         * sensor is not sampling. Poll STATUS_REG so we keep running. */
        uint8_t status = 0;
        IMU_ReadReg(LSM6DSV16X_ADDR, LSM6DSV16X_STATUS_REG, &status);
        drdy_timeout_count++;
        if (status & 0x03) break;      /* XLDA or GDA set -> data available */
        wait_start = HAL_GetTick();
      }
    }
    imu_data_ready = 0;

    /* Timestamp as close to the sample as possible */
    uint32_t currentTick = __HAL_TIM_GET_COUNTER(&htim2);
    uint32_t elapsedTick = currentTick - lastTick;   /* uint32 wrap-safe */
    lastTick = currentTick;
    float dt = (float)elapsedTick / 1000000.0f;
    if (dt <= 0.0f || dt > 0.5f) dt = 1.0f / 240.0f;

    /* ---- Read 12 bytes: gyro X,Y,Z then accel X,Y,Z ---- */
    if (HAL_I2C_Mem_Read(&hi2c1, LSM6DSV16X_ADDR, LSM6DSV16X_OUTX_L_G,
                         I2C_MEMADD_SIZE_8BIT, raw_data, 12, HAL_MAX_DELAY) != HAL_OK)
    {
      continue;
    }

    /* ---- Read mag STATUS + 6 data bytes in one transaction.
     * Only update mag values when the sensor flags new XYZ data (mag runs
     * at 100 Hz, IMU at 240 Hz+), otherwise reuse the last sample. ---- */
    if (HAL_I2C_Mem_Read(&hi2c1, LIS2MDL_ADDR, LIS2MDL_STATUS_REG,
                         I2C_MEMADD_SIZE_8BIT, mag_raw_data, sizeof(mag_raw_data),
                         MAG_I2C_TIMEOUT_MS) == HAL_OK
        && (mag_raw_data[0] & LIS2MDL_NEW_XYZ))
    {
      mag_x = (int16_t)((uint16_t)mag_raw_data[1] | ((uint16_t)mag_raw_data[2] << 8));
      mag_y = (int16_t)((uint16_t)mag_raw_data[3] | ((uint16_t)mag_raw_data[4] << 8));
      mag_z = (int16_t)((uint16_t)mag_raw_data[5] | ((uint16_t)mag_raw_data[6] << 8));
      mag_x_uT = (float)mag_x * MAG_SENS_UT_PER_LSB;
      mag_y_uT = (float)mag_y * MAG_SENS_UT_PER_LSB;
      mag_z_uT = (float)mag_z * MAG_SENS_UT_PER_LSB;
    }

    /* Reconstruct little-endian 16-bit values */
    gyro_x  = (int16_t)((uint16_t)raw_data[0]  | ((uint16_t)raw_data[1]  << 8));
    gyro_y  = (int16_t)((uint16_t)raw_data[2]  | ((uint16_t)raw_data[3]  << 8));
    gyro_z  = (int16_t)((uint16_t)raw_data[4]  | ((uint16_t)raw_data[5]  << 8));
    accel_x = (int16_t)((uint16_t)raw_data[6]  | ((uint16_t)raw_data[7]  << 8));
    accel_y = (int16_t)((uint16_t)raw_data[8]  | ((uint16_t)raw_data[9]  << 8));
    accel_z = (int16_t)((uint16_t)raw_data[10] | ((uint16_t)raw_data[11] << 8));

    /* Scale to physical units */
    gyro_x_dps  = (float)gyro_x  * GYRO_SENS_DPS_PER_LSB;
    gyro_y_dps  = (float)gyro_y  * GYRO_SENS_DPS_PER_LSB;
    gyro_z_dps  = (float)gyro_z  * GYRO_SENS_DPS_PER_LSB;
    accel_x_ms2 = (float)accel_x * ACC_SENS_MS2_PER_LSB;
    accel_y_ms2 = (float)accel_y * ACC_SENS_MS2_PER_LSB;
    accel_z_ms2 = (float)accel_z * ACC_SENS_MS2_PER_LSB;

    /* ---- Apply calibration (bias subtract, then scale multiply) ---- */
    float accel_x_true = (accel_x_ms2 - acc_x_bias) * acc_x_scale * G_MS2;
    float accel_y_true = (accel_y_ms2 - acc_y_bias) * acc_y_scale * G_MS2;
    float accel_z_true = (accel_z_ms2 - acc_z_bias) * acc_z_scale * G_MS2;

    float mag_x_true = (mag_x_uT - mag_x_bias) * mag_x_scale;
    float mag_y_true = (mag_y_uT - mag_y_bias) * mag_y_scale;
    float mag_z_true = (mag_z_uT - mag_z_bias) * mag_z_scale;

    float gyro_x_true = gyro_x_dps - gyro_x_bias;
    float gyro_y_true = gyro_y_dps - gyro_y_bias;
    float gyro_z_true = gyro_z_dps - gyro_z_bias;

    /* ---- Accelerometer static angles ---- */
    float roll_acc  = atan2f(accel_y_true, accel_z_true) * (180.0f / PI);
    float pitch_acc = atan2f(-accel_x_true,
                             sqrtf(accel_y_true * accel_y_true + accel_z_true * accel_z_true)) * (180.0f / PI);

    /* ---- Complementary filter: roll & pitch ---- */
    roll  = ALPHA * (roll  + gyro_x_true * dt) + (1.0f - ALPHA) * roll_acc;
    pitch = ALPHA * (pitch + gyro_y_true * dt) + (1.0f - ALPHA) * pitch_acc;

    float phi   = roll  * (PI / 180.0f);
    float theta = pitch * (PI / 180.0f);

    /* ---- Tilt-compensated magnetic heading ----
     * Standard formulation (NED-style, x forward, y right, z down):
     *   Xh =  mx*cos(theta) + mz*sin(theta)
     *   Yh =  mx*sin(phi)*sin(theta) + my*cos(phi) - mz*sin(phi)*cos(theta)
     *   psi = atan2(-Yh, Xh)
     * If yaw moves the wrong direction or is offset by 90/180 deg, the LIS2MDL
     * axes on the shield are not aligned with the LSM6DSV16X axes -- swap or
     * negate mx/my/mz here to match. */
    float Xh = mag_x_true * cosf(theta) + mag_z_true * sinf(theta);
    float Yh = mag_x_true * sinf(phi) * sinf(theta) + mag_y_true * cosf(phi)
             - mag_z_true * sinf(phi) * cosf(theta);
    float psi = atan2f(-Yh, Xh) * (180.0f / PI);

    /* Complementary filter on yaw, blending through the ±180 wrap correctly */
    float yaw_gyro = yaw + gyro_z_true * dt;
    float yaw_err  = WrapDeg(psi - yaw_gyro);
    yaw = WrapDeg(yaw_gyro + (1.0f - ALPHA) * yaw_err);

    roll  = WrapDeg(roll);
    pitch = WrapDeg(pitch);

    /* ---- Quaternion ---- */
    /* 1. gyro rates in rad/s */
    float wx = gyro_x_true * (PI / 180.0f);
    float wy = gyro_y_true * (PI / 180.0f);
    float wz = gyro_z_true * (PI / 180.0f);

    /* 2. quaternion derivative  q_dot = 0.5 * q (x) [0, w] */
    float q_dot_w = 0.5f * (-q_x * wx - q_y * wy - q_z * wz);
    float q_dot_x = 0.5f * ( q_w * wx + q_y * wz - q_z * wy);
    float q_dot_y = 0.5f * ( q_w * wy - q_x * wz + q_z * wx);
    float q_dot_z = 0.5f * ( q_w * wz + q_x * wy - q_y * wx);

    /* 3. gyro-propagated quaternion */
    float qg_w = q_w + q_dot_w * dt;
    float qg_x = q_x + q_dot_x * dt;
    float qg_y = q_y + q_dot_y * dt;
    float qg_z = q_z + q_dot_z * dt;

    /* 4. reference quaternion from fused Euler angles (half angles) */
    float r_half = roll  * (PI / 360.0f);
    float p_half = pitch * (PI / 360.0f);
    float y_half = yaw   * (PI / 360.0f);
    float cr = cosf(r_half), sr = sinf(r_half);
    float cp = cosf(p_half), sp = sinf(p_half);
    float cy = cosf(y_half), sy = sinf(y_half);

    float qa_w = cy * cp * cr + sy * sp * sr;
    float qa_x = cy * cp * sr - sy * sp * cr;
    float qa_y = cy * sp * cr + sy * cp * sr;
    float qa_z = sy * cp * cr - cy * sp * sr;

    /* 5. blend (keep both on the same hemisphere so the average is sane) */
    if ((qg_w * qa_w + qg_x * qa_x + qg_y * qa_y + qg_z * qa_z) < 0.0f)
    {
      qa_w = -qa_w; qa_x = -qa_x; qa_y = -qa_y; qa_z = -qa_z;
    }
    q_w = ALPHA * qg_w + (1.0f - ALPHA) * qa_w;
    q_x = ALPHA * qg_x + (1.0f - ALPHA) * qa_x;
    q_y = ALPHA * qg_y + (1.0f - ALPHA) * qa_y;
    q_z = ALPHA * qg_z + (1.0f - ALPHA) * qa_z;

    /* 6. renormalize */
    float norm = sqrtf(q_w * q_w + q_x * q_x + q_y * q_y + q_z * q_z);
    if (norm > 0.0f)
    {
      q_w /= norm; q_x /= norm; q_y /= norm; q_z /= norm;
    }

    /* ---- Calibration trackers (always updated; only printed in CAL_MODE) ---- */
    gyro_x_sum += gyro_x_dps;
    gyro_y_sum += gyro_y_dps;
    gyro_z_sum += gyro_z_dps;
    gyro_sample_count++;

    if (accel_x_ms2 > ax_max) ax_max = accel_x_ms2;
    if (accel_x_ms2 < ax_min) ax_min = accel_x_ms2;
    if (accel_y_ms2 > ay_max) ay_max = accel_y_ms2;
    if (accel_y_ms2 < ay_min) ay_min = accel_y_ms2;
    if (accel_z_ms2 > az_max) az_max = accel_z_ms2;
    if (accel_z_ms2 < az_min) az_min = accel_z_ms2;

    if (mag_x_uT > mx_max) mx_max = mag_x_uT;
    if (mag_x_uT < mx_min) mx_min = mag_x_uT;
    if (mag_y_uT > my_max) my_max = mag_y_uT;
    if (mag_y_uT < my_min) my_min = mag_y_uT;
    if (mag_z_uT > mz_max) mz_max = mag_z_uT;
    if (mag_z_uT < mz_min) mz_min = mag_z_uT;

    /* ---- Output ---- */
#if CAL_MODE
    /* Print at ~10 Hz so the terminal stays readable */
    if ((gyro_sample_count % 24U) == 0U)
    {
      snprintf(uart_buff, sizeof(uart_buff),
               "%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%lu\r\n",
               ax_min, ax_max, ay_min, ay_max, az_min, az_max,
               mx_min, mx_max, my_min, my_max, mz_min, mz_max,
               gyro_x_sum, gyro_y_sum, gyro_z_sum,
               (unsigned long)gyro_sample_count);
      UART_Print(uart_buff);
    }
#else
    /* Full CSV row: calibrated raw data, Euler angles, quaternion */
    snprintf(uart_buff, sizeof(uart_buff),
             "%.3f,%.3f,%.3f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f,%.4f\r\n",
             accel_x_true, accel_y_true, accel_z_true,
             gyro_x_true, gyro_y_true, gyro_z_true,
             mag_x_true, mag_y_true, mag_z_true,
             roll, pitch, yaw,
             q_w, q_x, q_y, q_z);
    UART_Print(uart_buff);
#endif

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 16;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV4;
  RCC_OscInitStruct.PLL.PLLQ = 7;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.ClockSpeed = 400000;
  hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 83;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 4294967295;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 921600;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : LD2_Pin */
  GPIO_InitStruct.Pin = LD2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LD2_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : PB5 (LSM6DSV16X INT1 / Arduino D4) */
  GPIO_InitStruct.Pin = GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI9_5_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/**
  * @brief  EXTI callback. Requires EXTI9_5_IRQHandler() in stm32f4xx_it.c to
  *         call HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_5) -- CubeMX generates this
  *         when PB5 is set to GPIO_EXTI5 and its NVIC line is enabled.
  */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  if (GPIO_Pin == GPIO_PIN_5)
  {
    imu_irq_count++;
    imu_data_ready = 1;
    HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);   /* visual heartbeat: LED flickers at ODR/2 */
  }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
    /* Fast blink so a sensor/WHO_AM_I failure is visible without a debugger */
    HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);
    for (volatile uint32_t i = 0; i < 400000; i++) { }
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
