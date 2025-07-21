/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_op_resize_h mpix/op_resize.h
 * @brief Low-level resizing operations
 * @{
 */
#ifndef MPIX_OP_RESIZE_H
#define MPIX_OP_RESIZE_H

#include <stdint.h>

#include <mpix/op.h>

/**
 * Available scaling strategies to use while resizing an image.
 */
enum mpix_resize_type {
	/** Pick a single input pixel for every output pixel, faster but lower quality */
	MPIX_RESIZE_SUBSAMPLING,
	/** Perform pixel binning, good performance and quality but sizes must be x2 or /2 */
	MPIX_RESIZE_BINNING,
};

/**
 * Image resizing operation.
 * @internal
 */
struct mpix_resize_op {
	/** Fields common to all operations. */
	struct mpix_base_op base;
	/** The resize strategy to use */
	enum mpix_resize_type type;
};

/**
 * @brief Define a format conversion operation.
 *
 * Invoking this macro suffices for @ref mpix_image_convert() to include the extra format.
 *
 * @param id Short identifier to differentiate operations of the same type.
 * @param fn Function converting one input line.
 * @param t The strategy to use from @ref mpix_resize_type
 * @param fmt The pixel format of the data resized.
 */
#define MPIX_REGISTER_RESIZE_OP(id, fn, t, fmt)                                                    \
	const struct mpix_resize_op mpix_resize_op_##id = {                                        \
		.base.name = "resize_" #id,                                                        \
		.base.fourcc_src = MPIX_FMT_##fmt,                                                 \
		.base.fourcc_dst = MPIX_FMT_##fmt,                                                 \
		.base.window_size = 1,                                                             \
		.base.run = fn,                                                                    \
		.type = MPIX_RESIZE_##t,                                                           \
	}

/**
 * @brief Resize an 24-bit per pixel frame by subsampling the pixels horizontally/vertically.
 *
 * @param src_buf Input buffer to resize
 * @param src_width Width of the input in number of pixels.
 * @param src_height Height of the input in number of pixels.
 * @param dst_buf Output buffer in which the stretched/compressed is stored.
 * @param dst_width Width of the output in number of pixels.
 * @param dst_height Height of the output in number of pixels.
 */
void mpix_resize_frame_raw24(const uint8_t *src_buf, size_t src_width, size_t src_height,
			     uint8_t *dst_buf, size_t dst_width, size_t dst_height);
/**
 * @brief Resize an 16-bit per pixel frame by subsampling the pixels horizontally/vertically.
 * @copydetails mpix_resize_frame_raw24()
 */
void mpix_resize_frame_raw16(const uint8_t *src_buf, size_t src_width, size_t src_height,
			     uint8_t *dst_buf, size_t dst_width, size_t dst_height);
/**
 * @brief Resize an 8-bit per pixel frame by subsampling the pixels horizontally/vertically.
 * @copydetails mpix_resize_frame_raw24()
 */
void mpix_resize_frame_raw8(const uint8_t *src_buf, size_t src_width, size_t src_height,
			    uint8_t *dst_buf, size_t dst_width, size_t dst_height);

#endif /** @} */
