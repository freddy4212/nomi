/*
 * Copyright (c) 2025 tinyVision.ai Inc.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>

#include <mpix/image.h>
#include <mpix/print.h>
#include <mpix/test.h>

#define WIDTH_IN 6
#define HEIGHT_IN 10
#define PITCH_IN (WIDTH_IN * 3)

#define WIDTH_OUT 40
#define HEIGHT_OUT 22
#define PITCH_OUT (WIDTH_OUT * 3)

#define ERROR_MARGIN 9

/* Input/output buffers */
static uint8_t rgb24frame_in[WIDTH_IN * HEIGHT_IN * 3];
static uint8_t rgb24frame_out[WIDTH_OUT * HEIGHT_OUT * 3];

static void test_resize(uint32_t fourcc)
{
	struct mpix_image img;
	size_t w = WIDTH_OUT;
	size_t h = HEIGHT_OUT;
	size_t p = PITCH_OUT;
	int ret;

	mpix_image_from_buf(&img, rgb24frame_in, sizeof(rgb24frame_in), WIDTH_IN, HEIGHT_IN,
			    MPIX_FMT_RGB24);

	printf("input:\n");
	mpix_image_print_truecolor(&img);

	ret = mpix_image_convert(&img, fourcc);
	mpix_test_ok(ret);
	ret = mpix_image_resize(&img, MPIX_RESIZE_SUBSAMPLING, WIDTH_OUT, HEIGHT_OUT);
	mpix_test_ok(ret);
	ret = mpix_image_convert(&img, MPIX_FMT_RGB24);
	mpix_test_ok(ret);
	ret = mpix_image_to_buf(&img, rgb24frame_out, sizeof(rgb24frame_out));
	mpix_test_ok(ret);

	printf("output:\n");
	mpix_image_print_truecolor(&img);

	/* Test top left quadramt */
	mpix_test_within(rgb24frame_out[(0) * p + (0) * 3 + 0], 0x00, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(0) * p + (0) * 3 + 1], 0x00, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(0) * p + (0) * 3 + 2], 0x7f, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 - 1) * p + (w / 2 - 1) * 3 + 0], 0x00, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 - 1) * p + (w / 2 - 1) * 3 + 1], 0x00, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 - 1) * p + (w / 2 - 1) * 3 + 2], 0x7f, ERROR_MARGIN);

	/* Test bottom left quadrant */
	mpix_test_within(rgb24frame_out[(h - 1) * p + (0) * 3 + 0], 0x00, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h - 1) * p + (0) * 3 + 1], 0xff, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h - 1) * p + (0) * 3 + 2], 0x7f, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 + 1) * p + (w / 2 - 1) * 3 + 0], 0x00, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 + 1) * p + (w / 2 - 1) * 3 + 1], 0xff, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 + 1) * p + (w / 2 - 1) * 3 + 2], 0x7f, ERROR_MARGIN);

	/* Test top right quadrant */
	mpix_test_within(rgb24frame_out[(0) * p + (w - 1) * 3 + 0], 0xff, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(0) * p + (w - 1) * 3 + 1], 0x00, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(0) * p + (w - 1) * 3 + 2], 0x7f, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 - 1) * p + (w / 2 + 1) * 3 + 0], 0xff, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 - 1) * p + (w / 2 + 1) * 3 + 1], 0x00, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 - 1) * p + (w / 2 + 1) * 3 + 2], 0x7f, ERROR_MARGIN);

	/* Test bottom right quadrant */
	mpix_test_within(rgb24frame_out[(h - 1) * p + (w - 1) * 3 + 0], 0xff, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h - 1) * p + (w - 1) * 3 + 1], 0xff, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h - 1) * p + (w - 1) * 3 + 2], 0x7f, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 + 1) * p + (w / 2 + 1) * 3 + 0], 0xff, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 + 1) * p + (w / 2 + 1) * 3 + 1], 0xff, ERROR_MARGIN);
	mpix_test_within(rgb24frame_out[(h / 2 + 1) * p + (w / 2 + 1) * 3 + 2], 0x7f, ERROR_MARGIN);
}

int main(void)
{
	/* Generate test input data */
	for (uint16_t h = 0; h < HEIGHT_IN; h++) {
		for (uint16_t w = 0; w < WIDTH_IN; w++) {
			rgb24frame_in[h * PITCH_IN + w * 3 + 0] = w < WIDTH_IN / 2 ? 0x00 : 0xff;
			rgb24frame_in[h * PITCH_IN + w * 3 + 1] = h < HEIGHT_IN / 2 ? 0x00 : 0xff;
			rgb24frame_in[h * PITCH_IN + w * 3 + 2] = 0x7f;
		}
	}

	test_resize(MPIX_FMT_RGB24);
	test_resize(MPIX_FMT_RGB565);
	test_resize(MPIX_FMT_RGB565X);

	return 0;
}
