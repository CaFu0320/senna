/* Auto-generated from decision_tree_quaternion_fe.json; do not edit. */
#include "decision_tree_quaternion_fe.h"
#include <stddef.h>
typedef struct { int16_t feature; float threshold; int32_t left; int32_t right; uint8_t cls; } quat_node_t;
static const quat_node_t nodes[5] = {
    {0, 0.319011904f, 1, 4, 1u},
    {1, 0.0280000009f, 2, 3, 1u},
    {-1, 0.0f, -1, -1, 0u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
};
/* 6 statistics per component, in the order of the Python code: mean, var, max, min, p2p, energy */
static void features(const float x[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS], float out[24]) {
    uint32_t a, i;
    for (a = 0u; a < QUAT_TREE_CHANNELS; ++a) {
        float sum = 0.0f, sq = 0.0f, mean, var = 0.0f, mn = x[0][a], mx = x[0][a];
        uint32_t b = a * 6u;
        for (i = 0u; i < QUAT_TREE_WINDOW_SIZE; ++i) {
            float v = x[i][a];
            sum += v; sq += v * v;
            if (v < mn) mn = v;
            if (v > mx) mx = v;
        }
        mean = sum / (float)QUAT_TREE_WINDOW_SIZE;
        for (i = 0u; i < QUAT_TREE_WINDOW_SIZE; ++i) { float d = x[i][a] - mean; var += d * d; }
        out[b + 0u] = mean;
        out[b + 1u] = var / (float)QUAT_TREE_WINDOW_SIZE;
        out[b + 2u] = mx;
        out[b + 3u] = mn;
        out[b + 4u] = mx - mn;
        out[b + 5u] = sq / (float)QUAT_TREE_WINDOW_SIZE;
    }
}
quat_feature_tree_class_t quat_feature_tree_predict_window(const float samples[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS]) {
    float f[24], sel[8];
    int32_t ni = 0;
    uint32_t step;
    if (samples == NULL) return QUAT_FEATURE_CLASS_UNKNOWN;
    features(samples, f);
    sel[0u] = f[0u]; /* q0__mean */
    sel[1u] = f[3u]; /* q0__min */
    sel[2u] = f[8u]; /* q1__max */
    sel[3u] = f[9u]; /* q1__min */
    sel[4u] = f[2u]; /* q0__max */
    sel[5u] = f[6u]; /* q1__mean */
    sel[6u] = f[5u]; /* q0__energy */
    sel[7u] = f[14u]; /* q2__max */
    for (step = 0u; step < QUAT_TREE_NODE_COUNT; ++step) {
        const quat_node_t *n;
        if (ni < 0 || (uint32_t)ni >= QUAT_TREE_NODE_COUNT) return QUAT_FEATURE_CLASS_UNKNOWN;
        n = &nodes[ni];
        if (n->feature < 0) return (quat_feature_tree_class_t)n->cls;
        if ((uint32_t)n->feature >= QUAT_TREE_FEATURE_COUNT) return QUAT_FEATURE_CLASS_UNKNOWN;
        ni = (sel[n->feature] <= n->threshold) ? n->left : n->right;
    }
    return QUAT_FEATURE_CLASS_UNKNOWN;
}
