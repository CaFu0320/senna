/* Auto-generated. Window=42; input order q0,q1,q2,q3. */
#ifndef DECISION_TREE_QUATERNION_FEATURES_RFE_H
#define DECISION_TREE_QUATERNION_FEATURES_RFE_H
#include <stdint.h>
#define QUAT_TREE_WINDOW_SIZE 42u
#define QUAT_TREE_CHANNELS 4u
#define QUAT_TREE_FEATURE_COUNT 12u
#define QUAT_TREE_NODE_COUNT 5u
typedef enum {
    QUAT_FEATURE_CLASS_HORIZONTAL = 0,
    QUAT_FEATURE_CLASS_STATIC = 1,
    QUAT_FEATURE_CLASS_VERTICAL = 2 ,
    QUAT_FEATURE_CLASS_UNKNOWN = 255
} quat_feature_tree_class_t;
/* samples[window_index][q0..q3]; quaternion units/convention must match training.
 * 0: q2__waveform_length
 * 1: q3__mean
 * 2: q3__std
 * 3: q3__min
 * 4: q3__max
 * 5: q3__range
 * 6: q3__rms
 * 7: q3__median
 * 8: q3__iqr
 * 9: q3__mean_abs
 * 10: q3__zero_crossing_rate
 * 11: q3__waveform_length
 */
quat_feature_tree_class_t quat_feature_tree_predict_window(const float samples[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS]);
#endif
