/**
 * SPDX-License-Identifier: Apache-2.0
 * @file imx219.h
 * @brief IMX219 camera sensor driver for MPIX stream interface
 */

#ifndef IMX219_H
#define IMX219_H

#include <mpix/sensor.h>

#ifdef __cplusplus
extern "C" {
#endif

/* IMX219 chip information */
#define IMX219_CHIP_ID          0x0219
#define IMX219_I2C_ADDR         0x10

/* IMX219 supported resolutions */
typedef enum {
    IMX219_MODE_640x480_30FPS = 0,
    IMX219_MODE_1280x960_30FPS,
    IMX219_MODE_MAX
} imx219_mode_t;

/* IMX219 hardware context */
struct imx219_hw_ctx {
    
    /* I2C configuration */
    uint8_t i2c_addr;
    
    /* Current sensor state */
    imx219_mode_t current_mode;
    bool streaming;
    bool initialized;
    
    /* Image format configuration */
    struct mpix_sensor_format current_format;
    
    /* Control values */
    bool h_mirror;       /* horizontal mirror */
    bool v_flip;         /* vertical flip */
    int exposure;        /* auto exposure control */
    int white_balance;   /* auto white balance */
    int test_pattern;    /* test pattern mode */
};

/**
 * @brief Get the IMX219 sensor instance
 * @return Pointer to the sensor structure
 */
struct mpix_sensor *imx219_get_sensor(void);

/**
 * @brief Initialize IMX219 hardware context
 * @param hw_ctx Hardware context to initialize
 * @return 0 on success, negative error code on failure
 */
int imx219_hw_ctx_init(struct imx219_hw_ctx *hw_ctx);



#ifdef __cplusplus
}
#endif

#endif /* IMX219_H */
