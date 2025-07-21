/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_print_h mpix/print.h
 * @brief Print images and statistics
 * @{
 */
#ifndef MPIX_PRINT_H
#define MPIX_PRINT_H

#include <stddef.h>
#include <stdint.h>

/**
 * @brief Print a buffer using higher quality TRUECOLOR terminal escape codes.
 *
 * @param buf Imagme buffer to display in the terminal.
 * @param size Size of the buffer in bytes.
 * @param width Number of pixel of the input buffer in width
 * @param height Max number of rows to print
 * @param fourcc Format of the buffer to print
 */
void mpix_print_buf_truecolor(const uint8_t *buf, size_t size, uint16_t width, uint16_t height,
			      uint32_t fourcc);
/**
 * @brief Print a buffer using higher speed 256COLOR terminal escape codes.
 * @copydetails mpix_print_buf_truecolor()
 */
void mpix_print_buf_256color(const uint8_t *buf, size_t size, uint16_t width, uint16_t height,
			     uint32_t fourcc);

/**
 * @brief Print two pixels using TRUECOLOR terminal escape sequences
 *
 * No newline character is printed at the end.
 *
 * @param row0 The pixel to print at the top.
 * @param row1 The pixel to print at the bottom.
 */
void mpix_print_truecolor(const uint8_t row0[3], const uint8_t row1[3]);
/**
 * @brief Print two pixels using 256COLOR terminal escape sequences
 * @copydetails mpix_print_truecolor()
 */
void mpix_print_256color(const uint8_t row0[3], const uint8_t row1[3]);
/**
 * @brief Print two grayscale pixels using terminal escape sequences
 * @copydetails mpix_print_truecolor()
 */
void mpix_print_256gray(uint8_t row0, uint8_t row1);

/**
 * @brief Hexdump a buffer in the specified format.
 *
 * @param buf Input buffer to display in the terminal.
 * @param size Size of the input buffer in bytes.
 * @param width Number of pixel of the input buffer in width
 * @param height Max number of rows to print
 * @param fourcc Four Character Code identifying the format to hexdump.
 */
void mpix_hexdump(const uint8_t *buf, size_t size, uint16_t width, uint16_t height,
		  uint32_t fourcc);

/**
 * @brief Printing RGB histograms to the terminal.
 *
 * @param r_hist Buckets for the red channel.
 * @param g_hist Buckets for the green channel.
 * @param b_hist Buckets for the blue channel.
 * @param size Total number of buckets in total contained within @p rgb24hist all channels included.
 * @param height Desired height of the chart in pixels.
 */
void mpix_print_rgb_hist(const uint16_t *r_hist, const uint16_t *g_hist, const uint16_t *b_hist,
			 size_t size, uint16_t height);

/**
 * @brief Printing Y histograms to the terminal.
 *
 * @param y8hist Buffer storing the histogram for the Y (luma) channel.
 * @param size Total number of buckets in total contained within @p hist.
 * @param height Desired height of the chart in pixels.
 */
void mpix_print_y_hist(const uint16_t *y8hist, size_t size, uint16_t height);

#endif /** @} */
