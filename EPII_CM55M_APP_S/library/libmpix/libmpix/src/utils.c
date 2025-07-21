/* SPDX-License-Identifier: Apache-2.0 */

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#include <mpix/utils.h>

uint32_t mpix_lcg_rand_u32(void)
{
	static uint32_t lcg_state;

	/* Linear Congruent Generator (LCG) are low-quality but very fast, here considered enough
	 * as even a fixed offset would have been enough.The % phase is skipped as there is already
	 * "% vbuf->bytesused" downstream in the code.
	 *
	 * The constants are from https://en.wikipedia.org/wiki/Linear_congruential_generator
	 */
	lcg_state = lcg_state * 1103515245 + 12345;
	return lcg_state;
}
