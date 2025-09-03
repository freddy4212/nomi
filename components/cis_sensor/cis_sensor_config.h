#ifndef CIS_SENSOR_CONFIG_H
#define CIS_SENSOR_CONFIG_H

/* Camera sensor configuration header */
/* This file provides unified interface for different camera sensors */

#ifdef __cplusplus
extern "C" {
#endif

/* Include the appropriate sensor header based on configuration */
#if defined(CIS_OV5647_ENABLED) || defined(CAMERA_SENSOR_OV5647)
    #include "cis_ov5647/cisdp_sensor.h"
    #define CAMERA_SENSOR_NAME "OV5647"
    #define CAMERA_SENSOR_OV5647
    
#elif defined(CIS_IMX219_ENABLED) || defined(CAMERA_SENSOR_IMX219)
    #include "cis_imx219/cisdp_sensor.h"
    #define CAMERA_SENSOR_NAME "IMX219"
    #define CAMERA_SENSOR_IMX219
    
#elif defined(CIS_IMX477_ENABLED) || defined(CAMERA_SENSOR_IMX477)
    #include "cis_imx477/cisdp_sensor.h"
    #define CAMERA_SENSOR_NAME "IMX477"
    #define CAMERA_SENSOR_IMX477
    
#elif defined(CIS_IMX708_ENABLED) || defined(CAMERA_SENSOR_IMX708)
    #include "cis_imx708/cisdp_sensor.h"
    #define CAMERA_SENSOR_NAME "IMX708"
    #define CAMERA_SENSOR_IMX708
    
#elif defined(CIS_HM0360_ENABLED) || defined(CAMERA_SENSOR_HM0360)
    #include "cis_hm0360/cisdp_sensor.h"
    #define CAMERA_SENSOR_NAME "HM0360"
    #define CAMERA_SENSOR_HM0360
    
#else
    #error "No camera sensor type defined! Please define CAMERA_SENSOR_TYPE in your CMakeLists.txt"
#endif

/* Common sensor interface functions */
/* All sensor drivers should implement these functions with the same signature */

/**
 * @brief Get the name of the currently configured camera sensor
 * @return Sensor name string
 */
static inline const char* cis_get_sensor_name(void) {
    return CAMERA_SENSOR_NAME;
}

/**
 * @brief Check if a specific sensor type is enabled
 */
#define IS_SENSOR_OV5647()  (defined(CAMERA_SENSOR_OV5647))
#define IS_SENSOR_IMX219()  (defined(CAMERA_SENSOR_IMX219))
#define IS_SENSOR_IMX477()  (defined(CAMERA_SENSOR_IMX477))
#define IS_SENSOR_IMX708()  (defined(CAMERA_SENSOR_IMX708))
#define IS_SENSOR_HM0360()  (defined(CAMERA_SENSOR_HM0360))

/**
 * @brief Sensor-specific configuration macros
 */
#ifdef CAMERA_SENSOR_OV5647
    #define SENSOR_DEFAULT_WIDTH    640
    #define SENSOR_DEFAULT_HEIGHT   480
    #define SENSOR_MAX_WIDTH        2592
    #define SENSOR_MAX_HEIGHT       1944
    #define SENSOR_BPP              8
    
#elif defined(CAMERA_SENSOR_IMX219)
    #define SENSOR_DEFAULT_WIDTH    640
    #define SENSOR_DEFAULT_HEIGHT   480
    #define SENSOR_MAX_WIDTH        3280
    #define SENSOR_MAX_HEIGHT       2464
    #define SENSOR_BPP              8
    
#elif defined(CAMERA_SENSOR_IMX477)
    #define SENSOR_DEFAULT_WIDTH    640
    #define SENSOR_DEFAULT_HEIGHT   480
    #define SENSOR_MAX_WIDTH        4056
    #define SENSOR_MAX_HEIGHT       3040
    #define SENSOR_BPP              8
    
#elif defined(CAMERA_SENSOR_IMX708)
    #define SENSOR_DEFAULT_WIDTH    640
    #define SENSOR_DEFAULT_HEIGHT   480
    #define SENSOR_MAX_WIDTH        2304
    #define SENSOR_MAX_HEIGHT       1296
    #define SENSOR_BPP              8
    
#elif defined(CAMERA_SENSOR_HM0360)
    #define SENSOR_DEFAULT_WIDTH    640
    #define SENSOR_DEFAULT_HEIGHT   480
    #define SENSOR_MAX_WIDTH        640
    #define SENSOR_MAX_HEIGHT       480
    #define SENSOR_BPP              8
#endif

#ifdef __cplusplus
}
#endif

#endif /* CIS_SENSOR_CONFIG_H */
