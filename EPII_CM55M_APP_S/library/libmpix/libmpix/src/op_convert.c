/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <stdint.h>
#include <errno.h>

#include <mpix/utils.h>
#include <mpix/op_convert.h>
#include <mpix/genlist.h>

void mpix_convert_op(struct mpix_base_op *base)
{
	struct mpix_convert_op *op = (void *)base;
	const uint8_t *line_in = mpix_op_get_input_line(base);
	uint8_t *line_out = mpix_op_get_output_line(base);

	op->convert_fn(line_in, line_out, base->width);
	mpix_op_done(base);
}

__attribute__((weak))
void mpix_convert_rgb24_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width)
{
	memcpy(dst, src, width * 3);
}
MPIX_REGISTER_CONVERT_OP(rgb24_rgb24, mpix_convert_rgb24_to_rgb24, RGB24, RGB24);

__attribute__((weak))
void mpix_convert_rgb24_to_rgb332(const uint8_t *rgb24, uint8_t *rgb332, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 3, o += 1) {
		rgb332[o] = 0;
		rgb332[o] |= (uint16_t)rgb24[i + 0] >> 5 << (0 + 3 + 2);
		rgb332[o] |= (uint16_t)rgb24[i + 1] >> 5 << (0 + 0 + 2);
		rgb332[o] |= (uint16_t)rgb24[i + 2] >> 6 << (0 + 0 + 0);
	}
}
MPIX_REGISTER_CONVERT_OP(rgb24_rgb332, mpix_convert_rgb24_to_rgb332, RGB24, RGB332);

__attribute__((weak))
void mpix_convert_rgb332_to_rgb24(const uint8_t *rgb332, uint8_t *rgb24, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 1, o += 3) {
		rgb24[o + 0] = rgb332[i] >> (0 + 3 + 2) << 5;
		rgb24[o + 1] = rgb332[i] >> (0 + 0 + 2) << 5;
		rgb24[o + 2] = rgb332[i] >> (0 + 0 + 0) << 6;
	}
}
MPIX_REGISTER_CONVERT_OP(rgb332_rgb24, mpix_convert_rgb332_to_rgb24, RGB332, RGB24);

static inline uint16_t mpix_rgb24_to_rgb565(const uint8_t rgb24[3])
{
	uint16_t rgb565 = 0;

	rgb565 |= ((uint16_t)rgb24[0] >> 3 << (0 + 6 + 5));
	rgb565 |= ((uint16_t)rgb24[1] >> 2 << (0 + 0 + 5));
	rgb565 |= ((uint16_t)rgb24[2] >> 3 << (0 + 0 + 0));
	return rgb565;
}

static inline void mpix_rgb565_to_rgb24(uint16_t rgb565, uint8_t rgb24[3])
{
	rgb24[0] = rgb565 >> (0 + 6 + 5) << 3;
	rgb24[1] = rgb565 >> (0 + 0 + 5) << 2;
	rgb24[2] = rgb565 >> (0 + 0 + 0) << 3;
}

__attribute__((weak))
void mpix_convert_rgb24_to_rgb565be(const uint8_t *rgb24, uint8_t *rgb565be, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 3, o += 2) {
		*(uint16_t *)&rgb565be[o] = mpix_htobe16(mpix_rgb24_to_rgb565(&rgb24[i]));
	}
}
MPIX_REGISTER_CONVERT_OP(rgb24_rgb565x, mpix_convert_rgb24_to_rgb565be, RGB24, RGB565X);

__attribute__((weak))
void mpix_convert_rgb24_to_rgb565le(const uint8_t *rgb24, uint8_t *rgb565le, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 3, o += 2) {
		*(uint16_t *)&rgb565le[o] = mpix_htole16(mpix_rgb24_to_rgb565(&rgb24[i]));
	}
}
MPIX_REGISTER_CONVERT_OP(rgb24_rgb565, mpix_convert_rgb24_to_rgb565le, RGB24, RGB565);

__attribute__((weak))
void mpix_convert_rgb565be_to_rgb24(const uint8_t *rgb565be, uint8_t *rgb24, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 2, o += 3) {
		mpix_rgb565_to_rgb24(mpix_be16toh(*(uint16_t *)&rgb565be[i]), &rgb24[o]);
	}
}
MPIX_REGISTER_CONVERT_OP(rgb565x_rgb24, mpix_convert_rgb565be_to_rgb24, RGB565X, RGB24);

