/* SPDX-License-Identifier: Apache-2.0 */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#include "WE2_device.h"
#include "xprintf.h"
#include <mpix/port.h>

#ifdef FREERTOS
#include <FreeRTOS.h>
#include <task.h>
#include <timers.h>
#include <portmacro.h>
#endif

#ifndef FREERTOS
/* Static memory pool configuration - only used when FreeRTOS is not available */
#define MPIX_MEMORY_POOL_SIZE (1024 * 1024) /* 512KB memory pool */
#define MPIX_MAX_ALLOCATIONS 64           /* Maximum number of allocations */

/* Memory block header */
typedef struct mpix_mem_block
{
    size_t size; /* Size of allocated block */
    int in_use;  /* 1 if in use, 0 if free */
    void *ptr;   /* Pointer to actual memory */
} mpix_mem_block_t;

/* Static memory pool */
__attribute__((section(".bss.ucHeap"))) static uint8_t g_memory_pool[MPIX_MEMORY_POOL_SIZE] __ALIGNED(32);
static mpix_mem_block_t g_mem_blocks[MPIX_MAX_ALLOCATIONS];
static size_t g_pool_offset = 0;
static int g_pool_initialized = 0;
#endif /* !FREERTOS */

#ifndef FREERTOS
/* Initialize memory pool */
static void mpix_memory_pool_init(void)
{
    if (g_pool_initialized)
    {
        return;
    }

    memset(g_memory_pool, 0, sizeof(g_memory_pool));
    memset(g_mem_blocks, 0, sizeof(g_mem_blocks));
    g_pool_offset = 0;
    g_pool_initialized = 1;
}

/* Find free memory block slot */
static int mpix_find_free_block(void)
{
    for (int i = 0; i < MPIX_MAX_ALLOCATIONS; i++)
    {
        if (!g_mem_blocks[i].in_use)
        {
            return i;
        }
    }
    return -1;
}

/* Find memory block by pointer */
static int mpix_find_block_by_ptr(void *ptr)
{
    for (int i = 0; i < MPIX_MAX_ALLOCATIONS; i++)
    {
        if (g_mem_blocks[i].in_use && g_mem_blocks[i].ptr == ptr)
        {
            return i;
        }
    }
    return -1;
}
#endif /* !FREERTOS */

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
#ifdef FREERTOS
    /* Use FreeRTOS heap when available */
    if (size == 0)
    {
        return NULL;
    }
    
    void *ptr = pvPortMalloc(size);
    if (ptr != NULL)
    {
        /* Clear allocated memory */
        memset(ptr, 0, size);
    }
    return ptr;
#else
    /* Use static memory pool for bare metal */
    if (!g_pool_initialized)
    {
        mpix_memory_pool_init();
    }

    if (size == 0)
    {
        return NULL;
    }

    /* Align size to 4-byte boundary */
    size = (size + 3) & ~3;

    /* Check if we have enough space in the pool */
    if (g_pool_offset + size > MPIX_MEMORY_POOL_SIZE)
    {
        return NULL; /* Out of memory */
    }

    /* Find a free block slot */
    int block_idx = mpix_find_free_block();
    if (block_idx == -1)
    {
        return NULL; /* No more allocation slots */
    }

    /* Allocate from pool */
    void *ptr = &g_memory_pool[g_pool_offset];
    g_pool_offset += size;

    /* Record allocation */
    g_mem_blocks[block_idx].size = size;
    g_mem_blocks[block_idx].in_use = 1;
    g_mem_blocks[block_idx].ptr = ptr;

    /* Clear allocated memory */
    memset(ptr, 0, size);

    return ptr;
#endif
}

void mpix_port_free(void *mem)
{
#ifdef FREERTOS
    /* Use FreeRTOS heap when available */
    if (mem != NULL)
    {
        vPortFree(mem);
    }
#else
    /* Use static memory pool for bare metal */
    if (!mem || !g_pool_initialized)
    {
        return;
    }

    /* Find the memory block */
    int block_idx = mpix_find_block_by_ptr(mem);
    if (block_idx == -1)
    {
        return; /* Invalid pointer */
    }

    /* Mark block as free */
    g_mem_blocks[block_idx].in_use = 0;
    g_mem_blocks[block_idx].ptr = NULL;
    g_mem_blocks[block_idx].size = 0;

    /* Note: This is a simple allocator that doesn't compact memory.
     * Memory is not returned to the pool until system reset.
     * For embedded systems, this is often acceptable.
     */
#endif
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
