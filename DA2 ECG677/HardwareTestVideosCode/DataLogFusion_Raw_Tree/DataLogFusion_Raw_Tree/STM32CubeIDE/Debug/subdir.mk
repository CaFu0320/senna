################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (14.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Projects/NUCLEO-F401RE/Applications/IKS4A1/DataLogFusion_Raw_Tree/Src/decision_tree_features_rfe.c \
C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Projects/NUCLEO-F401RE/Applications/IKS4A1/DataLogFusion_Raw_Tree/Src/decision_tree_quaternion_features_rfe.c \
C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Projects/NUCLEO-F401RE/Applications/IKS4A1/DataLogFusion_Raw_Tree/Src/decision_tree_quaternion_raw.c \
C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Projects/NUCLEO-F401RE/Applications/IKS4A1/DataLogFusion_Raw_Tree/Src/decision_tree_raw.c 

OBJS += \
./decision_tree_features_rfe.o \
./decision_tree_quaternion_features_rfe.o \
./decision_tree_quaternion_raw.o \
./decision_tree_raw.o 

C_DEPS += \
./decision_tree_features_rfe.d \
./decision_tree_quaternion_features_rfe.d \
./decision_tree_quaternion_raw.d \
./decision_tree_raw.d 


# Each subdirectory must supply rules for building sources it contributes
decision_tree_features_rfe.o: C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Projects/NUCLEO-F401RE/Applications/IKS4A1/DataLogFusion_Raw_Tree/Src/decision_tree_features_rfe.c subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -g3 -DDEBUG -DUSE_HAL_DRIVER -DSTM32F401xE -c -I../../Inc -I../../../../../../../Drivers/STM32F4xx_HAL_Driver/Inc -I../../../../../../../Drivers/STM32F4xx_HAL_Driver/Inc/Legacy -I../../../../../../../Drivers/CMSIS/Device/ST/STM32F4xx/Include -I../../../../../../../Drivers/CMSIS/Include -I../../../../../../../Drivers/BSP/Components/lsm6dsv16x -I../../../../../../../Drivers/BSP/Components/lis2duxs12 -I../../../../../../../Drivers/BSP/Components/lis2mdl -I../../../../../../../Drivers/BSP/Components/lsm6dso16is -I../../../../../../../Drivers/BSP/Components/sht40ad1b -I../../../../../../../Drivers/BSP/Components/lps22df -I../../../../../../../Drivers/BSP/Components/stts22h -I../../../../../../../Drivers/BSP/IKS4A1 -I../../../../../../../Drivers/BSP/Components/Common -I../../../../../../../Middlewares/ST/STM32_MotionFX_Library/Inc -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"
decision_tree_quaternion_features_rfe.o: C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Projects/NUCLEO-F401RE/Applications/IKS4A1/DataLogFusion_Raw_Tree/Src/decision_tree_quaternion_features_rfe.c subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -g3 -DDEBUG -DUSE_HAL_DRIVER -DSTM32F401xE -c -I../../Inc -I../../../../../../../Drivers/STM32F4xx_HAL_Driver/Inc -I../../../../../../../Drivers/STM32F4xx_HAL_Driver/Inc/Legacy -I../../../../../../../Drivers/CMSIS/Device/ST/STM32F4xx/Include -I../../../../../../../Drivers/CMSIS/Include -I../../../../../../../Drivers/BSP/Components/lsm6dsv16x -I../../../../../../../Drivers/BSP/Components/lis2duxs12 -I../../../../../../../Drivers/BSP/Components/lis2mdl -I../../../../../../../Drivers/BSP/Components/lsm6dso16is -I../../../../../../../Drivers/BSP/Components/sht40ad1b -I../../../../../../../Drivers/BSP/Components/lps22df -I../../../../../../../Drivers/BSP/Components/stts22h -I../../../../../../../Drivers/BSP/IKS4A1 -I../../../../../../../Drivers/BSP/Components/Common -I../../../../../../../Middlewares/ST/STM32_MotionFX_Library/Inc -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"
decision_tree_quaternion_raw.o: C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Projects/NUCLEO-F401RE/Applications/IKS4A1/DataLogFusion_Raw_Tree/Src/decision_tree_quaternion_raw.c subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -g3 -DDEBUG -DUSE_HAL_DRIVER -DSTM32F401xE -c -I../../Inc -I../../../../../../../Drivers/STM32F4xx_HAL_Driver/Inc -I../../../../../../../Drivers/STM32F4xx_HAL_Driver/Inc/Legacy -I../../../../../../../Drivers/CMSIS/Device/ST/STM32F4xx/Include -I../../../../../../../Drivers/CMSIS/Include -I../../../../../../../Drivers/BSP/Components/lsm6dsv16x -I../../../../../../../Drivers/BSP/Components/lis2duxs12 -I../../../../../../../Drivers/BSP/Components/lis2mdl -I../../../../../../../Drivers/BSP/Components/lsm6dso16is -I../../../../../../../Drivers/BSP/Components/sht40ad1b -I../../../../../../../Drivers/BSP/Components/lps22df -I../../../../../../../Drivers/BSP/Components/stts22h -I../../../../../../../Drivers/BSP/IKS4A1 -I../../../../../../../Drivers/BSP/Components/Common -I../../../../../../../Middlewares/ST/STM32_MotionFX_Library/Inc -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"
decision_tree_raw.o: C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Projects/NUCLEO-F401RE/Applications/IKS4A1/DataLogFusion_Raw_Tree/Src/decision_tree_raw.c subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m4 -std=gnu11 -g3 -DDEBUG -DUSE_HAL_DRIVER -DSTM32F401xE -c -I../../Inc -I../../../../../../../Drivers/STM32F4xx_HAL_Driver/Inc -I../../../../../../../Drivers/STM32F4xx_HAL_Driver/Inc/Legacy -I../../../../../../../Drivers/CMSIS/Device/ST/STM32F4xx/Include -I../../../../../../../Drivers/CMSIS/Include -I../../../../../../../Drivers/BSP/Components/lsm6dsv16x -I../../../../../../../Drivers/BSP/Components/lis2duxs12 -I../../../../../../../Drivers/BSP/Components/lis2mdl -I../../../../../../../Drivers/BSP/Components/lsm6dso16is -I../../../../../../../Drivers/BSP/Components/sht40ad1b -I../../../../../../../Drivers/BSP/Components/lps22df -I../../../../../../../Drivers/BSP/Components/stts22h -I../../../../../../../Drivers/BSP/IKS4A1 -I../../../../../../../Drivers/BSP/Components/Common -I../../../../../../../Middlewares/ST/STM32_MotionFX_Library/Inc -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean--2e-

clean--2e-:
	-$(RM) ./decision_tree_features_rfe.cyclo ./decision_tree_features_rfe.d ./decision_tree_features_rfe.o ./decision_tree_features_rfe.su ./decision_tree_quaternion_features_rfe.cyclo ./decision_tree_quaternion_features_rfe.d ./decision_tree_quaternion_features_rfe.o ./decision_tree_quaternion_features_rfe.su ./decision_tree_quaternion_raw.cyclo ./decision_tree_quaternion_raw.d ./decision_tree_quaternion_raw.o ./decision_tree_quaternion_raw.su ./decision_tree_raw.cyclo ./decision_tree_raw.d ./decision_tree_raw.o ./decision_tree_raw.su

.PHONY: clean--2e-

