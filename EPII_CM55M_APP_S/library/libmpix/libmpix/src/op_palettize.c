/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <string.h>
#include <errno.h>

#include <mpix/genlist.h>
#include <mpix/sample.h>
#include <mpix/image.h>
#include <mpix/utils.h>
#include <mpix/op_palettize.h>

static inline uint8_t mpix_rgb24_to_palette(const uint8_t rgb[3],
					    const struct mpix_palette *palette);

static uint8_t mpix_palette_bit_depth(uint32_t fourcc)
{
	char *str = MPIX_FOURCC_TO_STR(fourcc);

	if (strncmp(str, "PLT", 3) != 0 || !IN_RANGE(str[3], '0', '9')) {
		return 0;
	}

	return str[3] - '0';
}

void mpix_image_from_palette(struct mpix_image *img, struct mpix_palette *palette)
{
	uint16_t num_colors = 1 << mpix_palette_bit_depth(palette->fourcc);

	assert(num_colors > 0);

	mpix_image_from_buf(img, palette->colors, num_colors * 3, num_colors, 1, MPIX_FMT_RGB24);
}

int mpix_image_to_palette(struct mpix_image *img, struct mpix_palette *palette)
{
	uint16_t num_colors = 1 << mpix_palette_bit_depth(palette->fourcc);

	assert(num_colors > 0);

	return mpix_image_to_buf(img, palette->colors, num_colors * 3);
}

uint8_t mpix_palette_depth(const struct mpix_palette *palette)
{
	assert(memcmp(MPIX_FOURCC_TO_STR(palette->fourcc), "PLT", 3) == 0);
	assert(IN_RANGE(MPIX_FOURCC_TO_STR(palette->fourcc)[3], '1', '8'));

	return MPIX_FOURCC_TO_STR(palette->fourcc)[3] - '0';
}

/*
 * This is an implementation of K-Mean algorithm to estimate the color palette that best matches
 * an image.
 */
int mpix_image_optimize_palette(struct mpix_image *img, struct mpix_palette *palette,
				uint16_t num_samples)
{
	size_t colors_nb = 1u << mpix_palette_depth(palette);
	uint32_t *sums;
	const size_t sums_sz = colors_nb * sizeof(*sums) * 3;
	uint16_t *nums;
	const size_t nums_sz = colors_nb * sizeof(*nums);
	uint8_t rgb[3];
	int ret;

	sums = mpix_port_alloc(sums_sz);
	if (sums == NULL) {
		MPIX_ERR("Failed to allocate the sum array");
		return mpix_image_error(img, -ENOMEM);
	}
	memset(sums, 0x00, sums_sz);

	nums = mpix_port_alloc(nums_sz);
	if (nums == NULL) {
		MPIX_ERR("Failed to allocate the num array");
		mpix_port_free(sums);
		return mpix_image_error(img, -ENOMEM);
	}
	memset(nums, 0x00, nums_sz);

	/* Take samples from the input image, find which palette point they belong to, and
	 * accumulate the colors to get an average color.
	 */
	for (uint16_t i = 0; i < num_samples; i++) {
		uint8_t idx;

		ret = mpix_sample_random_rgb(img->buffer, img->width, img->height, img->fourcc,
					     rgb);
		if (ret != 0) {
			return ret;
		}

		idx = mpix_rgb24_to_palette(rgb, palette);

		sums[idx * 3 + 0] += rgb[0];
		sums[idx * 3 + 1] += rgb[1];
		sums[idx * 3 + 2] += rgb[2];
		nums[idx]++;
	}

	/* Average each sum to generate the new palette, with now slightly adjusted colors to
	 * better fit the input image. Repeating the operation allows to improve the accuracy.
	 */
	for (size_t idx = 0; idx < colors_nb; idx++) {
		if (nums[idx] == 0) {
			/* If no value was detected, shift the colors a bit */
			palette->colors[idx * 3 + 0] += 0x10;
			palette->colors[idx * 3 + 1] += 0x10;
			palette->colors[idx * 3 + 2] += 0x10;
		} else {
			/* If there are matches, re-compute a better value */
			palette->colors[idx * 3 + 0] = sums[idx * 3 + 0] / nums[idx];
			palette->colors[idx * 3 + 1] = sums[idx * 3 + 1] / nums[idx];
			palette->colors[idx * 3 + 2] = sums[idx * 3 + 2] / nums[idx];
		}
	}

	mpix_port_free(sums);
	mpix_port_free(nums);

	return 0;
}

