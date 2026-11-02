#ifndef TASK7_QUAT_FE_TREE_H
#define TASK7_QUAT_FE_TREE_H
#include <stdint.h>
#define QUATFE_WINDOW 42u
#define QUATFE_STRIDE 21u
#define QUATFE_FEATURES 8u
#define QUATFE_NOT_READY 255u
/* Input order: q0=scalar(w), q1=x, q2=y, q3=z.
   Eight selected features (var, p2p) for each component in that order.
   Population variance (divide by 42), not sample variance.
   Model labels: 0 Horizontal; 1 Static; 2 Vertical. */
typedef struct {int16_t feature; int16_t left; int16_t right; float threshold; uint8_t predicted; float leaf_training_purity;} QuatFeNode;
typedef struct {uint32_t predicted_class;float leaf_training_purity;} QuatFePrediction;
QuatFePrediction quatfe_predict_features(const float x[QUATFE_FEATURES]);
void quatfe_window_features(const float buffer[QUATFE_WINDOW][4],float out[QUATFE_FEATURES]);
#endif
