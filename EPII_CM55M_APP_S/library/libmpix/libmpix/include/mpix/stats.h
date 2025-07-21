/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_stats_h mpix/stats.h
 * @brief Compute statistics on images.
 * @{
 */
#ifndef MPIX_STATS_H
#define MPIX_STATS_H

#include <stdint.h>
#include <stddef.h>

/**
 * @brief Histogram of one or multiple channels.
 */
struct mpix_stats {
	/** Storage for the values. One buffer per channel. Maximum number of channels is 3. */
	uint16_t y_histogram[64];
	/** Average value for each histogram bin. */
	uint8_t y_histogram_vals[64];
	/** Average value for each histogram bin. */
	uint16_t y_histogram_total;
	/** Average pixel value */
	uint8_t rgb_average[3];
	/** Minimum of each channel */
	uint8_t rgb_min[3];
	/** Maximum of each channel */
	uint8_t rgb_max[3];
	/** Number of values collected for building these statistics. */
	uint16_t nvals;
};

/**
 * @brief Collect red, green, blue channel averages of all pixels in an RGB24 frame.
 *
 * If the @c nvals field of @p stats is non-zero, then this value will be used to select the number
 * of pixels sampled from the image. Otherwise a default will be provided.
 *
 * @param stats Struct collecting the image statistics.
 * @param buf Buffer of pixels in RGB24 format (3 bytes per pixel) to collect the statistics from.
 * @param width Width of the buffer in pixels.
 * @param height Height of the buffer in pixels.
 * @param fourcc Pixel format of the buffer.
 */
void mpix_stats_from_buf(struct mpix_stats *stats,
			 const uint8_t *buf, uint16_t width, uint16_t height, uint32_t fourcc);

/**
 * @brief Print a representation of the statistics in the console for debug purpose.
 *
 * @param stats The statistics to print out.
 */
void mpix_stats_print(struct mpix_stats *stats);

/**
 * @brief Get the mean value from a histogram.
 *
 * The result is the mean expressed as grayscale pixel value: range 0 to 255.
 *
 * @param stats Statistics collected from the image
 * @return The mean pixel value.
 */
uint8_t mpix_stats_get_y_mean(struct mpix_stats *stats);

#endif /** @} */
