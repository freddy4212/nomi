cmake_minimum_required(VERSION 3.5.0)

project(allon_sensor_tflm C CXX)

get_filename_component(PROJECT_DIR ${CMAKE_CURRENT_LIST_DIR} ABSOLUTE)
get_filename_component(ROOT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../" ABSOLUTE)

include(${ROOT_DIR}/cmake/toolchain-arm-none-eabi.cmake)

# Configure camera sensor type
# Supported values: OV5647, IMX219, IMX477, IMX708, HM0360
# Uncomment and modify the line below to select a specific camera sensor
# set(CAMERA_SENSOR_TYPE "OV5647")  # Default sensor, no need to set explicitly

# Configure event handler modules
# Supported modules: EVT_DATAPATH, EVT_I2CCOMM, EVT_UARTCOMM, EVT_CM55MMB, EVT_CM55MMB_NBAPP, EVT_CM55MTIMER, EVT_CM55STIMER
# You can enable multiple modules by separating them with semicolons
set(EVENT_HANDLER_MODULES "EVT_DATAPATH")

# Override the default linker script with project-specific one
# Comment out the next line to use the default grove.ld
set(LINKER_SCRIPT ${CMAKE_CURRENT_LIST_DIR}/custom_grove.ld)

include(${ROOT_DIR}/cmake/project.cmake)