void mpix_palettize_op(struct mpix_base_op *base)
{
	struct mpix_palette_op *op = (void *)base;
	const uint8_t *line_in = mpix_op_get_input_line(base);
	uint8_t *line_out = mpix_op_get_output_line(base);

	op->palette_fn(line_in, line_out, base->width, op->palette);
	mpix_op_done(base);
}

/*
 * The 3D (R, G, B) distance between two points is given by:
 *
 * 	sqrt((r1 - r0)^2 + (g1 - g0)^2 + (b1 - b0)^2)
 *
 * But if A > B then sqrt(A) > sqrt(B), so no need to compute the square root.
 * The square of the distances are computed instead.
 */
static inline uint32_t mpix_rgb_square_distance(const uint8_t rgb0[3], const uint8_t rgb1[3])
{
	int16_t r_dist = (int16_t)rgb1[0] - (int16_t)rgb0[0];
	int16_t g_dist = (int16_t)rgb1[1] - (int16_t)rgb0[1];
	int16_t b_dist = (int16_t)rgb1[2] - (int16_t)rgb0[2];

	return r_dist * r_dist + g_dist * g_dist + b_dist + b_dist;
}

static inline uint8_t mpix_rgb24_to_palette(const uint8_t rgb[3],
					    const struct mpix_palette *palette)
{
	size_t colors_nb = 1u << mpix_palette_depth(palette);
	uint8_t best_color[3];
	uint32_t best_square_distance = UINT32_MAX;
	uint8_t idx = 0;

	for (size_t i = 0; i < colors_nb; i++) {
		uint8_t *color = &palette->colors[i * 3];
		uint32_t square_distance = mpix_rgb_square_distance(color, rgb);

		if (square_distance < best_square_distance) {
			best_square_distance = square_distance;
			memcpy(best_color, color, sizeof(best_color));
			idx = i;
		}
	}

	return idx;
}

__attribute__ ((weak))
void mpix_convert_rgb24_to_palette1(const uint8_t *src, uint8_t *dst, uint16_t width,
				    const struct mpix_palette *palette)
{
	assert(width % 8 == 0);

	for (uint16_t w = 0; w + 8 <= width; w += 8, src += 8 * 3, dst += 1) {
		*dst = mpix_rgb24_to_palette(&src[0], palette) << 7;
		*dst |= mpix_rgb24_to_palette(&src[3], palette) << 6;
		*dst |= mpix_rgb24_to_palette(&src[6], palette) << 5;
		*dst |= mpix_rgb24_to_palette(&src[9], palette) << 4;
		*dst |= mpix_rgb24_to_palette(&src[12], palette) << 3;
		*dst |= mpix_rgb24_to_palette(&src[15], palette) << 2;
		*dst |= mpix_rgb24_to_palette(&src[18], palette) << 1;
		*dst |= mpix_rgb24_to_palette(&src[21], palette) << 0;
	}
}
MPIX_REGISTER_PALETTE_OP(rgb24_palette1, mpix_convert_rgb24_to_palette1, RGB24, PALETTE1);

