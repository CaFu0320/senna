# Task 1 - Dataset summary

Total samples: **8883**, classes: **3**, recordings: **3**

## Per-class distribution

              samples  recordings  duration_s  percent
label                                                 
Curl             2836           1        38.9     31.9
LateralRaise     2849           1        39.1     32.1
LeftPunch        3198           1       291.1     36.0

## Sampling / timing check

                  active_rate_Hz  gaps_over_100ms         label  samples  duration_s  effective_rate_Hz  dt_min_ms  dt_median_ms  dt_max_ms  pct_steps_over_1p5x_median   quaternion_source
file                                                                                                                                                                                       
Curl.csv                   72.94                0          Curl     2836       38.87              72.94       10.0          10.0       20.0                        37.1  Madgwick (offline)
LateralRaise.csv           72.89                0  LateralRaise     2849       39.07              72.89       10.0          10.0       20.0                        37.2  Madgwick (offline)
LeftPunch.csv              71.50                1     LeftPunch     3198      291.12              10.98       10.0          10.0   246420.0                        39.9  Madgwick (offline)

## Feature ranges (all data)

       unit       min       max    mean       std
acc_x     g   -2.1900    0.5180 -0.3090    0.3374
acc_y     g   -1.8930    1.8330 -0.2244    0.6258
acc_z     g   -1.7540    2.2590 -0.0602    0.7799
gyro_x  dps -279.1600  264.5300  0.0567  101.5256
gyro_y  dps -256.3400  229.3900 -0.0119   70.8462
gyro_z  dps -182.8400  191.4500  1.3686   46.7827
q0        -   -0.1014    0.9631  0.5549    0.2693
q1        -   -0.9443    0.9851  0.0082    0.5859
q2        -   -0.0901    0.9748  0.3364    0.3429
q3        -   -0.4025    0.2736 -0.1529    0.1488

## Temporal dynamics

              acc_mag_peak_Hz  acc_mag_rms  gyro_mag_peak_Hz  gyro_mag_rms
label                                                                     
Curl                     0.78       0.4015              1.56       58.8311
LateralRaise             0.78       0.3923              1.17       29.7207
LeftPunch                1.17       0.2264              1.17       41.5016

## Stratified split

               train     val    test   total  train_%  val_%  test_%
label                                                               
Curl          1985.0   426.0   425.0  2836.0     70.0   15.0    15.0
LateralRaise  1994.0   427.0   428.0  2849.0     70.0   15.0    15.0
LeftPunch     2239.0   479.0   480.0  3198.0     70.0   15.0    15.0
ALL           6218.0  1332.0  1333.0  8883.0     70.0   15.0    15.0

## Per-class statistics

### acc_x

                mean     std    min    max
label                                     
Curl         -0.1292  0.1331 -0.675  0.354
LateralRaise -0.2265  0.1169 -0.543  0.460
LeftPunch    -0.5420  0.4466 -2.190  0.518

### acc_y

                mean     std    min    max
label                                     
Curl          0.2776  0.2332 -0.597  0.878
LateralRaise -0.8766  0.4093 -1.627  0.767
LeftPunch    -0.0886  0.5193 -1.893  1.833

### acc_z

                mean     std    min    max
label                                     
Curl          0.7917  0.7459 -1.754  2.259
LateralRaise -0.4451  0.2541 -1.702  0.474
LeftPunch    -0.4727  0.4394 -1.741  1.333

### gyro_x

                mean       std     min     max
label                                         
Curl         -0.3427  157.3266 -279.16  264.53
LateralRaise -0.1365   79.4115 -157.43  132.02
LeftPunch     0.5832   32.6994 -146.58  123.76

### gyro_y

                mean       std     min     max
label                                         
Curl         -1.8183   47.4052 -169.19  160.09
LateralRaise -1.6225   28.9793 -113.68  112.28
LeftPunch     3.0248  105.7786 -256.34  229.39

### gyro_z

                mean      std     min     max
label                                        
Curl         -1.7019  28.1438 -134.75  104.30
LateralRaise  1.2288  32.2856  -70.56  143.22
LeftPunch     4.2160  66.5811 -182.84  191.45

### q0

                mean     std     min     max
label                                       
Curl          0.7914  0.1719  0.1575  0.9631
LateralRaise  0.5249  0.1496  0.2335  0.8421
LeftPunch     0.3718  0.2671 -0.1014  0.9236

### q1

                mean     std     min     max
label                                       
Curl          0.4364  0.2922 -0.1303  0.9851
LateralRaise -0.8030  0.0864 -0.9443 -0.5219
LeftPunch     0.3512  0.0685  0.1175  0.4934

### q2

                mean     std     min     max
label                                       
Curl          0.0068  0.0374 -0.0901  0.1109
LateralRaise  0.1897  0.0555  0.0110  0.3063
LeftPunch     0.7595  0.1677  0.2167  0.9748

### q3

                mean     std     min     max
label                                       
Curl         -0.2529  0.0547 -0.3401 -0.0392
LateralRaise  0.0333  0.0980 -0.1955  0.2736
LeftPunch    -0.2301  0.0679 -0.4025 -0.0931

