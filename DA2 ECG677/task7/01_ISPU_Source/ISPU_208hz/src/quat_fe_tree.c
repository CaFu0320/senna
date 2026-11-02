#include "quat_fe_tree.h"
/* GENERATED from decision_tree_task7_120hz_motion_fe.json */
static const QuatFeNode kNodes[17]={
  {7,1,10,2.999999560416e-03f,1,3.355048860e-01f}, /* node 0 */
  {5,2,5,1.500000013039e-03f,1,8.728813559e-01f}, /* node 1 */
  {3,3,4,1.500000071246e-03f,1,9.552238806e-01f}, /* node 2 */
  {-1,-1,-1,0.000000000000e+00f,1,9.333333333e-01f}, /* node 3 */
  {-1,-1,-1,0.000000000000e+00f,1,9.729729730e-01f}, /* node 4 */
  {3,6,9,1.500000071246e-03f,1,7.647058824e-01f}, /* node 5 */
  {5,7,8,2.499999944121e-03f,1,6.875000000e-01f}, /* node 6 */
  {-1,-1,-1,0.000000000000e+00f,1,7.307692308e-01f}, /* node 7 */
  {-1,-1,-1,0.000000000000e+00f,0,5.000000000e-01f}, /* node 8 */
  {-1,-1,-1,0.000000000000e+00f,1,8.947368421e-01f}, /* node 9 */
  {7,11,14,3.399998322129e-02f,2,5.238095238e-01f}, /* node 10 */
  {4,12,13,2.812811580952e-04f,2,9.797979798e-01f}, /* node 11 */
  {-1,-1,-1,0.000000000000e+00f,0,5.000000000e-01f}, /* node 12 */
  {-1,-1,-1,0.000000000000e+00f,2,1.000000000e+00f}, /* node 13 */
  {0,15,16,6.395994205377e-06f,0,9.777777778e-01f}, /* node 14 */
  {-1,-1,-1,0.000000000000e+00f,0,5.000000000e-01f}, /* node 15 */
  {-1,-1,-1,0.000000000000e+00f,0,1.000000000e+00f}, /* node 16 */
};
QuatFePrediction quatfe_predict_features(const float x[QUATFE_FEATURES]){
    uint16_t node=0;
    while(kNodes[node].feature>=0){
        const QuatFeNode *n=&kNodes[node];
        node=(uint16_t)(x[n->feature]<=n->threshold?n->left:n->right);
    }
    QuatFePrediction p={(uint32_t)kNodes[node].predicted,kNodes[node].leaf_training_purity};
    return p;
}
/* For simplicity the 42-sample caller passes a *chronological* or unordered
   window. Var and peak-to-peak are order-invariant; no sorting needed. */
void quatfe_window_features(const float b[QUATFE_WINDOW][4],float out[QUATFE_FEATURES]){
    for(unsigned j=0;j<4;j++){
        float min=b[0][j],max=b[0][j],sum=0.0f,var=0.0f;
        for(unsigned i=0;i<QUATFE_WINDOW;i++){
            float v=b[i][j]; if(v<min)min=v; if(v>max)max=v; sum+=v;
        }
        float mu=sum/(float)QUATFE_WINDOW;
        for(unsigned i=0;i<QUATFE_WINDOW;i++){
            float d=b[i][j]-mu;var+=d*d;
        }
        out[2*j]=var/(float)QUATFE_WINDOW;
        out[2*j+1]=max-min;
    }
}
