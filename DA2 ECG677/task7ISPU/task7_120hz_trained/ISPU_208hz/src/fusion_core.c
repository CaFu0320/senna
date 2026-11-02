#include "fusion_core.h"
#include <math.h>
#include <string.h>

#ifndef ISPU_SAMPLE_RATE_HZ
#define ISPU_SAMPLE_RATE_HZ 104
#endif
#define GYRO_TO_RAD 0.017453292519943295f
#define DT_SECONDS (1.0f/(float)ISPU_SAMPLE_RATE_HZ)
/* Consecutive still samples required; 2.0 seconds at either target rate. */
#define CAL_SAMPLES ((uint32_t)(2u*ISPU_SAMPLE_RATE_HZ))
#define BETA 0.07f

static float norm3(const float v[3]) {
    return sqrtf(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
}
void fusion_core_init(FusionCore *s) {
    memset(s,0,sizeof(*s));
    madgwick6_init(&s->fusion,BETA);
}
void fusion_core_sample(FusionCore *s,const float a[3],const float gyro[3]) {
    s->sample_count++;
    for (unsigned j=0;j<3;j++) s->raw_gyro_dps[j]=gyro[j];
    s->accel_norm_g=norm3(a);
    /* Calibrate only when the board truly looks still. Motion resets count. */
    float raw_speed=norm3(gyro);
    unsigned startup_still=(s->accel_norm_g>0.94f && s->accel_norm_g<1.06f && raw_speed<8.0f);
    if (s->status!=2u) {
        s->stationary=startup_still;
        if (!startup_still) {
            s->status=0u; s->cal_count=0u;
            for(unsigned j=0;j<3;j++) s->bias_sum_dps[j]=0.0f;
            return;
        }
        s->status=1u;
        for(unsigned j=0;j<3;j++) s->bias_sum_dps[j]+=gyro[j];
        if (++s->cal_count>=CAL_SAMPLES) {
            float inv=1.0f/(float)s->cal_count;
            for(unsigned j=0;j<3;j++) s->bias_dps[j]=s->bias_sum_dps[j]*inv;
            /* Attitude starts aligned to gravity; no artificial 2-second tilt transient. */
            madgwick6_from_acc(&s->fusion,a);
            s->status=2u;
            s->stable_count=0u;
        }
        return;
    }

    float residual[3];
    for(unsigned j=0;j<3;j++) residual[j]=gyro[j]-s->bias_dps[j];
    float corrected_speed=norm3(residual);
    s->stationary=(s->accel_norm_g>0.96f && s->accel_norm_g<1.04f && corrected_speed<1.5f);
    if(s->stationary) {
        if(s->stable_count<20000u)s->stable_count++;
    } else s->stable_count=0u;
    /* Very slow adaptive zero-rate estimator, only after 0.5s continuously still.
       This reduces long-term thermal bias drift, but cannot identify true yaw. */
    if(s->stable_count>(uint32_t)(ISPU_SAMPLE_RATE_HZ/2)) {
        for(unsigned j=0;j<3;j++) {
            s->bias_dps[j]+=0.002f*(gyro[j]-s->bias_dps[j]);
            residual[j]=gyro[j]-s->bias_dps[j];
        }
    }
    /* Suppress only near-zero residual quantization while positively stationary. */
    if (s->stationary) {
        for(unsigned j=0;j<3;j++) if(fabsf(residual[j])<0.08f) residual[j]=0.0f;
    }
    float gyro_rad[3];
    for(unsigned j=0;j<3;j++) gyro_rad[j]=residual[j]*GYRO_TO_RAD;
    madgwick6_update(&s->fusion,gyro_rad,a,DT_SECONDS);
}
