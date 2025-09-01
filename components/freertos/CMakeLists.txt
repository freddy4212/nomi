file(GLOB_RECURSE FREERTOS_SRCS ${WE2_SDK_PATH}/os/freertos_10_5_1/NTZ/*.c ${CMAKE_CURRENT_LIST_DIR}/*.c)
message(STATUS "FREERTOS_SRCS: ${FREERTOS_SRCS}")
add_compile_definitions(ENABLE_OS FREERTOS configENABLE_MPU=0)
component_register(
    COMPONENT_NAME freertos
    INCLUDE_DIRS ${CMAKE_CURRENT_LIST_DIR}
    ${WE2_SDK_PATH}/os/freertos_10_5_1/NTZ/freertos_kernel/include
    ${WE2_SDK_PATH}/os/freertos_10_5_1/NTZ/freertos_kernel/portable/GCC/ARM_CM55_NTZ/non_secure
    ${WE2_SDK_PATH}/os/freertos_10_5_1/NTZ/freertos_kernel/portable/MemMang
    SRCS ${FREERTOS_SRCS}
)