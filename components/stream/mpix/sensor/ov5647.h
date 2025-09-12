/**
 * SPDX-License-Identifier: Apache-2.0
 * @file ov5647.h
 * @brief OV5647 camera sensor driver for MPIX stream interface
 */

#ifndef OV5647_H
#define OV5647_H

#include <mpix/sensor.h>

#include "sccb.h"
#include "mipi_csi.h"
#include "datapath.h"

#ifdef __cplusplus
extern "C" {
#endif

/* OV5647 chip information */
#define OV5647_CHIP_ID          0x5647
#define OV5647_I2C_ADDR         0x36

/* OV5647 supported resolutions */
typedef enum {
    OV5647_MODE_640x480_30FPS = 0,
    OV5647_MODE_1280x720_30FPS,
    OV5647_MODE_1920x1080_15FPS,
    OV5647_MODE_2592x1944_15FPS,
    OV5647_MODE_MAX
} ov5647_mode_t;

/* OV5647 hardware context */
struct ov5647_hw_ctx {
    /* I2C configuration */
    uint8_t i2c_addr;
    
    /* Current sensor state */
    ov5647_mode_t current_mode;
    bool streaming;
    bool initialized;
    
    /* Image format configuration */
    struct mpix_sensor_format current_format; 
    
    /* Control values */
    int brightness;      /* -2 to +2 */
    int contrast;        /* -2 to +2 */
    int saturation;      /* -2 to +2 */
    bool h_mirror;       /* horizontal mirror */
    bool v_flip;         /* vertical flip */
    int exposure;        /* auto exposure control */
    int white_balance;   /* auto white balance */
    int test_pattern;    /* test pattern mode */
};

/**
 * @brief Get the OV5647 sensor instance
 * @return Pointer to the sensor structure
 */
struct mpix_sensor *ov5647_get_sensor(void);

/**
 * @brief Initialize OV5647 hardware context
 * @param hw_ctx Hardware context to initialize
 * @return 0 on success, negative error code on failure
 */
int ov5647_hw_ctx_init(struct ov5647_hw_ctx *hw_ctx);



#ifdef __cplusplus
}
#endif

#endif /* OV5647_H */
