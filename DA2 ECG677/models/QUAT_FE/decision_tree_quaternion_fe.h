/* Auto-generated. Window=42; input order q0,q1,q2,q3. */
#ifndef DECISION_TREE_QUATERNION_FE_H
#define DECISION_TREE_QUATERNION_FE_H
#include <stdint.h>
#define QUAT_TREE_WINDOW_SIZE 42u
#define QUAT_TREE_CHANNELS 4u
#define QUAT_TREE_FEATURE_COUNT 8u
#define QUAT_TREE_NODE_COUNT 5u
typedef enum {
    QUAT_FEATURE_CLASS_HORIZONTAL = 0,
    QUAT_FEATURE_CLASS_STATIC = 1,
    QUAT_FEATURE_CLASS_VERTICAL = 2,
    QUAT_FEATURE_CLASS_UNKNOWN = 255
} quat_feature_tree_class_t;
/* samples[window_index][q0..q3]; quaternion convention must match training.
 * Selected features, in tree order:
 * 0: q3__var
 * 1: q3__min
 * 2: q3__p2p
 * 3: q1__max
 * 4: q1__energy
 * 5: q3__mean
 * 6: q3__max
 * 7: q1__var
 */
quat_feature_tree_class_t quat_feature_tree_predict_window(const float samples[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS]);
#endif
