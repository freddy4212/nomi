/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_op_convert_h mpix/op_convert.h
 * @brief Low-level pixel format conversion operations
 * @{
 */
#ifndef MPIX_OP_CONVERT_H
#define MPIX_OP_CONVERT_H

#include <stdlib.h>
#include <stdint.h>

#include <mpix/image.h>

/**
 * @brief Conversion operation
 * @private
 */
struct mpix_convert_op {
	/** Fields common to all operations. */
	struct mpix_base_op base;
	/** Line conversion function repeated over the entire image */
	void (*convert_fn)(const uint8_t *src, uint8_t *dst, uint16_t width);
};

/**
 * @brief Define a new format conversion operation.
 *
 * @param id Short identifier to differentiate operations of the same type.
 * @param fn Function converting one input line.
 * @param format_in The input format for that operation.
 * @param format_out The Output format for that operation.
 */
#define MPIX_REGISTER_CONVERT_OP(id, fn, format_in, format_out)                                    \
	const struct mpix_convert_op mpix_convert_op_##id = {                                      \
		.base.name = ("convert_" #id),                                                     \
		.base.fourcc_src = (MPIX_FMT_##format_in),                                         \
		.base.fourcc_dst = (MPIX_FMT_##format_out),                                        \
		.base.window_size = 1,                                                             \
		.base.run = (mpix_convert_op),                                                     \
		.convert_fn = (fn),                                                                \
	}

/**
 * @brief Get the luminance (luma channel) of an RGB24 pixel.
 *
 * @param rgb24 Pointer to an RGB24 pixel: red, green, blue channels.
 */
uint8_t mpix_rgb24_get_luma_bt709(const uint8_t rgb24[3]);

/**
 * @brief Convert a line of pixel data from RGB24 to RGB24 (null conversion).
 *
 * See @ref mpix_formats_h for the definition of the input and output formats.
 *
 * You only need to call this function to work directly on raw buffers.
 * See @ref mpix_image_convert for converting between formats.
 *
 * @param src Buffer of the input line in the format, @c XXX in @c mpix_convert_XXX_to_YYY().
 * @param dst Buffer of the output line in the format, @c YYY in @c mpix_convert_XXX_to_YYY().
 * @param width Width of the lines in number of pixels.
 */
void mpix_convert_rgb24_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB332 to RGB24.
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb332_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB24 to RGB332 little-endian.
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb24_to_rgb332(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB565 little-endian to RGB24.
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb565le_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB565 big-endian to RGB24.
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb565be_to_rgb24(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB24 to RGB565 little-endian.
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb24_to_rgb565le(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB24 to RGB565 big-endian.
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb24_to_rgb565be(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from YUYV to RGB24 (BT.709 coefficients).
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_yuyv_to_rgb24_bt709(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB24 to YUYV (BT.709 coefficients).
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb24_to_yuyv_bt709(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB24 to YUV24 (BT.709 coefficients).
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb24_to_yuv24_bt709(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from YUV24 to RGB24 (BT.709 coefficients).
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_yuv24_to_rgb24_bt709(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from YUYV to YUV24
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_yuyv_to_yuv24(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from YUV24 to YUYV
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_yuv24_to_yuyv(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from Y8 to RGB24
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_y8_to_rgb24_bt709(const uint8_t *src, uint8_t *dst, uint16_t width);
/**
 * @brief Convert a line of pixel data from RGB24 to Y8
 * @copydetails mpix_convert_rgb24_to_rgb24()
 */
void mpix_convert_rgb24_to_y8_bt709(const uint8_t *src, uint8_t *dst, uint16_t width);

/**
 * Helper to simplify the implementation of an image format conversion operation.
 *
 * @internal
 *
 * @param base Base operation type, casted to @ref mpix_convert_op.
 */
void mpix_convert_op(struct mpix_base_op *base);

#endif /** @} */
