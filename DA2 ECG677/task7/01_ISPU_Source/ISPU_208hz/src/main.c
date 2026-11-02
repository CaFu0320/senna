/* Task 7: stable 208-Hz Madgwick ISPU, 120-Hz resampled QUAT+FE classification.
 * The STM32/AlgoBuilder Sensor Hub timer handles 120-Hz UART/log export;
 * native sensor/ISPU processing is 208 Hz, not 120 Hz.
 * Caution: 120 samples per sec here are selected from 208 filter updates.
 * This is not 120-Hz native sensor/ISPU processing.
 */
#include "peripherals.h"
#include "reg_map.h"
#include "fusion_core.h"
#include "quat_fe_tree.h"
#include <stdint.h>
#include <stdbool.h>

#define ACC_SENS_G_PER_LSB 0.000244f /* sensor full-scale 8 g */
#define GYR_SENS_DPS_PER_LSB 0.070f  /* sensor full-scale 2000 dps */
#define ISPU_HZ 208u
#define QUAT_OUTPUT_HZ 120u

void __attribute__((signal)) algo_00_init(void);
void __attribute__((signal)) algo_00(void);
static volatile uint32_t int_status;
static FusionCore state;

/* Ring uses quaternion [w,x,y,z] to match Python feature ordering. */
static float qwin[QUATFE_WINDOW][4];
static uint32_t q_write=0u, q_count=0u, resample_phase=0u;
static uint32_t prediction_count=0u, activity_id=QUATFE_NOT_READY;
static float leaf_training_purity=0.0f;
static float q3_p2p=0.0f, q2_var=0.0f;

void __attribute__((signal)) algo_00_init(void) {
    fusion_core_init(&state);
    q_write=q_count=resample_phase=prediction_count=0u;
    activity_id=QUATFE_NOT_READY;
    for (unsigned i=0u;i<16u;i++) cast_uint32_t(ISPU_DOUT_00 + 4u*i)=0u;
    cast_uint32_t(ISPU_DOUT_20)=QUATFE_NOT_READY;
}

static void classifier_on_120hz_quaternion(const float q[4]) {
    /* Deterministic 120/208 rate accumulator, no interpolation.
     * 120 quaternions selected per 208 native ISPU ticks (on average).
     */
    resample_phase+=QUAT_OUTPUT_HZ;
    if(resample_phase<ISPU_HZ) return;
    resample_phase-=ISPU_HZ;

    for(unsigned j=0;j<4;j++) qwin[q_write][j]=q[j];
    q_write=(q_write+1u)%QUATFE_WINDOW;
    ++q_count;
    if(q_count<QUATFE_WINDOW) return;
    if(((q_count-QUATFE_WINDOW)%QUATFE_STRIDE)!=0u) return;

    /* Variance and peak-to-peak do not depend on ring ordering. */
    float features[QUATFE_FEATURES];
    quatfe_window_features(qwin, features);
    QuatFePrediction p=quatfe_predict_features(features);
    activity_id=p.predicted_class;
    leaf_training_purity=p.leaf_training_purity;
    q2_var=features[4];
    q3_p2p=features[7];
    prediction_count++;
}

void __attribute__((signal)) algo_00(void) {
    float a[3], g[3];
    a[0]=(float)cast_sint16_t(ISPU_ARAW_X)*ACC_SENS_G_PER_LSB;
    a[1]=(float)cast_sint16_t(ISPU_ARAW_Y)*ACC_SENS_G_PER_LSB;
    a[2]=(float)cast_sint16_t(ISPU_ARAW_Z)*ACC_SENS_G_PER_LSB;
    g[0]=(float)cast_sint16_t(ISPU_GRAW_X)*GYR_SENS_DPS_PER_LSB;
    g[1]=(float)cast_sint16_t(ISPU_GRAW_Y)*GYR_SENS_DPS_PER_LSB;
    g[2]=(float)cast_sint16_t(ISPU_GRAW_Z)*GYR_SENS_DPS_PER_LSB;

    fusion_core_sample(&state,a,g);
    const float *q=state.fusion.q; /* [w,x,y,z] */
    if(state.status==2u) {
        classifier_on_120hz_quaternion(q);
    } else {
        /* Recalibration/startup invalidates old model outputs. */
        activity_id=QUATFE_NOT_READY;
    }

    cast_float(ISPU_DOUT_00)=q[1]; /* Quat_x */
    cast_float(ISPU_DOUT_02)=q[2]; /* Quat_y */
    cast_float(ISPU_DOUT_04)=q[3]; /* Quat_z */
    cast_float(ISPU_DOUT_06)=q[0]; /* Quat_w */
    cast_uint32_t(ISPU_DOUT_08)=state.sample_count;
    cast_uint32_t(ISPU_DOUT_10)=state.status;
    cast_uint32_t(ISPU_DOUT_12)=state.cal_count;
    cast_float(ISPU_DOUT_14)=state.bias_dps[0];
    cast_float(ISPU_DOUT_16)=state.bias_dps[1];
    cast_float(ISPU_DOUT_18)=state.bias_dps[2];
    cast_uint32_t(ISPU_DOUT_20)=activity_id;
    cast_uint32_t(ISPU_DOUT_22)=prediction_count;
    cast_float(ISPU_DOUT_24)=q3_p2p;
    cast_float(ISPU_DOUT_26)=q2_var;
    cast_float(ISPU_DOUT_28)=leaf_training_purity;
    cast_uint32_t(ISPU_DOUT_30)=state.stationary;
    int_status|=1u;
}

int main(void) {
    uint8_t status=cast_uint8_t(ISPU_STATUS);
    cast_uint8_t(ISPU_STATUS)=status|0x04u;
    cast_uint8_t(ISPU_GLB_CALL_EN)=0x01u;
    while(true) {
        stop_and_wait_start_pulse;
        int_status=0u;
        cast_uint32_t(ISPU_INT_STATUS)=0u;
        cast_uint8_t(ISPU_INT_PIN)=0u;
        cast_uint32_t(ISPU_CALL_EN)=cast_uint32_t(ISPU_ALGO)<<1;
        while(cast_uint32_t(ISPU_CALL_EN)!=0u) { }
        uint8_t int_pin=0u;
        int_pin|=((int_status & cast_uint32_t(ISPU_INT1_CTRL))>0u) ? 0x01u:0u;
        int_pin|=((int_status & cast_uint32_t(ISPU_INT2_CTRL))>0u) ? 0x02u:0u;
        cast_uint32_t(ISPU_INT_STATUS)=int_status;
        cast_uint8_t(ISPU_INT_PIN)=int_pin;
    }
}
