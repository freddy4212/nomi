/**
 * SPDX-License-Identifier: Apache-2.0
 * @defgroup mpix_op_qoi_h mpix/op_qoi.h
 * @brief Low-level QOI encoding operations
 * @{
 */
#ifndef MPIX_QOI_H
#define MPIX_QOI_H

#include <stdlib.h>
#include <stdint.h>

#include <mpix/op.h>

/**
 * QOI format conversion operation.
 * @internal
 */
struct mpix_qoi_op {
	/** Fields common to all operations. */
	struct mpix_base_op base;
	/** Array of previously seen pixels */
	uint8_t qoi_cache[64 * 3];
	/** The last seend pixel value just before the new pixel to encode */
	uint8_t qoi_prev[3];
	/** Size of the ongoing run */
	uint8_t qoi_run_length;
};

/**
 * @brief Define a new encoding operation: from a pixel format to the QOI format.
 *
 * @param id Short identifier to differentiate operations of the same category.
 * @param op Operation to use for the conversion.
 * @param fmt_src The input format for that operation.
 * @param fmt_dst The Output format for that operation.
 */
#define MPIX_REGISTER_QOI_OP(id, op, fmt_src, fmt_dst)                                             \
	const struct mpix_qoi_op mpix_qoi_op_##id = {                                              \
		.base.name = ("qoi_" #id),                                                         \
		.base.fourcc_src = (MPIX_FMT_##fmt_src),                                           \
		.base.fourcc_dst = (MPIX_FMT_##fmt_dst),                                           \
		.base.window_size = 1,                                                             \
		.base.run = (op),                                                                  \
	}

#endif /** @} */
