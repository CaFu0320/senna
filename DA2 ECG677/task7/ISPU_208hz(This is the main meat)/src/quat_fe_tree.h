#ifndef TASK7_QUAT_FE_TREE_H
#define TASK7_QUAT_FE_TREE_H
#include <stdint.h>
#define QUATFE_WINDOW 42u
#define QUATFE_STRIDE 21u
#define QUATFE_FEATURES 36u
#define QUATFE_NOT_READY 255u
/* Class mapping: 0=Curl, 1=Lateral raise, 2=Left punch; 255=not ready.
   Quaternion input order is [w,x,y,z]. All 36 features are computed on
   RELATIVE quaternions / squared quaternion steps, never absolute angle.
   Sample order is required; 'oldest' is ring index of earliest sample. */
typedef struct {int16_t feature, left, right; float threshold; uint8_t predicted; float leaf_training_purity;} QuatFeNode;
typedef struct {uint32_t predicted_class; float leaf_training_purity;} QuatFePrediction;
void quatfe_window_features(const float ring[QUATFE_WINDOW][4], uint32_t oldest, float out[QUATFE_FEATURES]);
QuatFePrediction quatfe_predict_features(const float x[QUATFE_FEATURES]);
#endif
