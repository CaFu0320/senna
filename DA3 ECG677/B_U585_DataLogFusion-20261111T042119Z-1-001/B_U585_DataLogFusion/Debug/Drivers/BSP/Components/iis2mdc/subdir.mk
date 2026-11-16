################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (14.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Drivers/BSP/Components/iis2mdc/iis2mdc.c \
../Drivers/BSP/Components/iis2mdc/iis2mdc_reg.c 

OBJS += \
./Drivers/BSP/Components/iis2mdc/iis2mdc.o \
./Drivers/BSP/Components/iis2mdc/iis2mdc_reg.o 

C_DEPS += \
./Drivers/BSP/Components/iis2mdc/iis2mdc.d \
./Drivers/BSP/Components/iis2mdc/iis2mdc_reg.d 


# Each subdirectory must supply rules for building sources it contributes
Drivers/BSP/Components/iis2mdc/%.o Drivers/BSP/Components/iis2mdc/%.su Drivers/BSP/Components/iis2mdc/%.cyclo: ../Drivers/BSP/Components/iis2mdc/%.c Drivers/BSP/Components/iis2mdc/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m33 -std=gnu11 -g3 -DDEBUG -DUSE_HAL_DRIVER -DSTM32U585xx -c -I../Core/Inc -I"C:/Users/dante/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Middlewares/ST/STM32_MotionFX_Library/Inc" -I"C:/Users/jabri/STM32Cube/Repository/Packs/STMicroelectronics/X-CUBE-MEMS1/13.0.0/Middlewares/ST/STM32_MotionFX_Library/Inc" -I../Drivers/STM32U5xx_HAL_Driver/Inc -I../Drivers/STM32U5xx_HAL_Driver/Inc/Legacy -I../Drivers/CMSIS/Device/ST/STM32U5xx/Include -I../Drivers/CMSIS/Include -I../MEMS/App -I../MEMS/Target -I../Drivers/BSP/B-U585I-IOT02A -I../Drivers/BSP/Components/ism330dhcx -I../Drivers/BSP/Components/iis2mdc -I../Drivers/BSP/Components/Common -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv5-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Drivers-2f-BSP-2f-Components-2f-iis2mdc

clean-Drivers-2f-BSP-2f-Components-2f-iis2mdc:
	-$(RM) ./Drivers/BSP/Components/iis2mdc/iis2mdc.cyclo ./Drivers/BSP/Components/iis2mdc/iis2mdc.d ./Drivers/BSP/Components/iis2mdc/iis2mdc.o ./Drivers/BSP/Components/iis2mdc/iis2mdc.su ./Drivers/BSP/Components/iis2mdc/iis2mdc_reg.cyclo ./Drivers/BSP/Components/iis2mdc/iis2mdc_reg.d ./Drivers/BSP/Components/iis2mdc/iis2mdc_reg.o ./Drivers/BSP/Components/iis2mdc/iis2mdc_reg.su

.PHONY: clean-Drivers-2f-BSP-2f-Components-2f-iis2mdc

