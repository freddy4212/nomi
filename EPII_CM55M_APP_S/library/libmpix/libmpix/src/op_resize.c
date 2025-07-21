/* SPDX-License-Identifier: Apache-2.0 */

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <mpix/genlist.h>
#include <mpix/image.h>
#include <mpix/op_resize.h>

static inline void mpix_resize_line(const uint8_t *src_buf, size_t src_width, uint8_t *dst_buf,
				    size_t dst_width, uint8_t bits_per_pixel)
{
	for (size_t dst_w = 0; dst_w < dst_width; dst_w++) {
		size_t src_w = dst_w * src_width / dst_width;
		size_t src_i = src_w * bits_per_pixel / BITS_PER_BYTE;
		size_t dst_i = dst_w * bits_per_pixel / BITS_PER_BYTE;

		memmove(&dst_buf[dst_i], &src_buf[src_i], bits_per_pixel / BITS_PER_BYTE);
	}
}

static inline void mpix_resize_frame(const uint8_t *src_buf, size_t src_width, size_t src_height,
				     uint8_t *dst_buf, size_t dst_width, size_t dst_height,
				     uint8_t bits_per_pixel)
{
	for (size_t dst_h = 0; dst_h < dst_height; dst_h++) {
		size_t src_h = dst_h * src_height / dst_height;
		size_t src_i = src_h * src_width * bits_per_pixel / BITS_PER_BYTE;
		size_t dst_i = dst_h * dst_width * bits_per_pixel / BITS_PER_BYTE;

		mpix_resize_line(&src_buf[src_i], src_width, &dst_buf[dst_i], dst_width,
				 bits_per_pixel);
	}
}

__attribute__((weak))
void mpix_resize_frame_raw24(const uint8_t *src_buf, size_t src_width, size_t src_height,
			     uint8_t *dst_buf, size_t dst_width, size_t dst_height)
{
	mpix_resize_frame(src_buf, src_width, src_height, dst_buf, dst_width, dst_height, 24);
}

__attribute__((weak))
void mpix_resize_frame_raw16(const uint8_t *src_buf, size_t src_width, size_t src_height,
				    uint8_t *dst_buf, size_t dst_width, size_t dst_height)
{
	mpix_resize_frame(src_buf, src_width, src_height, dst_buf, dst_width, dst_height, 16);
}

__attribute__((weak))
void mpix_resize_frame_raw8(const uint8_t *src_buf, size_t src_width, size_t src_height,
				   uint8_t *dst_buf, size_t dst_width, size_t dst_height)
{
	mpix_resize_frame(src_buf, src_width, src_height, dst_buf, dst_width, dst_height, 8);
}

static inline void mpix_resize_op(struct mpix_base_op *base, uint8_t bits_per_pixel)
{
	struct mpix_base_op *next = base->next;
	uint16_t prev_offset = (base->line_offset + 1) * next->height / base->height;
	const uint8_t *line_in = mpix_op_get_input_line(base);
	uint16_t next_offset = (base->line_offset + 1) * next->height / base->height;

	for (uint16_t i = 0; prev_offset + i < next_offset; i++) {
		mpix_resize_line(line_in, base->width, mpix_op_get_output_line(base), next->width,
				 bits_per_pixel);
		mpix_op_done(base);
	}
}

__attribute__((weak))
void mpix_resize_op_raw24(struct mpix_base_op *base)
{
	mpix_resize_op(base, 24);
}
MPIX_REGISTER_RESIZE_OP(rgb24, mpix_resize_op_raw24, SUBSAMPLING, RGB24);
MPIX_REGISTER_RESIZE_OP(yuv24, mpix_resize_op_raw24, SUBSAMPLING, YUV24);

__attribute__((weak))
void mpix_resize_op_raw16(struct mpix_base_op *base)
{
	mpix_resize_op(base, 16);
}
MPIX_REGISTER_RESIZE_OP(rgb565, mpix_resize_op_raw16, SUBSAMPLING, RGB565);
MPIX_REGISTER_RESIZE_OP(rgb565x, mpix_resize_op_raw16, SUBSAMPLING, RGB565X);

__attribute__((weak))
void mpix_resize_op_raw8(struct mpix_base_op *base)
{
	mpix_resize_op(base, 8);
}
MPIX_REGISTER_RESIZE_OP(grey, mpix_resize_op_raw8, SUBSAMPLING, GREY);
MPIX_REGISTER_RESIZE_OP(rgb332, mpix_resize_op_raw8, SUBSAMPLING, RGB332);

static const struct mpix_resize_op **mpix_resize_op_list =
	(const struct mpix_resize_op *[]){MPIX_LIST_RESIZE_OP};

int mpix_image_resize(struct mpix_image *img, enum mpix_resize_type type,
		      uint16_t width, uint16_t height)
{
	const struct mpix_resize_op *op = NULL;
	int ret;

	op = mpix_op_by_format(mpix_resize_op_list, img->fourcc, img->fourcc);
	if (op == NULL) {
		MPIX_ERR("Resize operation for %s not found", MPIX_FOURCC_TO_STR(img->fourcc));
		return mpix_image_error(img, -ENOSYS);
	}

	ret = mpix_image_append_uncompressed_op(img, &op->base, sizeof(*op));
	img->width = width;
	img->height = height;
	return ret;
}
