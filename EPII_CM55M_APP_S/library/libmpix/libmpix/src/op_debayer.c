/* SPDX-License-Identifier: Apache-2.0 */

#include <stdint.h>
#include <errno.h>

#include <mpix/genlist.h>
#include <mpix/image.h>
#include <mpix/op_debayer.h>

/* 3x3 debayer */

#define FOLD_L_3X3(l0, l1, l2)                                                                     \
	{                                                                                          \
		{l0[1], l0[0], l0[1]},                                                             \
		{l1[1], l1[0], l1[1]},                                                             \
		{l2[1], l2[0], l2[1]},                                                             \
	}

#define FOLD_R_3X3(l0, l1, l2, n)                                                                  \
	{                                                                                          \
		{l0[(n) - 2], l0[(n) - 1], l0[(n) - 2]},                                           \
		{l1[(n) - 2], l1[(n) - 1], l1[(n) - 2]},                                           \
		{l2[(n) - 2], l2[(n) - 1], l2[(n) - 2]},                                           \
	}

static inline void mpix_rggb8_to_rgb24_3x3(const uint8_t rgr0[3], const uint8_t gbg1[3],
					   const uint8_t rgr2[3], uint8_t rgb24[3])
{
	rgb24[0] = ((uint16_t)rgr0[0] + rgr0[2] + rgr2[0] + rgr2[2]) / 4;
	rgb24[1] = ((uint16_t)rgr0[1] + gbg1[2] + gbg1[0] + rgr2[1]) / 4;
	rgb24[2] = gbg1[1];
}

static inline void mpix_bggr8_to_rgb24_3x3(const uint8_t bgb0[3], const uint8_t grg1[3],
					   const uint8_t bgb2[3], uint8_t rgb24[3])
{
	rgb24[0] = grg1[1];
	rgb24[1] = ((uint16_t)bgb0[1] + grg1[2] + grg1[0] + bgb2[1]) / 4;
	rgb24[2] = ((uint16_t)bgb0[0] + bgb0[2] + bgb2[0] + bgb2[2]) / 4;
}

static inline void mpix_grbg8_to_rgb24_3x3(const uint8_t grg0[3], const uint8_t bgb1[3],
					   const uint8_t grg2[3], uint8_t rgb24[3])
{
	rgb24[0] = ((uint16_t)grg0[1] + grg2[1]) / 2;
	rgb24[1] = bgb1[1];
	rgb24[2] = ((uint16_t)bgb1[0] + bgb1[2]) / 2;
}

static inline void mpix_gbrg8_to_rgb24_3x3(const uint8_t gbg0[3], const uint8_t rgr1[3],
					   const uint8_t gbg2[3], uint8_t rgb24[3])
{
	rgb24[0] = ((uint16_t)rgr1[0] + rgr1[2]) / 2;
	rgb24[1] = rgr1[1];
	rgb24[2] = ((uint16_t)gbg0[1] + gbg2[1]) / 2;
}

__attribute__((weak))
void mpix_convert_rggb8_to_rgb24_3x3(const uint8_t *i0, const uint8_t *i1, const uint8_t *i2,
					    uint8_t *o0, uint16_t w)
{
	uint8_t il[3][3] = FOLD_L_3X3(i0, i1, i2);
	uint8_t ir[3][3] = FOLD_R_3X3(i0, i1, i2, w);

	assert(w >= 4 && w % 2 == 0);

	mpix_grbg8_to_rgb24_3x3(il[0], il[1], il[2], &o0[0]);
	for (size_t i = 0, o = 3; i + 4 <= w; i += 2, o += 6) {
		mpix_rggb8_to_rgb24_3x3(&i0[i + 0], &i1[i + 0], &i2[i + 0], &o0[o + 0]);
		mpix_grbg8_to_rgb24_3x3(&i0[i + 1], &i1[i + 1], &i2[i + 1], &o0[o + 3]);
	}
	mpix_rggb8_to_rgb24_3x3(ir[0], ir[1], ir[2], &o0[w * 3 - 3]);
}

