/* Auto-generated from decision_tree_raw_fe.json; do not edit by hand. */
#include "decision_tree_raw_fe.h"
#include <stddef.h>
#include <stdint.h>

typedef struct { int16_t feature_index; float threshold; int32_t left; int32_t right; uint8_t predicted_class; } imu_feature_tree_node_t;
static const imu_feature_tree_node_t imu_tree_nodes[9] = {
    {23, 2.88017779e+09f, 1, 6, 2u},
    {1, 4748.96753f, 2, 5, 2u},
    {11, 177808.164f, 3, 4, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {9, -688.0f, 7, 8, 0u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 0u},
};

/* The 36 features, in the same order as Python's extract_window_features():
   per axis: mean, variance (divide by n), max, min, peak-to-peak, energy (mean of squares). */
static void imu_compute_features(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS],
    float out[IMU_FEATURE_TREE_FEATURE_COUNT])
{
    uint32_t axis, i;
    for (axis = 0u; axis < IMU_FEATURE_TREE_RAW_CHANNELS; ++axis) {
        float sum = 0.0f, sum_sq = 0.0f, mean, variance = 0.0f;
        float minimum = samples[0][axis], maximum = samples[0][axis];
        uint32_t base = axis * 6u;
        for (i = 0u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {
            float v = samples[i][axis];
            sum += v;
            sum_sq += v * v;
            if (v < minimum) minimum = v;
            if (v > maximum) maximum = v;
        }
        mean = sum / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
        for (i = 0u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {
            float d = samples[i][axis] - mean;
            variance += d * d;
        }
        out[base + 0u] = mean;
        out[base + 1u] = variance / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
        out[base + 2u] = maximum;
        out[base + 3u] = minimum;
        out[base + 4u] = maximum - minimum;
        out[base + 5u] = sum_sq / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
    }
}

imu_feature_tree_class_t imu_feature_tree_predict_window(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS])
{
    float features[IMU_FEATURE_TREE_FEATURE_COUNT];
    int32_t node_index = 0;
    uint32_t steps;
    if (samples == NULL) return IMU_FEATURE_CLASS_UNKNOWN;
    imu_compute_features(samples, features);
    for (steps = 0u; steps < IMU_FEATURE_TREE_NODE_COUNT; ++steps) {
        const imu_feature_tree_node_t *node;
        if (node_index < 0 || (uint32_t)node_index >= IMU_FEATURE_TREE_NODE_COUNT) return IMU_FEATURE_CLASS_UNKNOWN;
        node = &imu_tree_nodes[node_index];
        if (node->feature_index < 0) return (imu_feature_tree_class_t)node->predicted_class;
        if ((uint32_t)node->feature_index >= IMU_FEATURE_TREE_FEATURE_COUNT) return IMU_FEATURE_CLASS_UNKNOWN;
        node_index = (features[node->feature_index] <= node->threshold) ? node->left : node->right;
    }
    return IMU_FEATURE_CLASS_UNKNOWN;
}
