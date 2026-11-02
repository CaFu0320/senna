/* Auto-generated raw quaternion tree; input order q0,q1,q2,q3. */
#ifndef DECISION_TREE_QUATERNION_H
#define DECISION_TREE_QUATERNION_H
#include <stdint.h>
typedef enum {
 QUAT_RAW_CLASS_HORIZONTAL = 0,
 QUAT_RAW_CLASS_STATIC = 1,
 QUAT_RAW_CLASS_VERTICAL = 2,
 QUAT_RAW_CLASS_UNKNOWN = 255
} quat_raw_tree_class_t;
quat_raw_tree_class_t quat_raw_tree_predict(const float q[4]);
#endif