__attribute__((weak))
void mpix_convert_grbg8_to_rgb24_3x3(const uint8_t *i0, const uint8_t *i1, const uint8_t *i2,
					    uint8_t *o0, uint16_t w)
{
	uint8_t il[3][4] = FOLD_L_3X3(i0, i1, i2);
	uint8_t ir[3][4] = FOLD_R_3X3(i0, i1, i2, w);

	assert(w >= 4 && w % 2 == 0);

	mpix_rggb8_to_rgb24_3x3(il[0], il[1], il[2], &o0[0]);
	for (size_t i = 0, o = 3; i + 4 <= w; i += 2, o += 6) {
		mpix_grbg8_to_rgb24_3x3(&i0[i + 0], &i1[i + 0], &i2[i + 0], &o0[o + 0]);
		mpix_rggb8_to_rgb24_3x3(&i0[i + 1], &i1[i + 1], &i2[i + 1], &o0[o + 3]);
	}
	mpix_grbg8_to_rgb24_3x3(ir[0], ir[1], ir[2], &o0[w * 3 - 3]);
}

__attribute__((weak))
void mpix_convert_bggr8_to_rgb24_3x3(const uint8_t *i0, const uint8_t *i1, const uint8_t *i2,
					    uint8_t *o0, uint16_t w)
{
	uint8_t il[3][4] = FOLD_L_3X3(i0, i1, i2);
	uint8_t ir[3][4] = FOLD_R_3X3(i0, i1, i2, w);

	assert(w >= 4 && w % 2 == 0);

	mpix_gbrg8_to_rgb24_3x3(il[0], il[1], il[2], &o0[0]);
	for (size_t i = 0, o = 3; i + 4 <= w; i += 2, o += 6) {
		mpix_bggr8_to_rgb24_3x3(&i0[i + 0], &i1[i + 0], &i2[i + 0], &o0[o + 0]);
		mpix_gbrg8_to_rgb24_3x3(&i0[i + 1], &i1[i + 1], &i2[i + 1], &o0[o + 3]);
	}
	mpix_bggr8_to_rgb24_3x3(ir[0], ir[1], ir[2], &o0[w * 3 - 3]);
}

__attribute__((weak))
void mpix_convert_gbrg8_to_rgb24_3x3(const uint8_t *i0, const uint8_t *i1, const uint8_t *i2,
					    uint8_t *o0, uint16_t w)
{
	uint8_t il[3][4] = FOLD_L_3X3(i0, i1, i2);
	uint8_t ir[3][4] = FOLD_R_3X3(i0, i1, i2, w);

	assert(w >= 4 && w % 2 == 0);

	mpix_bggr8_to_rgb24_3x3(il[0], il[1], il[2], &o0[0]);
	for (size_t i = 0, o = 3; i + 4 <= w; i += 2, o += 6) {
		mpix_gbrg8_to_rgb24_3x3(&i0[i + 0], &i1[i + 0], &i2[i + 0], &o0[o + 0]);
		mpix_bggr8_to_rgb24_3x3(&i0[i + 1], &i1[i + 1], &i2[i + 1], &o0[o + 3]);
	}
	mpix_gbrg8_to_rgb24_3x3(ir[0], ir[1], ir[2], &o0[w * 3 - 3]);
}

typedef void fn_3x3_t(const uint8_t *i0, const uint8_t *i1, const uint8_t *i2, uint8_t *o0,
		      uint16_t width);

static inline void mpix_op_debayer_to_rgb24_3x3(struct mpix_base_op *base,
					      fn_3x3_t *fn0, fn_3x3_t *fn1)
{
	uint16_t prev_line_offset = base->line_offset;
	const uint8_t *i0 = mpix_op_get_input_line(base);
	const uint8_t *i1 = mpix_op_peek_input_line(base);
	const uint8_t *i2 = mpix_op_peek_input_line(base);

	if (prev_line_offset == 0) {
		fn1(i1, i0, i1, mpix_op_get_output_line(base), base->width);
		mpix_op_done(base);
	}

	if (prev_line_offset % 2 == 0) {
		fn0(i0, i1, i2, mpix_op_get_output_line(base), base->width);
		mpix_op_done(base);
	} else {
		fn1(i0, i1, i2, mpix_op_get_output_line(base), base->width);
		mpix_op_done(base);
	}

	if (base->line_offset + 2 == base->height) {
		fn0(i1, i2, i1, mpix_op_get_output_line(base), base->width);
		mpix_op_done(base);

		/* Skip the two lines of lookahead context, now that the conversion is complete */
		mpix_op_get_input_line(base);
		mpix_op_get_input_line(base);
	}
}

