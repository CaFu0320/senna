/* Auto-generated from decision_tree_raw.json; do not edit by hand. */
#include "decision_tree_raw.h"
#include <stddef.h>
#include <stdint.h>

typedef struct {
    int16_t feature_index; /* -1 indicates a leaf */
    float threshold;
    int32_t left_child;
    int32_t right_child;
    uint8_t predicted_class;
} imu_tree_node_t;

static const imu_tree_node_t imu_tree_nodes[95] = {
    {1, 19.5f, 1, 56, 2u},
    {1, 8.5f, 2, 29, 1u},
    {0, -144.0f, 3, 6, 2u},
    {3, -33005.0f, 4, 5, 0u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {5, 41195.0f, 7, 28, 2u},
    {1, 4.5f, 8, 21, 2u},
    {1, -8.5f, 9, 14, 2u},
    {3, 35.0f, 10, 11, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {3, 105.0f, 12, 13, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {3, -560.0f, 15, 16, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {3, 910.0f, 17, 20, 2u},
    {2, 939.0f, 18, 19, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {3, -2905.0f, 22, 23, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {3, 3570.0f, 24, 27, 2u},
    {4, 1015.0f, 25, 26, 1u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {5, -140.0f, 30, 39, 1u},
    {5, -48615.0f, 31, 32, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {0, 598.0f, 33, 38, 2u},
    {5, -280.0f, 34, 35, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {2, 1166.0f, 36, 37, 1u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {5, 525.0f, 40, 47, 1u},
    {4, 1085.0f, 41, 46, 1u},
    {5, 35.0f, 42, 45, 1u},
    {3, -35.0f, 43, 44, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {5, 40530.0f, 48, 55, 2u},
    {0, -407.5f, 49, 50, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {5, 1260.0f, 51, 54, 2u},
    {1, 10.0f, 52, 53, 1u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {0, 187.5f, 57, 88, 0u},
    {5, -31990.0f, 58, 59, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {5, 40530.0f, 60, 87, 2u},
    {0, -487.5f, 61, 62, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {1, 27.5f, 63, 70, 2u},
    {4, -735.0f, 64, 65, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {4, 1575.0f, 66, 69, 2u},
    {0, -25.0f, 67, 68, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {1, 40.5f, 71, 80, 2u},
    {1, 39.5f, 72, 77, 2u},
    {3, 210.0f, 73, 74, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {3, 1540.0f, 75, 76, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {5, 210.0f, 78, 79, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {0, 19.5f, 81, 82, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {0, 20.5f, 83, 86, 2u},
    {4, 1085.0f, 84, 85, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {2, 1582.0f, 89, 92, 0u},
    {2, 330.0f, 90, 91, 0u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {4, 4235.0f, 93, 94, 2u},
    {-1, 0.0f, -1, -1, 0u},
    {-1, 0.0f, -1, -1, 2u},
};

imu_tree_class_t imu_tree_predict(const float features[IMU_TREE_FEATURE_COUNT])
{
    int32_t node_index = 0;
    uint32_t steps;

    if (features == NULL) {
        return IMU_CLASS_UNKNOWN;
    }

    /* A valid tree reaches a leaf in fewer steps than the number of nodes.
       The bound also prevents an infinite loop if the table is corrupted. */
    for (steps = 0u; steps < IMU_TREE_NODE_COUNT; ++steps) {
        const imu_tree_node_t *node;
        float value;

        if (node_index < 0 || (uint32_t)node_index >= IMU_TREE_NODE_COUNT) {
            return IMU_CLASS_UNKNOWN;
        }
        node = &imu_tree_nodes[node_index];
        if (node->feature_index < 0) {
            return (imu_tree_class_t)node->predicted_class;
        }
        if ((uint32_t)node->feature_index >= IMU_TREE_FEATURE_COUNT) {
            return IMU_CLASS_UNKNOWN;
        }
        value = features[node->feature_index];
        if (value <= node->threshold) {
            node_index = node->left_child;
        } else {
            node_index = node->right_child;
        }
    }
    return IMU_CLASS_UNKNOWN;
}
