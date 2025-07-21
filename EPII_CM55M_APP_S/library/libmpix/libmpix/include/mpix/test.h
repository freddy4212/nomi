/**
 * SPDX-License-Identifier: Apache-2.0
 * @internal
 * @defgroup mpix_test_h mpix/test.h
 * @brief Test suite utilities
 * @{
 */
#ifndef MPIX_TEST_H
#define MPIX_TEST_H

#include <assert.h>

#define mpix_test(expr) \
	assert(expr)

#define mpix_test_ok(ret) \
	assert((ret) == 0)

#define mpix_test_within(val, reference, margin) \
	(assert((val) >= (reference) - (margin)), assert((val) <= (reference) + (margin)))

#define mpix_test_equal(val, reference) \
	assert((val) == (reference))

#endif /* @} */