static void mpix_op_srggb8_to_rgb24_3x3(struct mpix_base_op *base)
{
	mpix_op_debayer_to_rgb24_3x3(base, &mpix_convert_rggb8_to_rgb24_3x3,
				   &mpix_convert_gbrg8_to_rgb24_3x3);
}
MPIX_REGISTER_DEBAYER_OP(srggb8_3x3, mpix_op_srggb8_to_rgb24_3x3, SRGGB8, 3);

static void mpix_op_sgbrg8_to_rgb24_3x3(struct mpix_base_op *base)
{
	mpix_op_debayer_to_rgb24_3x3(base, &mpix_convert_gbrg8_to_rgb24_3x3,
				   &mpix_convert_rggb8_to_rgb24_3x3);
}
MPIX_REGISTER_DEBAYER_OP(sgbrg8_3x3, mpix_op_sgbrg8_to_rgb24_3x3, SGBRG8, 3);

static void mpix_op_sbggr8_to_rgb24_3x3(struct mpix_base_op *base)
{
	mpix_op_debayer_to_rgb24_3x3(base, &mpix_convert_bggr8_to_rgb24_3x3,
				   &mpix_convert_grbg8_to_rgb24_3x3);
}
MPIX_REGISTER_DEBAYER_OP(sbggr8_3x3, mpix_op_sbggr8_to_rgb24_3x3, SBGGR8, 3);
MPIX_REGISTER_DEBAYER_OP(bggr8_3x3, mpix_op_sbggr8_to_rgb24_3x3, BGGR8, 3);

static void mpix_op_sgrbg8_to_rgb24_3x3(struct mpix_base_op *base)
{
	mpix_op_debayer_to_rgb24_3x3(base, &mpix_convert_grbg8_to_rgb24_3x3,
				   &mpix_convert_bggr8_to_rgb24_3x3);
}
MPIX_REGISTER_DEBAYER_OP(sgrbg8_3x3, mpix_op_sgrbg8_to_rgb24_3x3, SGRBG8, 3);

/* 2x2 debayer */

static inline void mpix_rggb8_to_rgb24_2x2(uint8_t r0, uint8_t g0, uint8_t g1, uint8_t b0,
					   uint8_t dst[3])
{
	dst[0] = r0;
	dst[1] = ((uint16_t)g0 + g1) / 2;
	dst[2] = b0;
}

static inline void mpix_gbrg8_to_rgb24_2x2(uint8_t g0, uint8_t b0, uint8_t r0, uint8_t g1,
					   uint8_t dst[3])
{
	dst[0] = r0;
	dst[1] = ((uint16_t)g0 + g1) / 2;
	dst[2] = b0;
}

static inline void mpix_bggr8_to_rgb24_2x2(uint8_t b0, uint8_t g0, uint8_t g1, uint8_t r0,
					   uint8_t dst[3])
{
	dst[0] = r0;
	dst[1] = ((uint16_t)g0 + g1) / 2;
	dst[2] = b0;
}

static inline void mpix_grbg8_to_rgb24_2x2(uint8_t g0, uint8_t r0, uint8_t b0, uint8_t g1,
					   uint8_t dst[3])
{
	dst[0] = r0;
	dst[1] = ((uint16_t)g0 + g1) / 2;
	dst[2] = b0;
}

__attribute__((weak))
void mpix_convert_rggb8_to_rgb24_2x2(const uint8_t *src0, const uint8_t *src1, uint8_t *dst,
					    uint16_t width)
{
	assert(width >= 2 && width % 2 == 0);

	for (size_t w = 0; w + 3 <= width; w += 2, src0 += 2, src1 += 2, dst += 6) {
		mpix_rggb8_to_rgb24_2x2(src0[0], src0[1], src1[0], src1[1], &dst[0]);
		mpix_grbg8_to_rgb24_2x2(src0[1], src0[2], src1[1], src1[2], &dst[3]);
	}
	mpix_rggb8_to_rgb24_2x2(src0[0], src0[1], src1[0], src1[1], &dst[0]);
	mpix_grbg8_to_rgb24_2x2(src0[1], src0[-1], src1[1], src1[-1], &dst[3]);
}