__attribute__((weak))
void mpix_convert_rgb565le_to_rgb24(const uint8_t *rgb565le, uint8_t *rgb24, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 2, o += 3) {
		mpix_rgb565_to_rgb24(mpix_le16toh(*(uint16_t *)&rgb565le[i]), &rgb24[o]);
	}
}
MPIX_REGISTER_CONVERT_OP(rgb565_rgb24, mpix_convert_rgb565le_to_rgb24, RGB565, RGB24);

#define Q21(val) ((int32_t)((val) * (1 << 21)))

static inline uint8_t mpix_rgb24_to_y8_bt709(const uint8_t rgb24[3])
{
	int16_t r = rgb24[0], g = rgb24[1], b = rgb24[2];

	return CLAMP(((Q21(+0.1826) * r + Q21(+0.6142) * g + Q21(+0.0620) * b) >> 21) + 16,
		     0x00, 0xff);
}

uint8_t mpix_rgb24_get_luma_bt709(const uint8_t rgb24[3])
{
	return mpix_rgb24_to_y8_bt709(rgb24);
}

static inline uint8_t mpix_rgb24_to_u8_bt709(const uint8_t rgb24[3])
{
	int16_t r = rgb24[0], g = rgb24[1], b = rgb24[2];

	return CLAMP(((Q21(-0.1006) * r + Q21(-0.3386) * g + Q21(+0.4392) * b) >> 21) + 128,
		     0x00, 0xff);
}

static inline uint8_t mpix_rgb24_to_v8_bt709(const uint8_t rgb24[3])
{
	int16_t r = rgb24[0], g = rgb24[1], b = rgb24[2];

	return CLAMP(((Q21(+0.4392) * r + Q21(-0.3989) * g + Q21(-0.0403) * b) >> 21) + 128,
		     0x00, 0xff);
}

static inline void mpix_yuv24_to_rgb24_bt709(const uint8_t y, uint8_t u, uint8_t v,
					      uint8_t rgb24[3])
{
	int32_t yy = (int32_t)y - 16, uu = (int32_t)u - 128, vv = (int32_t)v - 128;

	/* Y range [16:235], U/V range [16:240], RGB range[0:255] (full range) */
	rgb24[0] = CLAMP((Q21(+1.1644) * yy + Q21(+0.0000) * uu + Q21(+1.7928) * vv) >> 21,
			 0x00, 0xff);
	rgb24[1] = CLAMP((Q21(+1.1644) * yy + Q21(-0.2133) * uu + Q21(-0.5330) * vv) >> 21,
			 0x00, 0xff);
	rgb24[2] = CLAMP((Q21(+1.1644) * yy + Q21(+2.1124) * uu + Q21(+0.0000) * vv) >> 21,
			 0x00, 0xff);
}

#undef Q21

__attribute__((weak))
void mpix_convert_yuv24_to_rgb24_bt709(const uint8_t *yuv24, uint8_t *rgb24, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 3, o += 3) {
		mpix_yuv24_to_rgb24_bt709(yuv24[i + 0], yuv24[i + 1], yuv24[i + 2], &rgb24[o]);
	}
}
MPIX_REGISTER_CONVERT_OP(yuv24_rgb24, mpix_convert_yuv24_to_rgb24_bt709, YUV24, RGB24);

void mpix_convert_rgb24_to_yuv24_bt709(const uint8_t *rgb24, uint8_t *yuv24, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 3, o += 3) {
		yuv24[o + 0] = mpix_rgb24_to_y8_bt709(&rgb24[i]);
		yuv24[o + 1] = mpix_rgb24_to_u8_bt709(&rgb24[i]);
		yuv24[o + 2] = mpix_rgb24_to_v8_bt709(&rgb24[i]);
	}
}
MPIX_REGISTER_CONVERT_OP(rgb24_yuv24, mpix_convert_rgb24_to_yuv24_bt709, RGB24, YUV24);

__attribute__((weak))
void mpix_convert_yuv24_to_yuyv(const uint8_t *yuv24, uint8_t *yuyv, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w + 2 <= width; w += 2, i += 6, o += 4) {
		/* Pixel 0 */
		yuyv[o + 0] = yuv24[i + 0];
		yuyv[o + 1] = yuv24[i + 1];
		/* Pixel 1 */
		yuyv[o + 2] = yuv24[i + 3];
		yuyv[o + 3] = yuv24[i + 5];
	}
}
MPIX_REGISTER_CONVERT_OP(yuv24_yuyv, mpix_convert_yuv24_to_yuyv, YUV24, YUYV);

