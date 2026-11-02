/* Auto-generated from decision_tree_quaternion_raw.json; do not edit. */
#include "decision_tree_quaternion_raw.h"
#include <stddef.h>
typedef struct { int8_t feature; float threshold; int32_t left,right; uint8_t cls; } node_t;
static const node_t nodes[13]={
 {2, 0.6875f, 1, 12, 0u},
 {3, 0.95449999f, 2, 3, 2u},
 {-1, 0.0f, -1, -1, 2u},
 {2, 0.294499993f, 4, 5, 1u},
 {-1, 0.0f, -1, -1, 2u},
 {3, 0.955499977f, 6, 11, 1u},
 {1, -0.00450000004f, 7, 10, 1u},
 {0, 0.00350000011f, 8, 9, 1u},
 {-1, 0.0f, -1, -1, 2u},
 {-1, 0.0f, -1, -1, 1u},
 {-1, 0.0f, -1, -1, 1u},
 {-1, 0.0f, -1, -1, 2u},
 {-1, 0.0f, -1, -1, 0u},
};
quat_raw_tree_class_t quat_raw_tree_predict(const float q[4]) { int32_t n=0; uint32_t steps; if(q==NULL)return QUAT_RAW_CLASS_UNKNOWN; for(steps=0;steps<13u;++steps){ const node_t *p; if(n<0||(uint32_t)n>=13u)return QUAT_RAW_CLASS_UNKNOWN; p=&nodes[n]; if(p->feature<0)return (quat_raw_tree_class_t)p->cls; if((uint32_t)p->feature>=4u)return QUAT_RAW_CLASS_UNKNOWN; n=(q[p->feature]<=p->threshold)?p->left:p->right; } return QUAT_RAW_CLASS_UNKNOWN; }