__attribute__ ((weak))
void mpix_convert_palette1_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width,
				    const struct mpix_palette *palette)
{
	assert(width % 8 == 0);

	for (uint16_t w = 0; w + 8 <= width; w += 8, src += 1, dst += 8 * 3) {
		memcpy(&dst[0], &palette->colors[((*src >> 7) & 0x1) * 3], 3);
		memcpy(&dst[3], &palette->colors[((*src >> 6) & 0x1) * 3], 3);
		memcpy(&dst[6], &palette->colors[((*src >> 5) & 0x1) * 3], 3);
		memcpy(&dst[9], &palette->colors[((*src >> 4) & 0x1) * 3], 3);
		memcpy(&dst[12], &palette->colors[((*src >> 3) & 0x1) * 3], 3);
		memcpy(&dst[15], &palette->colors[((*src >> 2) & 0x1) * 3], 3);
		memcpy(&dst[18], &palette->colors[((*src >> 1) & 0x1) * 3], 3);
		memcpy(&dst[21], &palette->colors[((*src >> 0) & 0x1) * 3], 3);
	}
}
MPIX_REGISTER_PALETTE_OP(palette1_rgb24, mpix_convert_palette1_to_rgb24, PALETTE1, RGB24);

__attribute__ ((weak))
void mpix_convert_rgb24_to_palette2(const uint8_t *src, uint8_t *dst, uint16_t width,
				    const struct mpix_palette *palette)
{
	assert(width % 4 == 0);

	for (uint16_t w = 0; w + 4 <= width; w += 4, src += 4 * 3, dst += 1) {
		*dst = mpix_rgb24_to_palette(&src[0], palette) << 6;
		*dst |= mpix_rgb24_to_palette(&src[3], palette) << 4;
		*dst |= mpix_rgb24_to_palette(&src[6], palette) << 2;
		*dst |= mpix_rgb24_to_palette(&src[9], palette) << 0;
	}
}
MPIX_REGISTER_PALETTE_OP(rgb24_palette2, mpix_convert_rgb24_to_palette2, RGB24, PALETTE2);

__attribute__ ((weak))
void mpix_convert_palette2_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width,
				    const struct mpix_palette *palette)
{
	assert(width % 4 == 0);

	for (uint16_t w = 0; w + 4 <= width; w += 4, src += 1, dst += 4 * 3) {
		memcpy(&dst[0], &palette->colors[((*src >> 6) & 0x3) * 3], 3);
		memcpy(&dst[3], &palette->colors[((*src >> 4) & 0x3) * 3], 3);
		memcpy(&dst[6], &palette->colors[((*src >> 2) & 0x3) * 3], 3);
		memcpy(&dst[9], &palette->colors[((*src >> 0) & 0x3) * 3], 3);
	}
}
MPIX_REGISTER_PALETTE_OP(palette2_rgb24, mpix_convert_palette2_to_rgb24, PALETTE2, RGB24);

__attribute__ ((weak))
void mpix_convert_rgb24_to_palette4(const uint8_t *src, uint8_t *dst, uint16_t width,
				    const struct mpix_palette *palette)
{
	assert(width % 2 == 0);

	for (uint16_t w = 0; w + 2 <= width; w += 2, src += 2 * 3, dst += 1) {
		*dst = mpix_rgb24_to_palette(&src[0], palette) << 4;
		*dst |= mpix_rgb24_to_palette(&src[3], palette) << 0;
	}
}
MPIX_REGISTER_PALETTE_OP(rgb24_palette3, mpix_convert_rgb24_to_palette4, RGB24, PALETTE3);
MPIX_REGISTER_PALETTE_OP(rgb24_palette4, mpix_convert_rgb24_to_palette4, RGB24, PALETTE4);

__attribute__ ((weak))
void mpix_convert_palette4_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width,
				    const struct mpix_palette *palette)
{
	assert(width % 2 == 0);

	for (uint16_t w = 0; w + 2 <= width; w += 2, src += 1, dst += 2 * 3) {
		memcpy(&dst[0], &palette->colors[((*src >> 4) & 0xf) * 3], 3);
		memcpy(&dst[3], &palette->colors[((*src >> 0) & 0xf) * 3], 3);
	}
}
MPIX_REGISTER_PALETTE_OP(palette3_rgb24, mpix_convert_palette4_to_rgb24, PALETTE3, RGB24);
MPIX_REGISTER_PALETTE_OP(palette4_rgb24, mpix_convert_palette4_to_rgb24, PALETTE4, RGB24);