__attribute__((weak))
void mpix_convert_bggr8_to_rgb24_2x2(const uint8_t *src0, const uint8_t *src1, uint8_t *dst,
					    uint16_t width)
{
	assert(width >= 2 && width % 2 == 0);

	for (size_t w = 0; w + 3 <= width; w += 2, src0 += 2, src1 += 2, dst += 6) {
		mpix_bggr8_to_rgb24_2x2(src0[0], src0[1], src1[0], src1[1], &dst[0]);
		mpix_gbrg8_to_rgb24_2x2(src0[1], src0[2], src1[1], src1[2], &dst[3]);
	}
	mpix_bggr8_to_rgb24_2x2(src0[0], src0[1], src1[0], src1[1], &dst[0]);
	mpix_gbrg8_to_rgb24_2x2(src0[1], src0[-1], src1[1], src1[-1], &dst[3]);
}

__attribute__((weak))
void mpix_convert_gbrg8_to_rgb24_2x2(const uint8_t *src0, const uint8_t *src1, uint8_t *dst,
					    uint16_t width)
{
	assert(width >= 2 && width % 2 == 0);

	for (size_t w = 0; w + 3 <= width; w += 2, src0 += 2, src1 += 2, dst += 6) {
		mpix_gbrg8_to_rgb24_2x2(src0[0], src0[1], src1[0], src1[1], &dst[0]);
		mpix_bggr8_to_rgb24_2x2(src0[1], src0[2], src1[1], src1[2], &dst[3]);
	}
	mpix_gbrg8_to_rgb24_2x2(src0[0], src0[1], src1[0], src1[1], &dst[0]);
	mpix_bggr8_to_rgb24_2x2(src0[1], src0[-1], src1[1], src1[-1], &dst[3]);
}

__attribute__((weak))
void mpix_convert_grbg8_to_rgb24_2x2(const uint8_t *src0, const uint8_t *src1, uint8_t *dst,
					    uint16_t width)
{
	assert(width >= 2 && width % 2 == 0);

	for (size_t w = 0; w + 3 <= width; w += 2, src0 += 2, src1 += 2, dst += 6) {
		mpix_grbg8_to_rgb24_2x2(src0[0], src0[1], src1[0], src1[1], &dst[0]);
		mpix_rggb8_to_rgb24_2x2(src0[1], src0[2], src1[1], src1[2], &dst[3]);
	}
	mpix_grbg8_to_rgb24_2x2(src0[0], src0[1], src1[0], src1[1], &dst[0]);
	mpix_rggb8_to_rgb24_2x2(src0[1], src0[-1], src1[1], src1[-1], &dst[3]);
}

typedef void fn_2x2_t(const uint8_t *i0, const uint8_t *i1, uint8_t *o0, uint16_t width);

static inline void mpix_op_debayer_to_rgb24_2x2(struct mpix_base_op *base,
					      fn_2x2_t *fn0, fn_2x2_t *fn1)
{
	uint16_t prev_line_offset = base->line_offset;
	const uint8_t *i0 = mpix_op_get_input_line(base);
	const uint8_t *i1 = mpix_op_peek_input_line(base);

	if (prev_line_offset % 2 == 0) {
		fn0(i0, i1, mpix_op_get_output_line(base), base->width);
		mpix_op_done(base);
	} else {
		fn1(i0, i1, mpix_op_get_output_line(base), base->width);
		mpix_op_done(base);
	}

	if (base->line_offset + 1 == base->height) {
		fn1(i1, i0, mpix_op_get_output_line(base), base->width);
		mpix_op_done(base);

		/* Skip the two lines of lookahead context, now that the conversion is complete */
		mpix_op_get_input_line(base);
	}
}

