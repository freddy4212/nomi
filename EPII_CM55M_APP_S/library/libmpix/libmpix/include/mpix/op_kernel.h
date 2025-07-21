/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_op_kernel_h mpix/op_kernel.h
 * @brief Low-level image kernel operations
 * @{
 */
#ifndef MPIX_OP_KERNEL_H
#define MPIX_OP_KERNEL_H

#include <stdint.h>
#include <stdlib.h>

#include <mpix/op.h>

/**
 * Available kernel operations to apply to the image.
 */
enum mpix_kernel_type {
	/** Identity kernel: no change, the input is the same as the output */
	MPIX_KERNEL_IDENTITY,
	/** Edge detection kernel: keep only an outline of the edges */
	MPIX_KERNEL_EDGE_DETECT,
	/** Gaussian blur kernel: apply a blur onto an image following a Gaussian curve */
	MPIX_KERNEL_GAUSSIAN_BLUR,
	/** Sharpen kernel: accentuate the edges, making the image look less blurry */
	MPIX_KERNEL_SHARPEN,
	/** Denoise kernel: remove the parasitic image noise using the local median value */
	MPIX_KERNEL_DENOISE,
};

/**
 * Kernel-based operation
 * @internal
 */
struct mpix_kernel_op {
	/** Fields common to all operations. */
	struct mpix_base_op base;
	/** Type of kernel operation */
	enum mpix_kernel_type type;
	/** Pointer to a function performing the transformation on one image tile. */
	void (*kernel_fn)(const uint8_t *src[], uint8_t *dst, uint16_t w);
};

/**
 * @brief Define a new 5x5 kernel conversion operation.
 *
 * @param id Short identifier to differentiate operations of the same category.
 * @param fn Function converting 5 input lines into 1 output line.
 * @param t Kernel operation type from @ref mpix_kernel_type
 * @param fmt The input format for that operation.
 */
#define MPIX_REGISTER_KERNEL_5X5_OP(id, fn, t, fmt)                                                \
	const struct mpix_kernel_op mpix_kernel_5x5_op_##id = {                                    \
		.base.name = ("kernel_5x5_" #id),                                                  \
		.base.fourcc_src = (MPIX_FMT_##fmt),                                               \
		.base.fourcc_dst = (MPIX_FMT_##fmt),                                               \
		.base.window_size = 5,                                                             \
		.base.run = mpix_kernel_5x5_op,                                                    \
		.kernel_fn = (fn),                                                                 \
		.type = (MPIX_KERNEL_##t),                                                         \
	}

/**
 * @brief Define a new 3x3 kernel conversion operation.
 *
 * @param id Short identifier to differentiate operations of the same type.
 * @param fn Function converting 3 input lines into 1 output line.
 * @param t Kernel operation type from @ref mpix_kernel_type
 * @param fmt The input format for that operation.
 */
#define MPIX_REGISTER_KERNEL_3X3_OP(id, fn, t, fmt)                                                \
	const struct mpix_kernel_op mpix_kernel_3x3_op_##id = {                                    \
		.base.name = ("kernel_3x3_" #id),                                                  \
		.base.fourcc_src = (MPIX_FMT_##fmt),                                                  \
		.base.fourcc_dst = (MPIX_FMT_##fmt),                                                  \
		.base.window_size = 3,                                                             \
		.base.run = mpix_kernel_3x3_op,                                                    \
		.kernel_fn = (fn),                                                                 \
		.type = (MPIX_KERNEL_##t),                                                         \
	}

/**
 * @brief Apply a 3x3 identity kernel to an RGB24 input window and produce one RGB24 line.
 *
 * @param in Array of input line buffers to convert.
 * @param out Pointer to the output line converted.
 * @param width Width of the input and output lines in pixels.
 */
void mpix_identity_rgb24_3x3(const uint8_t *in[3], uint8_t *out, uint16_t width);
/**
 * @brief Apply a 5x5 identity kernel to an RGB24 input window and produce one RGB24 line.
 * @copydetails mpix_identity_rgb24_3x3()
 */
void mpix_identity_rgb24_5x5(const uint8_t *in[5], uint8_t *out, uint16_t width);
/**
 * @brief Apply a 3x3 sharpen kernel to an RGB24 input window and produce one RGB24 line.
 * @copydetails mpix_identity_rgb24_3x3()
 */
void mpix_sharpen_rgb24_3x3(const uint8_t *in[3], uint8_t *out, uint16_t width);
/**
 * @brief Apply a 5x5 unsharp kernel to an RGB24 input window and produce one RGB24 line.
 * @copydetails mpix_identity_rgb24_3x3()
 */
void mpix_sharpen_rgb24_5x5(const uint8_t *in[5], uint8_t *out, uint16_t width);
/**
 * @brief Apply a 3x3 edge detection kernel to an RGB24 input window and produce one RGB24 line.
 * @copydetails mpix_identity_rgb24_3x3()
 */
void mpix_edgedetect_rgb24_3x3(const uint8_t *in[3], uint8_t *out, uint16_t width);
/**
 * @brief Apply a 3x3 gaussian blur kernel to an RGB24 input window and produce one RGB24 line.
 * @copydetails mpix_identity_rgb24_3x3()
 */
void mpix_gaussianblur_rgb24_3x3(const uint8_t *in[3], uint8_t *out, uint16_t width);
/**
 * @brief Apply a 3x3 median denoise kernel to an RGB24 input window and produce one RGB24 line.
 * @copydetails mpix_identity_rgb24_3x3()
 */
void mpix_median_rgb24_3x3(const uint8_t *in[3], uint8_t *out, uint16_t width);
/**
 * @brief Apply a 5x5 median denoise kernel to an RGB24 input window and produce one RGB24 line.
 * @copydetails mpix_identity_rgb24_3x3()
 */
void mpix_median_rgb24_5x5(const uint8_t *in[5], uint8_t *out, uint16_t width);

/**
 * @brief Helper to turn a 5x5 kernel conversion function into an operation.
 *
 * The line conversion function is free to perform any processing on the input lines and expected
 * to produce one output line.
 *
 * The line conversion function is to be provided in @c op->arg0.
 *
 * @param op Current operation in progress.
 */
void mpix_kernel_5x5_op(struct mpix_base_op *op);

/**
 * @brief Helper to turn a 3x3 kernel conversion function into an operation.
 * @copydetails mpix_kernel_5x5_op()
 */
void mpix_kernel_3x3_op(struct mpix_base_op *op);

#endif /** @} */
