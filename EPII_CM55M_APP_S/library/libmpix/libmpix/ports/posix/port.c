/* SPDX-License-Identifier: Apache-2.0 */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include <mpix/port.h>

#ifdef FREERTOS
/* FreeRTOS kernel includes. */
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "timers.h"
#endif

uint32_t mpix_port_get_uptime_us(void)
{
	int time = 1;
#ifdef FREERTOS
	TickType_t ticks = xTaskGetTickCount();
    time =  ticks * (1000000 / configTICK_RATE_HZ); 
#endif
	// clock_gettime(4, &ts);
	return time;
}


void *mpix_port_alloc(size_t size)
{
	return malloc(size);
}

void mpix_port_free(void *mem)
{
	free(mem);
}

void mpix_port_printf(const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);
}

int mpix_port_init_exposure(void *dev, int32_t *def, int32_t *max)
{
	*def = 0;
	*max = 1;

	return 0;
}

int mpix_port_set_exposure(void *dev, int32_t val)
{
	/* Not supported, do nothing */

	return 0;
}