__attribute__((weak))
void mpix_convert_yuyv_to_yuv24(const uint8_t *yuyv, uint8_t *yuv24, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w + 2 <= width; w += 2, i += 4, o += 6) {
		/* Pixel 0 */
		yuv24[o + 0] = yuyv[i + 0];
		yuv24[o + 1] = yuyv[i + 1];
		yuv24[o + 2] = yuyv[i + 3];
		/* Pixel 1 */
		yuv24[o + 3] = yuyv[i + 2];
		yuv24[o + 4] = yuyv[i + 1];
		yuv24[o + 5] = yuyv[i + 3];
	}
}
MPIX_REGISTER_CONVERT_OP(yuyv_yuv24, mpix_convert_yuyv_to_yuv24, YUYV, YUV24);

__attribute__((weak))
void mpix_convert_rgb24_to_yuyv_bt709(const uint8_t *rgb24, uint8_t *yuyv, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w + 2 <= width; w += 2, i += 6, o += 4) {
		/* Pixel 0 */
		yuyv[o + 0] = mpix_rgb24_to_y8_bt709(&rgb24[i + 0]);
		yuyv[o + 1] = mpix_rgb24_to_u8_bt709(&rgb24[i + 0]);
		/* Pixel 1 */
		yuyv[o + 2] = mpix_rgb24_to_y8_bt709(&rgb24[i + 3]);
		yuyv[o + 3] = mpix_rgb24_to_v8_bt709(&rgb24[i + 3]);
	}
}
MPIX_REGISTER_CONVERT_OP(rgb24_yuyv, mpix_convert_rgb24_to_yuyv_bt709, RGB24, YUYV);

__attribute__((weak))
void mpix_convert_yuyv_to_rgb24_bt709(const uint8_t *yuyv, uint8_t *rgb24, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w + 2 <= width; w += 2, i += 4, o += 6) {
		/* Pixel 0 */
		mpix_yuv24_to_rgb24_bt709(yuyv[i + 0], yuyv[i + 1], yuyv[i + 3], &rgb24[o + 0]);
		/* Pixel 1 */
		mpix_yuv24_to_rgb24_bt709(yuyv[i + 2], yuyv[i + 1], yuyv[i + 3], &rgb24[o + 3]);
	}
}
MPIX_REGISTER_CONVERT_OP(yuyv_rgb24, mpix_convert_yuyv_to_rgb24_bt709, YUYV, RGB24);

__attribute__((weak))
void mpix_convert_y8_to_rgb24_bt709(const uint8_t *y8, uint8_t *rgb24, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 1, o += 3) {
		mpix_yuv24_to_rgb24_bt709(y8[i], UINT8_MAX / 2, UINT8_MAX / 2, &rgb24[o]);
	}
}
MPIX_REGISTER_CONVERT_OP(grey_rgb24, mpix_convert_y8_to_rgb24_bt709, GREY, RGB24);

__attribute__((weak))
void mpix_convert_rgb24_to_y8_bt709(const uint8_t *rgb24, uint8_t *y8, uint16_t width)
{
	for (size_t i = 0, o = 0, w = 0; w < width; w++, i += 3, o += 1) {
		y8[o] = mpix_rgb24_to_y8_bt709(&rgb24[i]);
	}
}
MPIX_REGISTER_CONVERT_OP(rgb24_grey, mpix_convert_rgb24_to_y8_bt709, RGB24, GREY);

static const struct mpix_convert_op **mpix_convert_op_list =
	(const struct mpix_convert_op *[]){MPIX_LIST_CONVERT_OP};

int mpix_image_convert(struct mpix_image *img, uint32_t new_format)
{
	const struct mpix_convert_op *op = NULL;

	if (img->fourcc == new_format) {
		/* no-op */
		return 0;
	}

	for (size_t i = 0; mpix_convert_op_list[i] != NULL; i++) {
		const struct mpix_convert_op *tmp = mpix_convert_op_list[i];

		if (tmp->base.fourcc_src == img->fourcc && tmp->base.fourcc_dst == new_format) {
			op = tmp;
			break;
		}
	}

	if (op == NULL) {
		MPIX_ERR("Conversion operation from %s to %s not found",
			 MPIX_FOURCC_TO_STR(img->fourcc), MPIX_FOURCC_TO_STR(new_format));
		return mpix_image_error(img, -ENOSYS);
	}

	return mpix_image_append_uncompressed_op(img, &op->base, sizeof(*op));
}
