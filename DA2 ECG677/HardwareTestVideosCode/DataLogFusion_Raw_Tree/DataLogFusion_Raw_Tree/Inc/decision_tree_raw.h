/* Auto-generated from decision_tree_raw.json; do not edit by hand.
 * Feature vector order (float values in training-data units):
 *   0: ACC_X
 *   1: ACC_Y
 *   2: ACC_Z
 *   3: GYR_X
 *   4: GYR_Y
 *   5: GYR_Z
 */
#ifndef DECISION_TREE_RAW_H
#define DECISION_TREE_RAW_H

#include <stdint.h>

#define IMU_TREE_FEATURE_COUNT ((uint32_t)6u)
#define IMU_TREE_NODE_COUNT ((uint32_t)95u)

typedef enum {
    IMU_CLASS_HORIZONTAL = 0,
    IMU_CLASS_STATIC = 1,
    IMU_CLASS_VERTICAL = 2,
    IMU_CLASS_UNKNOWN = 255
} imu_tree_class_t;

/* features[] must be in the order listed above and use the same units as training. */
imu_tree_class_t imu_tree_predict(const float features[IMU_TREE_FEATURE_COUNT]);

#endif /* DECISION_TREE_RAW_H */
