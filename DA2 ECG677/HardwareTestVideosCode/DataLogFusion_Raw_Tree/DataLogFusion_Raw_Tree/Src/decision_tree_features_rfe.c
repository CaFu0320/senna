/* Auto-generated from decision_tree_features_rfe.json; do not edit by hand. */
#include "decision_tree_features_rfe.h"
#include <math.h>
#include <stddef.h>
#include <stdint.h>

typedef struct { int16_t feature_index; float threshold; int32_t left; int32_t right; uint8_t predicted_class; } imu_feature_tree_node_t;
static const imu_feature_tree_node_t imu_tree_nodes[5] = {
    {4, 46165.0f, 1, 4, 2u},
    {8, 4716.25f, 2, 3, 2u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
    {-1, 0.0f, -1, -1, 0u},
};
static void imu_compute_all_features(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS],
    float out[66])
{
    uint32_t axis;
    for (axis = 0u; axis < IMU_FEATURE_TREE_RAW_CHANNELS; ++axis) {
        float values[IMU_FEATURE_TREE_WINDOW_SIZE];
        float sorted[IMU_FEATURE_TREE_WINDOW_SIZE];
        float sum = 0.0f, sum_sq = 0.0f, sum_abs = 0.0f, wave_len = 0.0f;
        float mean, variance = 0.0f, minimum, maximum, rms, median, q1, q3;
        uint32_t i, j, crossings = 0u;
        int last_sign = 0;
        for (i = 0u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {
            values[i] = samples[i][axis];
            sorted[i] = values[i];
            sum += values[i];
            sum_sq += values[i] * values[i];
            sum_abs += fabsf(values[i]);
            if (i == 0u) { minimum = values[i]; maximum = values[i]; }
            else {
                if (values[i] < minimum) minimum = values[i];
                if (values[i] > maximum) maximum = values[i];
                wave_len += fabsf(values[i] - values[i - 1u]);
            }
        }
        mean = sum / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
        for (i = 0u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {
            float delta = values[i] - mean;
            variance += delta * delta;
            if (delta > 0.0f) { if (last_sign < 0) ++crossings; last_sign = 1; }
            else if (delta < 0.0f) { if (last_sign > 0) ++crossings; last_sign = -1; }
        }
        variance /= (float)IMU_FEATURE_TREE_WINDOW_SIZE;
        rms = sqrtf(sum_sq / (float)IMU_FEATURE_TREE_WINDOW_SIZE);
        /* Insertion sort permits deterministic median and quartile computation. */
        for (i = 1u; i < IMU_FEATURE_TREE_WINDOW_SIZE; ++i) {
            float key = sorted[i];
            j = i;
            while (j > 0u && sorted[j - 1u] > key) {
                sorted[j] = sorted[j - 1u];
                --j;
            }
            sorted[j] = key;
        }
        {
            float pos = ((float)IMU_FEATURE_TREE_WINDOW_SIZE - 1.0f) * 0.5f;
            uint32_t lo = (uint32_t)pos;
            uint32_t hi = lo + 1u;
            median = (lo == hi) ? sorted[lo] : sorted[lo] + (pos - (float)lo) * (sorted[hi] - sorted[lo]);
        }
        {
            float pos1 = ((float)IMU_FEATURE_TREE_WINDOW_SIZE - 1.0f) * 0.25f;
            uint32_t lo1 = (uint32_t)pos1, hi1 = lo1 + 1u;
            q1 = sorted[lo1] + (pos1 - (float)lo1) * (sorted[hi1] - sorted[lo1]);
            float pos3 = ((float)IMU_FEATURE_TREE_WINDOW_SIZE - 1.0f) * 0.75f;
            uint32_t lo3 = (uint32_t)pos3, hi3 = lo3 + 1u;
            q3 = sorted[lo3] + (pos3 - (float)lo3) * (sorted[hi3] - sorted[lo3]);
        }
        {
            uint32_t base = axis * 11u;
            out[base + 0u] = mean;
            out[base + 1u] = sqrtf(variance);
            out[base + 2u] = minimum;
            out[base + 3u] = maximum;
            out[base + 4u] = maximum - minimum;
            out[base + 5u] = rms;
            out[base + 6u] = median;
            out[base + 7u] = q3 - q1;
            out[base + 8u] = sum_abs / (float)IMU_FEATURE_TREE_WINDOW_SIZE;
            out[base + 9u] = (float)crossings / (float)(IMU_FEATURE_TREE_WINDOW_SIZE - 1u);
            out[base + 10u] = wave_len;
        }
    }
}


imu_feature_tree_class_t imu_feature_tree_predict_window(
    const float samples[IMU_FEATURE_TREE_WINDOW_SIZE][IMU_FEATURE_TREE_RAW_CHANNELS])
{
    float all_features[66];
    float selected_features[12];
    int32_t node_index = 0;
    uint32_t steps;
    if (samples == NULL) return IMU_FEATURE_CLASS_UNKNOWN;
    imu_compute_all_features(samples, all_features);
    selected_features[0u] = all_features[54u]; /* GYR_Y__waveform_length */
    selected_features[1u] = all_features[55u]; /* GYR_Z__mean */
    selected_features[2u] = all_features[56u]; /* GYR_Z__std */
    selected_features[3u] = all_features[57u]; /* GYR_Z__min */
    selected_features[4u] = all_features[58u]; /* GYR_Z__max */
    selected_features[5u] = all_features[59u]; /* GYR_Z__range */
    selected_features[6u] = all_features[60u]; /* GYR_Z__rms */
    selected_features[7u] = all_features[61u]; /* GYR_Z__median */
    selected_features[8u] = all_features[62u]; /* GYR_Z__iqr */
    selected_features[9u] = all_features[63u]; /* GYR_Z__mean_abs */
    selected_features[10u] = all_features[64u]; /* GYR_Z__zero_crossing_rate */
    selected_features[11u] = all_features[65u]; /* GYR_Z__waveform_length */
    for (steps = 0u; steps < IMU_FEATURE_TREE_NODE_COUNT; ++steps) {
        const imu_feature_tree_node_t *node;
        if (node_index < 0 || (uint32_t)node_index >= IMU_FEATURE_TREE_NODE_COUNT) return IMU_FEATURE_CLASS_UNKNOWN;
        node = &imu_tree_nodes[node_index];
        if (node->feature_index < 0) return (imu_feature_tree_class_t)node->predicted_class;
        if ((uint32_t)node->feature_index >= IMU_FEATURE_TREE_FEATURE_COUNT) return IMU_FEATURE_CLASS_UNKNOWN;
        if (selected_features[node->feature_index] <= node->threshold) node_index = node->left;
        else node_index = node->right;
    }
    return IMU_FEATURE_CLASS_UNKNOWN;
}
