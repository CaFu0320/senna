################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (14.3.rel1)
################################################################################

-include ../makefile.init

RM := rm -rf

# All of the sources participating in the build are defined here
-include sources.mk
-include MEMS/Target/subdir.mk
-include MEMS/App/subdir.mk
-include Drivers/STM32U5xx_HAL_Driver/Src/subdir.mk
-include Drivers/BSP/Components/ism330dhcx/subdir.mk
-include Drivers/BSP/Components/iis2mdc/subdir.mk
-include Drivers/BSP/B-U585I-IOT02A/subdir.mk
-include Core/Startup/subdir.mk
-include Core/Src/subdir.mk
-include objects.mk

ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(S_DEPS)),)
-include $(S_DEPS)
endif
ifneq ($(strip $(S_UPPER_DEPS)),)
-include $(S_UPPER_DEPS)
endif
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
endif

-include ../makefile.defs

OPTIONAL_TOOL_DEPS := \
$(wildcard ../makefile.defs) \
$(wildcard ../makefile.init) \
$(wildcard ../makefile.targets) \


BUILD_ARTIFACT_NAME := B_U585_DataLogFusion
BUILD_ARTIFACT_EXTENSION := elf
BUILD_ARTIFACT_PREFIX :=
BUILD_ARTIFACT := $(BUILD_ARTIFACT_PREFIX)$(BUILD_ARTIFACT_NAME)$(if $(BUILD_ARTIFACT_EXTENSION),.$(BUILD_ARTIFACT_EXTENSION),)

# Add inputs and outputs from these tool invocations to the build variables 
EXECUTABLES += \
B_U585_DataLogFusion.elf \

MAP_FILES += \
B_U585_DataLogFusion.map \

SIZE_OUTPUT += \
default.size.stdout \

OBJDUMP_LIST += \
B_U585_DataLogFusion.list \


# All Target
all: main-build

# Main-build Target
main-build: B_U585_DataLogFusion.elf secondary-outputs

# Tool invocations
B_U585_DataLogFusion.elf B_U585_DataLogFusion.map: $(OBJS) $(USER_OBJS) C:\Users\dante\Downloads\B_U585_DataLogFusion-20261111T042119Z-1-001\B_U585_DataLogFusion\STM32U585AIIXQ_FLASH.ld makefile objects.list $(OPTIONAL_TOOL_DEPS)
	arm-none-eabi-gcc -o "B_U585_DataLogFusion.elf" @"objects.list" $(USER_OBJS) $(LIBS) -mcpu=cortex-m33 -T"C:\Users\dante\Downloads\B_U585_DataLogFusion-20261111T042119Z-1-001\B_U585_DataLogFusion\STM32U585AIIXQ_FLASH.ld" --specs=nosys.specs -Wl,-Map="B_U585_DataLogFusion.map" -Wl,--gc-sections -static -L"C:\Users\jabri\STM32Cube\Repository\Packs\STMicroelectronics\X-CUBE-MEMS1\13.0.0\Middlewares\ST\STM32_MotionFX_Library\Lib" -L"C:\Users\dante\STM32Cube\Repository\Packs\STMicroelectronics\X-CUBE-MEMS1\13.0.0\Middlewares\ST\STM32_MotionFX_Library\Lib" -L"C:\Users\dante\STM32Cube\Repository\Packs\STMicroelectronics\X-CUBE-MEMS1\13.0.0\Middlewares\ST\STM32_MotionFX_Library\Lib" -L"C:\Users\dante\STM32Cube\Repository\Packs\STMicroelectronics\X-CUBE-MEMS1\13.0.0\Middlewares\ST\STM32_MotionFX_Library\Lib" -L"C:\Users\dante\STM32Cube\Repository\Packs\STMicroelectronics\X-CUBE-MEMS1\13.0.0\Middlewares\ST\STM32_MotionFX_Library\Inc" --specs=nano.specs -mfpu=fpv5-sp-d16 -mfloat-abi=hard -mthumb -u _printf_float -Wl,--start-group -lc -lm -Wl,--end-group
	@echo 'Finished building target: $@'
	@echo ' '

default.size.stdout: $(EXECUTABLES) makefile objects.list $(OPTIONAL_TOOL_DEPS)
	arm-none-eabi-size  $(EXECUTABLES)
	@echo 'Finished building: $@'
	@echo ' '

B_U585_DataLogFusion.list: $(EXECUTABLES) makefile objects.list $(OPTIONAL_TOOL_DEPS)
	arm-none-eabi-objdump -h -S $(EXECUTABLES) > "B_U585_DataLogFusion.list"
	@echo 'Finished building: $@'
	@echo ' '

# Other Targets
clean:
	-$(RM) B_U585_DataLogFusion.elf B_U585_DataLogFusion.list B_U585_DataLogFusion.map default.size.stdout
	-@echo ' '

secondary-outputs: $(SIZE_OUTPUT) $(OBJDUMP_LIST)

fail-specified-linker-script-missing:
	@echo 'Error: Cannot find the specified linker script. Check the linker settings in the build configuration.'
	@exit 2

warn-no-linker-script-specified:
	@echo 'Warning: No linker script specified. Check the linker settings in the build configuration.'

.PHONY: all clean dependents main-build fail-specified-linker-script-missing warn-no-linker-script-specified

-include ../makefile.targets
