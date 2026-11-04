#include "madgwick.h"
#include <math.h>

/* Independent C implementation of the 6-DOF Madgwick IMU gradient.
 * Reference: S. Madgwick, An efficient orientation filter for inertial and
 * inertial/magnetic sensor arrays, 2010. No magnetometer -> yaw unobservable.
 */
void madgwick6_init(Madgwick6 *s, float beta) {
    s->q[0] = 1.0f; s->q[1] = 0.0f; s->q[2] = 0.0f; s->q[3] = 0.0f;
    s->beta = beta;
}

void madgwick6_from_acc(Madgwick6 *s, const float a[3]) {
    float n2 = a[0]*a[0] + a[1]*a[1] + a[2]*a[2];
    if (!(n2 > 0.1f && n2 < 4.0f)) return;
    /* Set initial roll and pitch from gravity. Yaw is defined as zero. */
    float roll = atan2f(a[1], a[2]);
    float pitch = atan2f(-a[0], sqrtf(a[1]*a[1]+a[2]*a[2]));
    float cr = cosf(0.5f*roll), sr = sinf(0.5f*roll);
    float cp = cosf(0.5f*pitch), sp = sinf(0.5f*pitch);
    s->q[0] = cr*cp;
    s->q[1] = sr*cp;
    s->q[2] = cr*sp;
    s->q[3] = -sr*sp;
}

void madgwick6_update(Madgwick6 *s, const float g[3], const float a[3], float dt) {
    if (!(dt > 0.0f && dt < 0.1f)) return;
    float w=s->q[0], x=s->q[1], y=s->q[2], z=s->q[3];
    /* qdot = 0.5 q \otimes [0,gyro_rad_s]. */
    float d0 = 0.5f*(-x*g[0]-y*g[1]-z*g[2]);
    float d1 = 0.5f*( w*g[0]+y*g[2]-z*g[1]);
    float d2 = 0.5f*( w*g[1]-x*g[2]+z*g[0]);
    float d3 = 0.5f*( w*g[2]+x*g[1]-y*g[0]);
    float an2=a[0]*a[0]+a[1]*a[1]+a[2]*a[2];
    /* Reject clearly invalid/non-gravitational acceleration for correction.
     * Gyro integration still runs through the entire maneuver. */
    if (an2 > 0.72f && an2 < 1.32f) {  /* |a| about 0.85 ... 1.15 g */
        float inv=1.0f/sqrtf(an2);
        float ax=a[0]*inv, ay=a[1]*inv, az=a[2]*inv;
        float f0=2.0f*(x*z-w*y)-ax;
        float f1=2.0f*(w*x+y*z)-ay;
        float f2=1.0f-2.0f*(x*x+y*y)-az;
        /* Jacobian transpose times gravity residual. */
        float s0=-2.0f*y*f0+2.0f*x*f1;
        float s1=2.0f*z*f0+2.0f*w*f1-4.0f*x*f2;
        float s2=-2.0f*w*f0+2.0f*z*f1-4.0f*y*f2;
        float s3=2.0f*x*f0+2.0f*y*f1;
        float sn2=s0*s0+s1*s1+s2*s2+s3*s3;
        if (sn2 > 1.0e-12f) {
            float gain = s->beta/sqrtf(sn2);
            d0-=gain*s0; d1-=gain*s1; d2-=gain*s2; d3-=gain*s3;
        }
    }
    float q0=w+d0*dt, q1=x+d1*dt, q2=y+d2*dt, q3=z+d3*dt;
    float qn2=q0*q0+q1*q1+q2*q2+q3*q3;
    if (!(qn2 > 1.0e-12f && qn2 < 10.0f)) return;
    float inv=1.0f/sqrtf(qn2);
    q0*=inv; q1*=inv; q2*=inv; q3*=inv;
    /* Prevent a sign flip from appearing as a large feature jump. */
    if (q0*w+q1*x+q2*y+q3*z < 0.0f) {
        q0=-q0; q1=-q1; q2=-q2; q3=-q3;
    }
    s->q[0]=q0; s->q[1]=q1; s->q[2]=q2; s->q[3]=q3;
}
