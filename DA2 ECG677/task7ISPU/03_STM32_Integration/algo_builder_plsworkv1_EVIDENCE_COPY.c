/* Reconstructed from the user's working MEMS Studio 2.4.1-generated algo_builder.c.
 * This file is an evidence copy, not a stand-alone build.
 * Keep original ST-generated project files for actual STM32CubeIDE compilation.
 */
#include "algo_builder.h"
const char Identification_String[] = "ID_STRING:plsworkv1.json,On-line";
void *Sensor_Hub_1_out;
float ISPU_1_Quat_x[1],ISPU_1_Quat_y[1],ISPU_1_Quat_z[1],ISPU_1_Quat_w_scalar[1];
int32_t ISPU_1_Sample_counter[1],ISPU_1_Calibration_status[1],ISPU_1_Calibration_count[1];
float ISPU_1_Gyro_bias_x_dps[1],ISPU_1_Gyro_bias_y_dps[1],ISPU_1_Gyro_bias_z_dps[1];
int32_t ISPU_1_Activity_class_id[1],ISPU_1_Prediction_counter[1];
float ISPU_1_q3_p2p[1],ISPU_1_q2_variance[1],ISPU_1_Leaf_training_purity_uncalibrated[1];
int32_t ISPU_1_Stationary_flag[1];
float Mux_Float_1_out[4];
extern sensor_hub_data_t sensor_hub_data;
void ISPU_GetData(void *handle, float *Quat_x, float *Quat_y, float *Quat_z, float *Quat_w_scalar,
    int32_t *Sample_counter, int32_t *Calibration_status, int32_t *Calibration_count,
    float *Gyro_bias_x_dps, float *Gyro_bias_y_dps, float *Gyro_bias_z_dps,
    int32_t *Activity_class_id, int32_t *Prediction_counter, float *q3_p2p,
    float *q2_variance, float *Leaf_training_purity_uncalibrated, int32_t *Stationary_flag)
{
    (void)handle;
    memcpy_float(Quat_x, &sensor_hub_data.ispu_data[0]);
    memcpy_float(Quat_y, &sensor_hub_data.ispu_data[4]);
    memcpy_float(Quat_z, &sensor_hub_data.ispu_data[8]);
    memcpy_float(Quat_w_scalar, &sensor_hub_data.ispu_data[12]);
    memcpy_uint32_t(Sample_counter, &sensor_hub_data.ispu_data[16]);
    memcpy_uint32_t(Calibration_status, &sensor_hub_data.ispu_data[20]);
    memcpy_uint32_t(Calibration_count, &sensor_hub_data.ispu_data[24]);
    memcpy_float(Gyro_bias_x_dps, &sensor_hub_data.ispu_data[28]);
    memcpy_float(Gyro_bias_y_dps, &sensor_hub_data.ispu_data[32]);
    memcpy_float(Gyro_bias_z_dps, &sensor_hub_data.ispu_data[36]);
    memcpy_uint32_t(Activity_class_id, &sensor_hub_data.ispu_data[40]);
    memcpy_uint32_t(Prediction_counter, &sensor_hub_data.ispu_data[44]);
    memcpy_float(q3_p2p, &sensor_hub_data.ispu_data[48]);
    memcpy_float(q2_variance, &sensor_hub_data.ispu_data[52]);
    memcpy_float(Leaf_training_purity_uncalibrated, &sensor_hub_data.ispu_data[56]);
    memcpy_uint32_t(Stationary_flag, &sensor_hub_data.ispu_data[60]);
}
void Mux_float_4(float *in1, float *in2, float *in3, float *in4, float *out)
{out[0]=*in1;out[1]=*in2;out[2]=*in3;out[3]=*in4;}
sDISPLAY_INFO display_info_list[]={
 {INFO_TYPE_GRAPH,1,4,VAR_TYPE_FLOAT,0,"graph|Graph||1|19|q1|q2|q3|q4|||1",0},
 {INFO_TYPE_INT32,2,1,VAR_TYPE_INT32,16,"int32|Activity Classifier|Activity Number|||||||||||||||",0},
 {0,0,0,0,0,0,0}};
void AB_Init(void){Sensor_Hub_Init(0,120,2,3);ISPU_Init(64);Message_Length=20;}
void AB_Handler(void){
 Sensor_Hub_Handler(&Sensor_Hub_1_out);
 ISPU_GetData(Sensor_Hub_1_out,ISPU_1_Quat_x,ISPU_1_Quat_y,ISPU_1_Quat_z,ISPU_1_Quat_w_scalar,
 ISPU_1_Sample_counter,ISPU_1_Calibration_status,ISPU_1_Calibration_count,
 ISPU_1_Gyro_bias_x_dps,ISPU_1_Gyro_bias_y_dps,ISPU_1_Gyro_bias_z_dps,
 ISPU_1_Activity_class_id,ISPU_1_Prediction_counter,ISPU_1_q3_p2p,ISPU_1_q2_variance,
 ISPU_1_Leaf_training_purity_uncalibrated,ISPU_1_Stationary_flag);
 Mux_float_4(ISPU_1_Quat_x,ISPU_1_Quat_y,ISPU_1_Quat_z,ISPU_1_Quat_w_scalar,Mux_Float_1_out);
 Display_Update(Mux_Float_1_out,&display_info_list[0]);
 Display_Update(ISPU_1_Activity_class_id,&display_info_list[1]);
}
