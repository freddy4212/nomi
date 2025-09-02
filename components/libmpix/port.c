/* SPDX-License-Identifier: Apache-2.0 */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "WE2_device.h"
#include "xprintf.h"
#include <mpix/port.h>

#ifdef FREERTOS
#include <FreeRTOS.h>
#include <task.h>
#endif

uint32_t mpix_port_get_uptime_us(void)
{
#ifdef FREERTOS
    return (uint32_t)xTaskGetTickCount() * 1000;
#else
    uint32_t systick, loop_cnt;
    SystemGetTick(&systick, &loop_cnt);
    return systick * 1000 + loop_cnt / 1000;
#endif
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
    xvprintf(fmt, ap);
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
