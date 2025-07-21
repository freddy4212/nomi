/* SPDX-License-Identifier: Apache-2.0 */

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <mpix/formats.h>
#include <mpix/op_convert.h>
#include <mpix/sample.h>
#include <mpix/utils.h>

#define MPIX_IDX_R 0
#define MPIX_IDX_G 1
#define MPIX_IDX_B 2

static inline void mpix_sample_random_raw24(const uint8_t *buf, uint16_t width, uint16_t height,
					    uint8_t rgb[3])
{
	uint32_t i = (mpix_lcg_rand_u32() % (width * height)) * 3;

	memcpy(rgb, &buf[i], 3);
}

static inline void mpix_sample_random_yuyv(const uint8_t *buf, uint16_t width, uint16_t height,
					    uint8_t rgb[3])
{
	uint32_t i = mpix_lcg_rand_u32() % (width * height) / 2 * 4;
	uint8_t rgb2[3 * 2];

	mpix_convert_yuyv_to_rgb24_bt709(&buf[i], rgb2, 2);
	memcpy(rgb, rgb2, 3);
}

static inline void mpix_sample_random_rgb565le(const uint8_t *buf, uint16_t width, uint16_t height,
					    uint8_t rgb[3])
{
	uint32_t i = mpix_lcg_rand_u32() % (width * height) * 2;

	mpix_convert_rgb565le_to_rgb24(&buf[i], rgb, 1);
}

static inline void mpix_sample_random_bayer(const uint8_t *buf, uint16_t width, uint16_t height,
					    uint8_t rgb[3], int i0, int i1, int i2, int i3)
{
	uint32_t w = (mpix_lcg_rand_u32() % width) & ~1U;
	uint32_t h = (mpix_lcg_rand_u32() % height) & ~1U;

	rgb[i0] = buf[(h + 0) * width + (w + 0)];
	rgb[i1] = buf[(h + 0) * width + (w + 1)];
	rgb[i2] = buf[(h + 1) * width + (w + 0)];
	rgb[i3] = buf[(h + 1) * width + (w + 1)];
}

int mpix_sample_random_rgb(const uint8_t *buf, uint16_t width, uint16_t height, uint32_t fourcc,
			   uint8_t *rgb)
{
	switch (fourcc) {
	case MPIX_FMT_RGB24:
		mpix_sample_random_raw24(buf, width, height, rgb);
		break;
	case MPIX_FMT_RGB565:
		mpix_sample_random_rgb565le(buf, width, height, rgb);
		break;
	case MPIX_FMT_YUYV:
		mpix_sample_random_yuyv(buf, width, height, rgb);
		break;
	case MPIX_FMT_SRGGB8:
		mpix_sample_random_bayer(buf, width, height, rgb,
					 MPIX_IDX_R, MPIX_IDX_G, MPIX_IDX_G, MPIX_IDX_B);
		break;
	case MPIX_FMT_BGGR8:
	case MPIX_FMT_SBGGR8:
		mpix_sample_random_bayer(buf, width, height, rgb,
					 MPIX_IDX_B, MPIX_IDX_G, MPIX_IDX_G, MPIX_IDX_R);
		break;
	case MPIX_FMT_SGBRG8:
		mpix_sample_random_bayer(buf, width, height, rgb,
					 MPIX_IDX_G, MPIX_IDX_B, MPIX_IDX_R, MPIX_IDX_G);
		break;
	case MPIX_FMT_SGRBG8:
		mpix_sample_random_bayer(buf, width, height, rgb,
					 MPIX_IDX_G, MPIX_IDX_R, MPIX_IDX_B, MPIX_IDX_G);
		break;
	default:
		MPIX_ERR("Unsupported pixel format %s", MPIX_FOURCC_TO_STR(fourcc));
		return -ENOTSUP;
	}

	return 0;
}

int mpix_image_sample_random_rgb(struct mpix_image *img, uint8_t rgb[3])
{
	return mpix_sample_random_rgb(img->buffer, img->width, img->height, img->fourcc, rgb);
}
