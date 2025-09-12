/**
 * SPDX-License-Identifier: Apache-2.0
 * @file sccb.c
 * @brief Simple I2C operations for camera sensors (SCCB) - WE2 implementation
 */

#include <errno.h>

#include <hx_drv_CIS_common.h>
#include <hx_drv_timer.h>
#include <hx_drv_scu.h>
#include <hx_drv_scu_export.h>

#include <mpix/sensor/sccb.h>

static bool g_sccb_initialized = false;
static uint8_t g_sccb_addr = 0;

int sccb_init(void)
{
    // power up the sensor
    hx_drv_gpio_set_output(AON_GPIO1, GPIO_OUT_HIGH);
    hx_drv_scu_set_PA1_pinmux(SCU_PA1_PINMUX_AON_GPIO1, 1);
    hx_drv_gpio_set_out_value(AON_GPIO1, GPIO_OUT_HIGH);

    board_delay_ms(10);

    /* CIS initialization is handled by the camera driver */
    g_sccb_initialized = true;

    return 0;
}

int sccb_write_reg(uint8_t addr, uint16_t reg, uint8_t value)
{
    if (g_sccb_addr != addr)
    {
        hx_drv_cis_set_slaveID(addr);
        g_sccb_addr = addr;
    }

    if (!g_sccb_initialized)
    {
        g_sccb_initialized = true;
    }

    /* Use HX CIS driver for register write */
    HX_CIS_ERROR_E error = hx_drv_cis_set_reg(reg, value, 1);

    switch (error)
    {
    case HX_CIS_NO_ERROR:
        return 0;
    case HX_CIS_ERROR_INVALID_PARAMETERS:
        return -EINVAL;
    default:
        return -EIO;
    }
}

int sccb_read_reg(uint8_t addr, uint16_t reg, uint8_t *value)
{
    if (g_sccb_addr != addr)
    {
        hx_drv_cis_set_slaveID(addr);
        g_sccb_addr = addr;
    }

    if (!value)
    {
        return -EINVAL;
    }

    if (!g_sccb_initialized)
    {
        g_sccb_initialized = true;
    }

    /* Use HX CIS driver for register read */
    HX_CIS_ERROR_E error = hx_drv_cis_get_reg(reg, value);

    switch (error)
    {
    case HX_CIS_NO_ERROR:
        return 0;
    case HX_CIS_ERROR_INVALID_PARAMETERS:
        return -EINVAL;
    default:
        return -EIO;
    }
}

void sccb_delay_ms(uint32_t ms)
{
    board_delay_ms(ms);
}