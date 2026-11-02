/* Auto-generated from decision_tree_quaternion_features_rfe.json; do not edit. */
#include "decision_tree_quaternion_features_rfe.h"
#include <math.h>
#include <stddef.h>
typedef struct { int16_t feature; float threshold; int32_t left; int32_t right; uint8_t cls; } quat_node_t;
static const quat_node_t nodes[5] = {
    {4, 0.712500006f, 1, 2, 0u},
    {-1, 0.0f, -1, -1, 0u},
    {8, 0.00100000005f, 3, 4, 1u},
    {-1, 0.0f, -1, -1, 1u},
    {-1, 0.0f, -1, -1, 2u},
};
static float percentile(float *s, uint32_t n, float q) { float pos=(float)(n-1u)*q; uint32_t lo=(uint32_t)pos, hi=lo+1u; if(hi>=n) return s[n-1u]; return s[lo]+(pos-(float)lo)*(s[hi]-s[lo]); }
static void features(const float x[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS], float out[44]) {
 uint32_t a,i,j; for(a=0;a<4u;++a) { float v[QUAT_TREE_WINDOW_SIZE],s[QUAT_TREE_WINDOW_SIZE]; float sum=0.0f,sq=0.0f,ab=0.0f,wave=0.0f,mn,mx,mean,var=0.0f; uint32_t cross=0u; int last=0;
 for(i=0;i<QUAT_TREE_WINDOW_SIZE;++i) { v[i]=x[i][a]; s[i]=v[i]; sum+=v[i]; sq+=v[i]*v[i]; ab+=fabsf(v[i]); if(i==0u) mn=mx=v[i]; else { if(v[i]<mn)mn=v[i]; if(v[i]>mx)mx=v[i]; wave+=fabsf(v[i]-v[i-1u]); } } mean=sum/(float)QUAT_TREE_WINDOW_SIZE; for(i=0;i<QUAT_TREE_WINDOW_SIZE;++i) { float d=v[i]-mean; var+=d*d; if(d>0.0f){if(last<0)++cross;last=1;} else if(d<0.0f){if(last>0)++cross;last=-1;} } var/=(float)QUAT_TREE_WINDOW_SIZE; for(i=1u;i<QUAT_TREE_WINDOW_SIZE;++i) { float key=s[i]; j=i; while(j>0u && s[j-1u]>key){s[j]=s[j-1u];--j;} s[j]=key; }
 { float med=percentile(s,QUAT_TREE_WINDOW_SIZE,0.5f),q1=percentile(s,QUAT_TREE_WINDOW_SIZE,0.25f),q3=percentile(s,QUAT_TREE_WINDOW_SIZE,0.75f); uint32_t b=a*11u; out[b+0u]=mean;out[b+1u]=sqrtf(var);out[b+2u]=mn;out[b+3u]=mx;out[b+4u]=mx-mn;out[b+5u]=sqrtf(sq/(float)QUAT_TREE_WINDOW_SIZE);out[b+6u]=med;out[b+7u]=q3-q1;out[b+8u]=ab/(float)QUAT_TREE_WINDOW_SIZE;out[b+9u]=(float)cross/(float)(QUAT_TREE_WINDOW_SIZE-1u);out[b+10u]=wave; } } }
quat_feature_tree_class_t quat_feature_tree_predict_window(const float samples[QUAT_TREE_WINDOW_SIZE][QUAT_TREE_CHANNELS]) { float f[44],sel[12]; int32_t ni=0; uint32_t step; if(samples==NULL)return QUAT_FEATURE_CLASS_UNKNOWN; features(samples,f);
 sel[0u]=f[32u]; /* q2__waveform_length */
 sel[1u]=f[33u]; /* q3__mean */
 sel[2u]=f[34u]; /* q3__std */
 sel[3u]=f[35u]; /* q3__min */
 sel[4u]=f[36u]; /* q3__max */
 sel[5u]=f[37u]; /* q3__range */
 sel[6u]=f[38u]; /* q3__rms */
 sel[7u]=f[39u]; /* q3__median */
 sel[8u]=f[40u]; /* q3__iqr */
 sel[9u]=f[41u]; /* q3__mean_abs */
 sel[10u]=f[42u]; /* q3__zero_crossing_rate */
 sel[11u]=f[43u]; /* q3__waveform_length */
 for(step=0u;step<QUAT_TREE_NODE_COUNT;++step) { const quat_node_t *n; if(ni<0 || (uint32_t)ni>=QUAT_TREE_NODE_COUNT)return QUAT_FEATURE_CLASS_UNKNOWN; n=&nodes[ni]; if(n->feature<0)return (quat_feature_tree_class_t)n->cls; if((uint32_t)n->feature>=QUAT_TREE_FEATURE_COUNT)return QUAT_FEATURE_CLASS_UNKNOWN; ni=(sel[n->feature]<=n->threshold)?n->left:n->right; } return QUAT_FEATURE_CLASS_UNKNOWN; }
