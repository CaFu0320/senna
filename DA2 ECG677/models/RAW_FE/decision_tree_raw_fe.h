/* Auto-generated from decision_tree_raw_fe.json; do not edit by hand.
 * Window length: 42 samples. Raw channel order: ACC_X, ACC_Y, ACC_Z, GYR_X, GYR_Y, GYR_Z.
 * Raw input units MUST match the training CSV (mg and mdps for MEMS Studio logs).
 * Feature order seen by the tree (6 statistics per axis: mean, var, max, min, p2p, energy):
 *   0: ACC_X__mean
 *   1: ACC_X__var
 *   2: ACC_X__max
 *   3: ACC_X__min
 *   4: ACC_X__p2p
 *   5: ACC_X__energy
 *   6: ACC_Y__mean
 *   7: ACC_Y__var
 *   8: ACC_Y__max
 *   9: ACC_Y__min
 *   10: ACC_Y__p2p
 *   11: ACC_Y__energy
 *   12: ACC_Z__mean
 *   13: ACC_Z__var
 *   14: ACC_Z__max
 *   15: ACC_Z__min
 *   16: ACC_Z__p2p
 *   17: ACC_Z__energy
 *   18: GYR_X__mean
 *   19: GYR_X__var
 *   20: GYR_X__max
 *   21: GYR_X__min
 *   22: GYR_X__p2p
 *   23: GYR_X__energy
 *   24: GYR_Y__mean
 *   25: GYR_Y__var
 *   26: GYR_Y__max
 *   27: GYR_Y__min
 *   28: GYR_Y__p2p
 *   29: GYR_Y__energy
 *   30: GYR_Z__mean
 *   31: GYR_Z__var
 *   32: GYR_Z__max
 *   33: GYR_Z__min
 *   34: GYR_Z__p2p
 *   35: GYR_Z__energy
 */
#ifndef DECISION_TREE_RAW_FE_H
#define DECISION_TREE_RAW_FE_H
#include <stdint.h>
#define IMU_FEATURE_TREE_WINDOW_SIZE ((uint32_t)42u)
#define IMU_FEATURE_TREE_RAW_CHANNELS ((uint32_t)6u)
#define IMU_FEATURE_TREE_FEATURE_COUNT ((uint32_t)36u)
#define IMU_FEATURE_TREE_NODE_COUNT ((uint32_t)5u)

typedef enum {
    IMU_FEATURE_CLASS_HORIZONTAL = 0,
    IMU_FEATURE_CLASS_STATIC = 1,
    IMU_FEATURE_CLASS_VERTICAL = 2,
    IMU_FEATURE_CLASS_UNKNOWN = 255
} imu_feature_tree_class_t;

/* Call with a complete window [sample][channel] in the documented order and units. */
imu_feature_tree_class_t imu_feature_tree_predict_window(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS]);
#endif /* DECISION_TREE_RAW_FE_H */
