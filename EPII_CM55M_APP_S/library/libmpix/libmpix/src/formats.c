/* SPDX-License-Identifier: Apache-2.0 */

#include <mpix/formats.h>

__attribute__((weak))
uint8_t mpix_bits_per_pixel_cb(uint32_t fourcc)
{
	/* Default implementation to be overwritten by the application */
	return 0;
}
