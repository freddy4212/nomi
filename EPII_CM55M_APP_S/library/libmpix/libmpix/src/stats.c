/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#include <mpix/image.h>
#include <mpix/stats.h>
#include <mpix/sample.h>
#include <mpix/print.h>
#include <mpix/op_convert.h>

/* Arbitrary value estimated good enough for most cases */
#define MPIX_STATS_DEFAULT_NVALS 1000

void mpix_stats_from_buf(struct mpix_stats *stats,
			 const uint8_t *buf, uint16_t width, uint16_t height, uint32_t fourcc)
{
	uint32_t rgb_sum[3] = {0};
	uint16_t nvals;
	int ret;

	/* Reset the statistics to initial values */
	nvals = stats->nvals > 0 ? stats->nvals : MPIX_STATS_DEFAULT_NVALS;
	memset(stats, 0x00, sizeof(*stats));
	stats->nvals = nvals;

	/* Accumulate the statistics from the pixels */
	for (uint16_t i = 0; i < nvals; i++) {
		uint8_t rgb_value[3];
		uint8_t thres = 0xf0;

		ret = mpix_sample_random_rgb(buf, width, height, fourcc, rgb_value);
		if (ret < 0) {
			return;
		}

		/* Histogram statistics by ignoring the red/green/blue value */
		stats->y_histogram[rgb_value[0] >> 2]++;
		stats->y_histogram[rgb_value[1] >> 2]++;
		stats->y_histogram[rgb_value[2] >> 2]++;

		/* Over-exposed pixel, do not retain it for statistics */
		if (rgb_value[0] > thres && rgb_value[1] > thres && rgb_value[2] > thres) {
			continue;
		}

		/* RGB statistics */
		rgb_sum[0] += rgb_value[0];
		rgb_sum[1] += rgb_value[1];
		rgb_sum[2] += rgb_value[2];
	}

	/* Completion for Y histogram */
	for (size_t i = 0; i < ARRAY_SIZE(stats->y_histogram_vals); i++) {
		const uint8_t step = 256 / ARRAY_SIZE(stats->y_histogram_vals);

		/* Initialize to the middle value of each range */
		stats->y_histogram_vals[i] = i * step + step / 2;

		/* Values got aggregated for RGB24 as if they were RAW8, adjust */
		stats->y_histogram_vals[i] /= 3;
	}

	/* Completion for RGB averages */
	stats->rgb_average[0] = rgb_sum[0] / nvals;
	stats->rgb_average[1] = rgb_sum[1] / nvals;
	stats->rgb_average[2] = rgb_sum[2] / nvals;
}

void mpix_image_stats(struct mpix_image *img, struct mpix_stats *stats)
{
	mpix_stats_from_buf(stats, img->buffer, img->width, img->height, img->fourcc);
}

void mpix_stats_print(struct mpix_stats *stats)
{
	uint8_t *rgb = stats->rgb_average;

	mpix_port_printf("Average #%02x%02x%02x ", rgb[0], rgb[1], rgb[2]);
	mpix_print_truecolor(rgb, rgb);
	mpix_port_printf(" \x1b[m for %u values sampled\n", stats->nvals);
	mpix_print_y_hist(stats->y_histogram, ARRAY_SIZE(stats->y_histogram), 10);
}

uint8_t mpix_stats_get_y_mean(struct mpix_stats *stats)
{
	uint32_t nvals = 0;

	for (int i = 0; i < ARRAY_SIZE(stats->y_histogram); i++) {
		nvals += stats->y_histogram[i];

		if (nvals >= stats->nvals / 2) {
			return i * 256 / ARRAY_SIZE(stats->y_histogram);
		}
	}

	assert(0 /* The histogram is expected to contain all values */);
	return 0;
}
