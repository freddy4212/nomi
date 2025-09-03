# Camera sensor component with conditional compilation support
# Set the camera sensor to use by defining CAMERA_SENSOR_TYPE in your application
# Supported values: OV5647, IMX219, IMX477, IMX708, HM0360
# Default: OV5647

if(NOT DEFINED CAMERA_SENSOR_TYPE)
    set(CAMERA_SENSOR_TYPE "OV5647")
    message(STATUS "CAMERA_SENSOR_TYPE not defined, using default: ${CAMERA_SENSOR_TYPE}")
endif()

# Convert to lowercase for directory name matching
string(TOLOWER ${CAMERA_SENSOR_TYPE} CAMERA_SENSOR_LOWER)

# Define sensor-specific settings
set(SENSOR_SRCS "")
set(SENSOR_INCLUDE_DIRS "")
set(SENSOR_DEFINITIONS "")

if(CAMERA_SENSOR_TYPE STREQUAL "OV5647")
    set(SENSOR_SRCS ${CMAKE_CURRENT_LIST_DIR}/cis_ov5647/cisdp_sensor.c)
    set(SENSOR_INCLUDE_DIRS ${CMAKE_CURRENT_LIST_DIR}/cis_ov5647)
    set(SENSOR_DEFINITIONS CIS_OV5647_ENABLED)
    message(STATUS "Building with OV5647 camera sensor support")
    
elseif(CAMERA_SENSOR_TYPE STREQUAL "IMX219")
    set(SENSOR_SRCS ${CMAKE_CURRENT_LIST_DIR}/cis_imx219/cisdp_sensor.c)
    set(SENSOR_INCLUDE_DIRS ${CMAKE_CURRENT_LIST_DIR}/cis_imx219)
    set(SENSOR_DEFINITIONS CIS_IMX219_ENABLED)
    message(STATUS "Building with IMX219 camera sensor support")
    
elseif(CAMERA_SENSOR_TYPE STREQUAL "IMX477")
    set(SENSOR_SRCS ${CMAKE_CURRENT_LIST_DIR}/cis_imx477/cisdp_sensor.c)
    set(SENSOR_INCLUDE_DIRS ${CMAKE_CURRENT_LIST_DIR}/cis_imx477)
    set(SENSOR_DEFINITIONS CIS_IMX477_ENABLED)
    message(STATUS "Building with IMX477 camera sensor support")
    
elseif(CAMERA_SENSOR_TYPE STREQUAL "IMX708")
    set(SENSOR_SRCS ${CMAKE_CURRENT_LIST_DIR}/cis_imx708/cisdp_sensor.c)
    set(SENSOR_INCLUDE_DIRS ${CMAKE_CURRENT_LIST_DIR}/cis_imx708)
    set(SENSOR_DEFINITIONS CIS_IMX708_ENABLED)
    message(STATUS "Building with IMX708 camera sensor support")
    
elseif(CAMERA_SENSOR_TYPE STREQUAL "HM0360")
    set(SENSOR_SRCS ${CMAKE_CURRENT_LIST_DIR}/cis_hm0360/cisdp_sensor.c)
    set(SENSOR_INCLUDE_DIRS ${CMAKE_CURRENT_LIST_DIR}/cis_hm0360)
    set(SENSOR_DEFINITIONS CIS_HM0360_ENABLED)
    message(STATUS "Building with HM0360 camera sensor support")
    
else()
    message(FATAL_ERROR "Unsupported CAMERA_SENSOR_TYPE: ${CAMERA_SENSOR_TYPE}. Supported types: OV5647, IMX219, IMX477, IMX708, HM0360")
endif()

component_register(
    COMPONENT_NAME cis_sensor
    SRCS
        ${SENSOR_SRCS}
    INCLUDE_DIRS
        ${CMAKE_CURRENT_LIST_DIR}
        ${SENSOR_INCLUDE_DIRS}
    COMPILE_DEFINITIONS
        CIS_SUPPORT_ENABLED
        ${SENSOR_DEFINITIONS}
        CAMERA_SENSOR_${CAMERA_SENSOR_TYPE}
)
