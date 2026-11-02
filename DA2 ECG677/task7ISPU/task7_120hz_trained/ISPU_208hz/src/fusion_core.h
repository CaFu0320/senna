#ifndef TASK7_FUSION_CORE_H
#define TASK7_FUSION_CORE_H
#include <stdint.h>
#include "madgwick.h"

typedef struct {
    Madgwick6 fusion;
    float bias_dps[3];
    float bias_sum_dps[3];
    float accel_norm_g;
    float raw_gyro_dps[3];
    uint32_t sample_count;
    uint32_t cal_count;
    uint32_t stable_count;
    uint32_t status;      /* 0=waiting to be still, 1=calibrating, 2=ready */
    uint32_t stationary;  /* conservative stationary diagnostic */
} FusionCore;
void fusion_core_init(FusionCore *s);
void fusion_core_sample(FusionCore *s,const float accel_g[3],const float gyro_dps[3]);
#endif