static void mpix_op_srggb8_to_rgb24_2x2(struct mpix_base_op *base)
{
	mpix_op_debayer_to_rgb24_2x2(base, &mpix_convert_rggb8_to_rgb24_2x2,
					 &mpix_convert_gbrg8_to_rgb24_2x2);
}
MPIX_REGISTER_DEBAYER_OP(srggb8_2x2, mpix_op_srggb8_to_rgb24_2x2, SRGGB8, 2);

static void mpix_op_sgbrg8_to_rgb24_2x2(struct mpix_base_op *base)
{
	mpix_op_debayer_to_rgb24_2x2(base, &mpix_convert_gbrg8_to_rgb24_2x2,
					 &mpix_convert_rggb8_to_rgb24_2x2);
}
MPIX_REGISTER_DEBAYER_OP(sgbrg8_2x2, mpix_op_sgbrg8_to_rgb24_2x2, SGBRG8, 2);

static void mpix_op_sbggr8_to_rgb24_2x2(struct mpix_base_op *base)
{
	mpix_op_debayer_to_rgb24_2x2(base, &mpix_convert_bggr8_to_rgb24_2x2,
					 &mpix_convert_grbg8_to_rgb24_2x2);
}
MPIX_REGISTER_DEBAYER_OP(sbggr8_2x2, mpix_op_sbggr8_to_rgb24_2x2, SBGGR8, 2);
MPIX_REGISTER_DEBAYER_OP(bggr8_2x2, mpix_op_sbggr8_to_rgb24_2x2, BGGR8, 2); /* Zephyr 3.6 compat */

static void mpix_op_sgrbg8_to_rgb24_2x2(struct mpix_base_op *base)
{
	mpix_op_debayer_to_rgb24_2x2(base, &mpix_convert_grbg8_to_rgb24_2x2,
					 &mpix_convert_bggr8_to_rgb24_2x2);
}
MPIX_REGISTER_DEBAYER_OP(sgrbg8_2x2, mpix_op_sgrbg8_to_rgb24_2x2, SGRBG8, 2);

/* 1x1 debayer */

static void mpix_op_debayer_to_rgb24_1x1(struct mpix_base_op *base)
{
	const uint8_t *src = mpix_op_get_input_line(base);
	uint8_t *dst = mpix_op_get_output_line(base);

	for (uint16_t w = 0; w < base->width; w++, src += 1, dst += 3) {
		dst[0] = dst[1] = dst[2] = src[0];
	}

	mpix_op_done(base);
}
MPIX_REGISTER_DEBAYER_OP(srggb8_1x1, mpix_op_debayer_to_rgb24_1x1, SRGGB8, 1);
MPIX_REGISTER_DEBAYER_OP(sbggr8_1x1, mpix_op_debayer_to_rgb24_1x1, SBGGR8, 1);
MPIX_REGISTER_DEBAYER_OP(sgbrg8_1x1, mpix_op_debayer_to_rgb24_1x1, SGBRG8, 1);
MPIX_REGISTER_DEBAYER_OP(sgrbg8_1x1, mpix_op_debayer_to_rgb24_1x1, SGRBG8, 1);

/* High-level API */

static const struct mpix_debayer_op **mpix_debayer_op_list =
	(const struct mpix_debayer_op *[]){MPIX_LIST_DEBAYER_OP};

int mpix_image_debayer(struct mpix_image *img, uint32_t win_sz)
{
	const struct mpix_debayer_op *op = NULL;

	for (size_t i = 0; mpix_debayer_op_list[i] != NULL; i++) {
		const struct mpix_debayer_op *tmp = mpix_debayer_op_list[i];

		if (tmp->base.fourcc_src == img->fourcc &&
		    tmp->base.fourcc_dst == MPIX_FMT_RGB24 &&
		    tmp->base.window_size == win_sz) {
			op = tmp;
			break;
		}
	}
	if (op == NULL) {
		MPIX_ERR("Debayer operation from %s to %s using %ux%u window not found",
			 MPIX_FOURCC_TO_STR(img->fourcc), MPIX_FOURCC_TO_STR(MPIX_FMT_RGB24),
			 win_sz, win_sz);
		return mpix_image_error(img, -ENOSYS);
	}

	return mpix_image_append_uncompressed_op(img, &op->base, sizeof(*op));
}