__attribute__ ((weak))
void mpix_convert_rgb24_to_palette8(const uint8_t *src, uint8_t *dst, uint16_t width,
				    const struct mpix_palette *palette)
{
	for (uint16_t w = 0; w < width; w += 1, src += 3, dst += 1) {
		*dst = mpix_rgb24_to_palette(src, palette);
	}
}
MPIX_REGISTER_PALETTE_OP(rgb24_palette5, mpix_convert_rgb24_to_palette8, RGB24, PALETTE5);
MPIX_REGISTER_PALETTE_OP(rgb24_palette6, mpix_convert_rgb24_to_palette8, RGB24, PALETTE6);
MPIX_REGISTER_PALETTE_OP(rgb24_palette7, mpix_convert_rgb24_to_palette8, RGB24, PALETTE7);
MPIX_REGISTER_PALETTE_OP(rgb24_palette8, mpix_convert_rgb24_to_palette8, RGB24, PALETTE8);

__attribute__ ((weak))
void mpix_convert_palette8_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width,
				    const struct mpix_palette *palette)
{
	for (uint16_t w = 0; w < width; w += 1, src += 1, dst += 3) {
		memcpy(dst, &palette->colors[*src * 3], 3);
	}
}
MPIX_REGISTER_PALETTE_OP(palette5_rgb24, mpix_convert_palette8_to_rgb24, PALETTE5, RGB24);
MPIX_REGISTER_PALETTE_OP(palette6_rgb24, mpix_convert_palette8_to_rgb24, PALETTE6, RGB24);
MPIX_REGISTER_PALETTE_OP(palette7_rgb24, mpix_convert_palette8_to_rgb24, PALETTE7, RGB24);
MPIX_REGISTER_PALETTE_OP(palette8_rgb24, mpix_convert_palette8_to_rgb24, PALETTE8, RGB24);

static const struct mpix_palette_op **mpix_palette_op_list =
	(const struct mpix_palette_op *[]){MPIX_LIST_PALETTE_OP};

static int mpix_image_append_palette_op(struct mpix_image *img, const struct mpix_palette_op *op,
					struct mpix_palette *palette)
{
	struct mpix_palette_op *new;
	int ret;

	ret = mpix_image_append_uncompressed_op(img, &op->base, sizeof(*op));
	if (ret != 0) {
		return ret;
	}

	new = (struct mpix_palette_op *)img->ops.last;
	new->palette = palette;

	return 0;
}

int mpix_image_palettize(struct mpix_image *img, struct mpix_palette *palette)
{
	const struct mpix_palette_op *op = NULL;
	int ret;

	ret = mpix_image_convert(img, MPIX_FMT_RGB24);
	if (ret != 0) {
		return ret;
	}

	op = mpix_op_by_format(mpix_palette_op_list, img->fourcc, palette->fourcc);
	if (op == NULL) {
		MPIX_ERR("Conversion operation from %s to %s not found",
			 MPIX_FOURCC_TO_STR(img->fourcc), MPIX_FOURCC_TO_STR(palette->fourcc));
		return mpix_image_error(img, -ENOSYS);
	}

	return mpix_image_append_palette_op(img, op, palette);
}

int mpix_image_depalettize(struct mpix_image *img, struct mpix_palette *palette)
{
	const struct mpix_palette_op *op = NULL;

	if (img->fourcc != palette->fourcc) {
		MPIX_ERR("Image format is not matching the palette format");
	}

	op = mpix_op_by_format(mpix_palette_op_list, img->fourcc, MPIX_FMT_RGB24);
	if (op == NULL) {
		MPIX_ERR("Conversion operation from %s to %s not found",
			 MPIX_FOURCC_TO_STR(img->fourcc), MPIX_FOURCC_TO_STR(palette->fourcc));
		return mpix_image_error(img, -ENOSYS);
	}

	return mpix_image_append_palette_op(img, op, palette);
}
