/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>

#include <mpix/formats.h>
#include <mpix/genlist.h>
#include <mpix/image.h>
#include <mpix/op_jpeg.h>
#include <mpix/utils.h>

#define MPIX_JPEG_OP_INDEX  0x00 /* 00xxxxxx */
#define MPIX_JPEG_OP_DIFF   0x40 /* 01xxxxxx */
#define MPIX_JPEG_OP_LUMA   0x80 /* 10xxxxxx */
#define MPIX_JPEG_OP_RUN    0xc0 /* 11xxxxxx */
#define MPIX_JPEG_OP_RGB    0xfe /* 11111110 */
#define MPIX_JPEG_OP_RGBA   0xff /* 11111111 */

#define MPIX_JPEG_PUT_U8(u) ({                                                                     \
	if (o + 1 >= dst_sz) {                                                                     \
		return o;                                                                          \
	}                                                                                          \
	dst[o++] = (u);                                                                            \
})

#define MPIX_JPEG_PUT_U32(u) ({                                                                    \
	if (o + 4 >= dst_sz) {                                                                     \
		return o;                                                                          \
	}                                                                                          \
	dst[o++] = (u) >> 24;                                                                      \
	dst[o++] = (u) >> 16;                                                                      \
	dst[o++] = (u) >> 8;                                                                       \
	dst[o++] = (u) >> 0;                                                                       \
})

static void mpix_jpeg_yuyv_to_y8x8(const uint8_t *src[8], uint16_t offset, uint8_t block[64])
{
	for (int h = 0; h < 8; h++) {
		const uint8_t *row = src[h] + offset;

		for (int16_t w = 0; w < 8; w++, row += 2, block++) {
			*block = *row;
		}
	}
}

/*
 * YUYV is YUV with 4:2:2 chroma horizontal sub-sampling. To convert it to YUV 4:2:0 chroma
 * horizontal and vertical sub-sampling, it is necessary to average two rows of chroma.
 */
static void mpix_jpeg_yuyv_to_uv8x8(const uint8_t *src[8], uint16_t offset, uint8_t block[64])
{
	for (int h = 0; h < 16; h += 2) {
		const uint8_t *row0 = src[h + 0] + offset;
		const uint8_t *row1 = src[h + 1] + offset;

		for (int w = 0; w + 2 <= 16; w += 2, row0 += 4, row1 += 4, block++) {
			*block = (row0[1] + row1[1]) / 2;
		}
	}
}

static inline size_t mpix_jpeg_encode_block(struct mpix_jpeg_op *op, uint8_t block[64],
					    uint8_t *dst, size_t dst_sz)
{
	/* TODO insert JPEG input block to JPEG output here */
	return 0;
}

void mpix_jpeg_encode_yuyv_op(struct mpix_base_op *base)
{
	struct mpix_jpeg_op *op = (void *)base;
	uint8_t block[64];
	const uint8_t *src[16];
	uint8_t *dst;
	size_t dst_sz;
	size_t o = 0;

	for (size_t i = 0; i < ARRAY_SIZE(src); i++) {
		src[i] = mpix_op_get_input_line(base);
	}

	dst = mpix_op_peek_output(base, &dst_sz);

	/* 0   8   16  24  32  40  48  56  64  72  80  88  92
	 * '   '   '   '   '   '   '   '   '   '   '   '   '
	 * #=======#=======#=======#=======#=======#=======#  \
	 * #   |   #   |   #   |   #   |   #   |   #   |   #  | Scan tiles of 4 blocks of
	 * #---+---#---+---#---+---#---+---#---+---#---+---#  | 8x8 pixels each over the
	 * #   |   #   |   #   |   #   |   #   |   #   |   #  | full width of the line.
	 * #=======#=======#=======#=======#=======#=======#  /
	 * |   |   |   |   |   |   |   |   |   |   |   |   |
	 * +---+---+---+---+---+---+---+---+---+---+---+---+
	 * :   :   :   :   :   :   :   :   :   :   :   :   :
	 */
	for (uint16_t w = 0; w + 16 <= base->width; w += 16) {
		/* top left grayscale */
		mpix_jpeg_yuyv_to_y8x8(&src[0], w + 0, block);
		o += mpix_jpeg_encode_block(op, block, dst + o, dst_sz - o);

		/* top right grayscale */
		mpix_jpeg_yuyv_to_y8x8(&src[0], w + 8, block);
		o += mpix_jpeg_encode_block(op, block, dst + o, dst_sz - o);

		/* bottom left grayscale */
		mpix_jpeg_yuyv_to_y8x8(&src[8], w + 0, block);
		o += mpix_jpeg_encode_block(op, block, dst + o, dst_sz - o);

		/* bottom right grayscale */
		mpix_jpeg_yuyv_to_y8x8(&src[8], w + 8, block);
		o += mpix_jpeg_encode_block(op, block, dst + o, dst_sz - o);

		/* blueness */
		mpix_jpeg_yuyv_to_uv8x8(&src[8], w + 0, block);
		o += mpix_jpeg_encode_block(op, block, dst + o, dst_sz - o);

		/* redness */
		mpix_jpeg_yuyv_to_uv8x8(&src[8], w + 2, block);
		o += mpix_jpeg_encode_block(op, block, dst + o, dst_sz - o);

		/* Shift to the next 16x16 block (tile of four 8x8 blocks) towards the right */
		for (size_t i = 0; i < ARRAY_SIZE(src); i++) {
			src[i] += 16 * 2;
		}
	}
}
MPIX_REGISTER_JPEG_OP(encode_yuyv, mpix_jpeg_encode_yuyv_op, YUYV, JPEG);

static const struct mpix_jpeg_op **mpix_jpeg_op_list =
	(const struct mpix_jpeg_op *[]){MPIX_LIST_JPEG_OP};

int mpix_image_jpeg_encode(struct mpix_image *img)
{
	struct mpix_jpeg_op *op = NULL;

	op = mpix_op_by_format(mpix_jpeg_op_list, img->fourcc, MPIX_FMT_JPEG);
	if (op == NULL) {
		MPIX_ERR("Conversion operation from %s to %s not found",
			 MPIX_FOURCC_TO_STR(img->fourcc), MPIX_FOURCC_TO_STR(MPIX_FMT_JPEG));
		return mpix_image_error(img, -ENOSYS);
	}

	return mpix_image_append_uncompressed_op(img, &op->base, sizeof(*op));
}
