/**
 * SPDX-License-Identifier: Apache-2.0
 * @file sccb.h
 * @brief Simple I2C operations for camera sensors (SCCB)
 */

#ifndef SCCB_H
#define SCCB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize SCCB/I2C interface
 * @return 0 on success, negative error code on failure
 */
int sccb_init(void);

/**
 * @brief Write a single byte to sensor register
 * @param addr 7-bit I2C device address
 * @param reg Register address
 * @param value Value to write
 * @return 0 on success, negative error code on failure
 */
int sccb_write_reg(uint8_t addr, uint16_t reg, uint8_t value);

/**
 * @brief Read a single byte from sensor register
 * @param addr 7-bit I2C device address
 * @param reg Register address
 * @param value Pointer to store read value
 * @return 0 on success, negative error code on failure
 */
int sccb_read_reg(uint8_t addr, uint16_t reg, uint8_t *value);

/**
 * @brief Delay function for sensor operations
 * @param ms Delay in milliseconds
 */
void sccb_delay_ms(uint32_t ms);

#ifdef __cplusplus
}
#endif

#endif /* SCCB_H */