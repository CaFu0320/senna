/* Auto-generated from decision_tree_features_rfe.json; do not edit by hand.
 * Window length: 42 samples.
 * Raw input channel order: ACC_X, ACC_Y, ACC_Z, GYR_X, GYR_Y, GYR_Z.
 * Raw input units MUST match training CSV (check units in CSV headers).
 * Selected engineered features, in tree input order:
 *   0: GYR_Y__waveform_length
 *   1: GYR_Z__mean
 *   2: GYR_Z__std
 *   3: GYR_Z__min
 *   4: GYR_Z__max
 *   5: GYR_Z__range
 *   6: GYR_Z__rms
 *   7: GYR_Z__median
 *   8: GYR_Z__iqr
 *   9: GYR_Z__mean_abs
 *   10: GYR_Z__zero_crossing_rate
 *   11: GYR_Z__waveform_length
 */
#ifndef DECISION_TREE_FEATURES_RFE_H
#define DECISION_TREE_FEATURES_RFE_H
#include <stdint.h>
#define IMU_FEATURE_TREE_WINDOW_SIZE ((uint32_t)42u)
#define IMU_FEATURE_TREE_RAW_CHANNELS ((uint32_t)6u)
#define IMU_FEATURE_TREE_FEATURE_COUNT ((uint32_t)12u)
#define IMU_FEATURE_TREE_NODE_COUNT ((uint32_t)5u)

typedef enum {
    IMU_FEATURE_CLASS_HORIZONTAL = 0,
    IMU_FEATURE_CLASS_STATIC = 1,
    IMU_FEATURE_CLASS_VERTICAL = 2,
    IMU_FEATURE_CLASS_UNKNOWN = 255
} imu_feature_tree_class_t;

/* Call with a complete window [sample][channel], using the documented order/units. */
imu_feature_tree_class_t imu_feature_tree_predict_window(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS]);
#endif /* DECISION_TREE_FEATURES_RFE_H */
