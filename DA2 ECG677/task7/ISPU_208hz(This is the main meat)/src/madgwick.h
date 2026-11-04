#ifndef TASK7_MADGWICK_STABLE_H
#define TASK7_MADGWICK_STABLE_H
/* 6-axis (accelerometer+gyroscope) Madgwick filter.
 * q[0] = scalar w; q[1..3] = x,y,z.
 * gyro uses radians per second, accel uses g, dt uses seconds.
 */
typedef struct { float q[4]; float beta; } Madgwick6;
void madgwick6_init(Madgwick6 *s, float beta);
void madgwick6_from_acc(Madgwick6 *s, const float accel_g[3]);
void madgwick6_update(Madgwick6 *s, const float gyro_rad_s[3], const float accel_g[3], float dt);
#endif
