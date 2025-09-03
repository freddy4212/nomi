# CMSIS-NN Component for ARM Cortex-M55
# Based on cmsis_nn_7_0_0.mk

set(CMSIS_NN_BASE_PATH ${WE2_SDK_PATH}/library/cmsis_nn/cmsis_nn_7_0_0)

# Check if CMSIS-NN library exists
if(NOT EXISTS ${CMSIS_NN_BASE_PATH})
    message(WARNING "CMSIS-NN library not found at ${CMSIS_NN_BASE_PATH}")
    return()
endif()

# Collect CMSIS-NN source files
file(GLOB_RECURSE CMSIS_NN_SRCS
    ${CMSIS_NN_BASE_PATH}/Source/ActivationFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/BasicMathFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/ConcatenationFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/ConvolutionFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/FullyConnectedFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/NNSupportFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/PoolingFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/ReshapeFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/SoftmaxFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/SVDFunctions/*.c
    ${CMSIS_NN_BASE_PATH}/Source/LSTMFunctions/*.c
)

# Include directories
set(CMSIS_NN_INCLUDE_DIRS
    ${CMSIS_NN_BASE_PATH}
    ${CMSIS_NN_BASE_PATH}/Include
    ${CMSIS_NN_BASE_PATH}/Include/Internal
    ${WE2_SDK_PATH}/CMSIS/CMSIS/Core/Include
    ${WE2_SDK_PATH}/CMSIS/CMSIS/DSP/Include
    ${WE2_SDK_PATH}/CMSIS/CMSIS/NN/Include
)

# Compiler definitions specific to CMSIS-NN
set(CMSIS_NN_COMPILE_DEFINITIONS
    ARM_MATH_DSP
    ARM_MATH_LOOPUNROLL
    ARM_MATH_MVEI
    CMSIS_NN
    ARM_MATH_CM55
)

# Compiler options for CMSIS-NN
set(CMSIS_NN_COMPILE_OPTIONS
    -Os
    -ffast-math
    -ffunction-sections
    -fdata-sections
    -Wall
    -Wno-unused-parameter
    -Wno-unused-function
    -Wno-unused-variable
)

# Register the CMSIS-NN component
component_register(
    COMPONENT_NAME cmsis-nn
    SRCS ${CMSIS_NN_SRCS}
    INCLUDE_DIRS ${CMSIS_NN_INCLUDE_DIRS}
    COMPILE_DEFINITIONS ${CMSIS_NN_COMPILE_DEFINITIONS}
    PRIVATE_COMPILE_OPTIONS ${CMSIS_NN_COMPILE_OPTIONS}
)

# Specific optimizations for ARM Cortex-M55
if(TARGET cmsis-nn)
    # Enable ARM Cortex-M55 specific optimizations
    target_compile_options(cmsis-nn PRIVATE
        -mcpu=cortex-m55
        -mfpu=auto
        -mfloat-abi=hard
        -mthumb
    )
    
    # Additional definitions for Cortex-M55
    target_compile_definitions(cmsis-nn PRIVATE
        __CM55_REV=0x0001
        __FPU_PRESENT=1
        __DSP_PRESENT=1
        __MVE_PRESENT=1
        __MVE_FP=1
    )
endif()

