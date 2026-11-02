/* Auto-generated from decision_tree_quaternion.json; do not edit. */
#include "decision_tree_quaternion.h"
#include <stddef.h>
typedef struct { int8_t feature; float threshold; int32_t left,right; uint8_t cls; } node_t;
static const node_t nodes[7]={
 {3, -0.00150000001f, 1, 6, 2u},
 {2, 0.996499985f, 2, 3, 0u},
 {-1, 0.0f, -1, -1, 0u},
 {3, -0.0690000001f, 4, 5, 1u},
 {-1, 0.0f, -1, -1, 1u},
 {-1, 0.0f, -1, -1, 0u},
 {-1, 0.0f, -1, -1, 2u},
};
quat_raw_tree_class_t quat_raw_tree_predict(const float q[4]) { int32_t n=0; uint32_t steps; if(q==NULL)return QUAT_RAW_CLASS_UNKNOWN; for(steps=0;steps<7u;++steps){ const node_t *p; if(n<0||(uint32_t)n>=7u)return QUAT_RAW_CLASS_UNKNOWN; p=&nodes[n]; if(p->feature<0)return (quat_raw_tree_class_t)p->cls; if((uint32_t)p->feature>=4u)return QUAT_RAW_CLASS_UNKNOWN; n=(q[p->feature]<=p->threshold)?p->left:p->right; } return QUAT_RAW_CLASS_UNKNOWN; }
