#include "fusion_core.h"
#include <stdio.h>
#include <math.h>
#include <assert.h>

static void tick(FusionCore *s, float ax, float ay, float az,
                 float gx, float gy, float gz) {
    float a[3]={ax,ay,az}, g[3]={gx,gy,gz};
    fusion_core_sample(s,a,g);
}
int main(void) {
    FusionCore s; fusion_core_init(&s);
#ifndef ISPU_SAMPLE_RATE_HZ
#define ISPU_SAMPLE_RATE_HZ 104
#endif
    /* Deliberate startup motion must not contaminate calibration. */
    for(int i=0;i<ISPU_SAMPLE_RATE_HZ;i++) tick(&s,0,0,1,0,0,35);
    assert(s.status==0u && s.cal_count==0u);
    /* Stationary with 1.4 dps Z gyro bias: output should not drift once calibrated. */
    for(int i=0;i<3*ISPU_SAMPLE_RATE_HZ;i++) tick(&s,0,0,1,0.49f,-0.28f,1.4f);
    assert(s.status==2u);
    assert(fabsf(s.bias_dps[2]-1.4f)<0.01f);
    for(int i=0;i<30*ISPU_SAMPLE_RATE_HZ;i++) tick(&s,0,0,1,0.49f,-0.28f,1.4f);
    float n=0.0f;
    for(int i=0;i<4;i++) n+=s.fusion.q[i]*s.fusion.q[i];
    assert(fabsf(n-1.0f)<0.001f);
    assert(fabsf(s.fusion.q[3])<0.005f);
    printf("PASS: startup motion rejected, gyro bias %.3f dps, static yaw ~= 0, q norm %.7f\n",s.bias_dps[2],n);
    /* With gyro well above stillness threshold, rotate 90 deg about z. */
    for(int i=0;i<ISPU_SAMPLE_RATE_HZ;i++) tick(&s,0,0,1,0.49f,-0.28f,91.4f);
    assert(s.fusion.q[3]>0.68f && s.fusion.q[3]<0.74f);
    printf("PASS: 90 deg yaw rotation, q_z=%.4f, q_w=%.4f\n",s.fusion.q[3],s.fusion.q[0]);
    /* Tilt initialization: 30 deg roll and 10 deg pitch gravity vector. */
    FusionCore t; fusion_core_init(&t);
    float ax=-0.17364818f, ay=0.49240388f, az=0.85286853f;
    for(int i=0;i<3*ISPU_SAMPLE_RATE_HZ;i++) tick(&t,ax,ay,az,0.28f,0.14f,0.21f);
    assert(t.status==2u);
    float xr=2.0f*(t.fusion.q[1]*t.fusion.q[3]-t.fusion.q[0]*t.fusion.q[2]);
    float yr=2.0f*(t.fusion.q[0]*t.fusion.q[1]+t.fusion.q[2]*t.fusion.q[3]);
    float zr=1.0f-2.0f*(t.fusion.q[1]*t.fusion.q[1]+t.fusion.q[2]*t.fusion.q[2]);
    assert(fabsf(xr-ax)<0.01f && fabsf(yr-ay)<0.01f && fabsf(zr-az)<0.01f);
    printf("PASS: tilt initialization matches gravity\n");
    return 0;
}
