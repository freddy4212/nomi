/*
 * Copyright (c) 2025 tinyVision.ai Inc.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include <mpix/print.h>
#include <mpix/image.h>
#include <mpix/test.h>

#define WIDTH 16
#define HEIGHT 16

#define ERROR_MARGIN 13

static uint8_t bayerframe_in[WIDTH * HEIGHT * 1];
static uint8_t rgb24frame_out[WIDTH * HEIGHT * 3];

void test_bayer(uint32_t fourcc, uint32_t window_size, uint32_t expected_color)
{
	uint8_t r = expected_color >> 16;
	uint8_t g = expected_color >> 8;
	uint8_t b = expected_color >> 0;
	struct mpix_image img;
	int ret;

	mpix_image_from_buf(&img, bayerframe_in, sizeof(bayerframe_in), WIDTH, HEIGHT, fourcc);

	printf("input:\n");
	mpix_image_print_truecolor(&img);

	ret = mpix_image_debayer(&img, window_size);
	mpix_test_ok(ret);

	mpix_image_to_buf(&img, rgb24frame_out, sizeof(rgb24frame_out));

	printf("output: (expecting #%06x, R:%02x G:%02x B:%02x)\n", expected_color, r, g, b);
	mpix_image_print_truecolor(&img);

	for (int i = 0; i < sizeof(rgb24frame_out) / 3; i++) {
		uint8_t out_r = rgb24frame_out[i * 3 + 0];
		uint8_t out_g = rgb24frame_out[i * 3 + 1];
		uint8_t out_b = rgb24frame_out[i * 3 + 2];
		char *s = MPIX_FOURCC_TO_STR(fourcc);

		mpix_test_equal(r, out_r);
		mpix_test_equal(g, out_g);
		mpix_test_equal(b, out_b);
	}
}

int main(void)
{
	/* Generate test input data for 2x2 debayer */
	for (size_t h = 0; h < HEIGHT; h++) {
		memset(bayerframe_in + h * WIDTH, h % 2 ? 0xff : 0x00, WIDTH * 1);
	}

	test_bayer(MPIX_FMT_SRGGB8, 2, 0x007fff);
	test_bayer(MPIX_FMT_SGRBG8, 2, 0x007fff);
	test_bayer(MPIX_FMT_SBGGR8, 2, 0xff7f00);
	test_bayer(MPIX_FMT_SGBRG8, 2, 0xff7f00);

	/* Generate test input data for 3x3 debayer */
	for (size_t h = 0; h < HEIGHT; h++) {
		for (size_t w = 0; w < WIDTH; w++) {
			bayerframe_in[h * WIDTH + w] = (h + w) % 2 ? 0xff : 0x00;
		}
	}

	test_bayer(MPIX_FMT_SRGGB8, 3, 0x00ff00);
	test_bayer(MPIX_FMT_SGBRG8, 3, 0xff00ff);
	test_bayer(MPIX_FMT_SBGGR8, 3, 0x00ff00);
	test_bayer(MPIX_FMT_SGRBG8, 3, 0xff00ff);

	return 0;
}
