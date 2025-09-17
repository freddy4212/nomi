/*
 * mipi_csi.c
 *
 * MIPI CSI interface implementation for WE2 platform
 */

#include "hx_drv_CIS_common.h"
#include "hx_drv_timer.h"
#include "hx_drv_scu_export.h"
#include "hx_drv_scu.h"
#include "hx_drv_swreg_aon.h"
#include "WE2_core.h"
#include "sensor_dp_lib.h"
#include "driver_interface.h"
#include <mpix/utils.h>
#include <mpix/sensor/mipi_csi.h>
#include <math.h>
#include <string.h>

// Static variables
static mipi_csi_config_t g_mipi_config = {0};
static bool g_mipi_initialized = false;
static bool g_mipi_enabled = false;

// Internal functions
static int mipi_csi_calculate_fifo_settings(const mipi_csi_config_t *config, uint16_t *rx_fifo_fill);
static int mipi_csi_reset_controller(void);
static int mipi_csi_configure_phy(const mipi_csi_config_t *config);
static uint32_t mipi_csi_get_pixel_clock_mhz(void);

int mipi_csi_init(const mipi_csi_config_t *config)
{
    if (!config)
    {
        MPIX_ERR("Invalid config");
        return -1;
    }

    // Validate configuration
    if (config->lane_count != MIPI_CSI_LANE_1 &&
        config->lane_count != MIPI_CSI_LANE_2)
    {
        MPIX_ERR("Invalid lane count %d", config->lane_count);
        return -1;
    }

    if (config->pixel_depth != MIPI_CSI_PIXEL_DEPTH_8 &&
        config->pixel_depth != MIPI_CSI_PIXEL_DEPTH_10)
    {
        MPIX_ERR("Invalid pixel depth %d", config->pixel_depth);
        return -1;
    }

    // Store configuration
    memcpy(&g_mipi_config, config, sizeof(mipi_csi_config_t));

    MPIX_INF("Initialize MIPI CSI");
    MPIX_DBG("Clock: %dMHz", config->clock_freq_mhz);
    MPIX_DBG("Lanes: %d", config->lane_count);
    MPIX_DBG("Pixel depth: %d", config->pixel_depth);
    MPIX_DBG("Frame: %dx%d", config->timing.frame_width, config->timing.frame_height);

    // Reset MIPI controller
    if (mipi_csi_reset_controller() != 0)
    {
        return -1;
    }

    // Configure PHY parameters
    if (mipi_csi_configure_phy(config) != 0)
    {
        return -1;
    }

    hx_drv_cis_init((CIS_XHSHUTDOWN_INDEX_E)AON_GPIO2, SENSORCTRL_MCLK_DIV3);

    g_mipi_initialized = true;
    return 0;
}

int mipi_csi_enable(void)
{
    if (!g_mipi_initialized)
    {
        MPIX_ERR("Not initialized");
        return -1;
    }

    MPIX_INF("Enable MIPI CSI");

    // Calculate and set FIFO fill level
    uint16_t rx_fifo_fill = 0;
    if (mipi_csi_calculate_fifo_settings(&g_mipi_config, &rx_fifo_fill) == 0)
    {
        sensordplib_csirx_set_fifo_fill(rx_fifo_fill);
    }

    // Enable CSIRX with configured lane count
    sensordplib_csirx_enable(g_mipi_config.lane_count);

    g_mipi_enabled = true;

    // Debug register dump
    MPIX_DBG("VMUTE: 0x%08X", *(uint32_t *)(SCU_LSC_ADDR + 0x408));
    MPIX_DBG("CSITX+0x1000: 0x%08X", *(uint32_t *)(CSITX_REGS_BASE + 0x1000));
    MPIX_DBG("CSITX+0x1004: 0x%08X", *(uint32_t *)(CSITX_REGS_BASE + 0x1004));

    return 0;
}

int mipi_csi_disable(void)
{
    if (!g_mipi_initialized)
    {
        MPIX_ERR("Not initialized");
        return -1;
    }

    MPIX_INF("Disable MIPI CSI");

    sensordplib_csirx_disable();

    g_mipi_enabled = false;
    return 0;
}

int mipi_csi_configure(const mipi_csi_config_t *config)
{
    if (!config)
    {
        return -1;
    }

    // If already enabled, disable first
    if (g_mipi_enabled)
    {
        mipi_csi_disable();
    }

    // Reinitialize with new config
    g_mipi_initialized = false;
    return mipi_csi_init(config);
}

int mipi_csi_get_status(void)
{
    return g_mipi_enabled ? 1 : 0;
}

static int mipi_csi_calculate_fifo_settings(const mipi_csi_config_t *config, uint16_t *rx_fifo_fill)
{
    if (!config || !rx_fifo_fill)
    {
        return -1;
    }

    uint32_t bitrate_1lane = config->clock_freq_mhz * 2;
    uint32_t byte_clk = bitrate_1lane / 8;
    uint32_t mipi_pixel_clk = mipi_csi_get_pixel_clock_mhz();

    uint32_t n_preload = 15;
    uint32_t l_header = 4;
    uint32_t l_footer = 2;

    // Calculate timing parameters
    double t_input = (double)(l_header + config->timing.line_length * config->pixel_depth / 8 + l_footer) /
                         (config->lane_count * byte_clk) +
                     0.06;
    double t_output = (double)config->timing.line_length / mipi_pixel_clk;
    double t_preload = (double)(7 + (n_preload * 4) / config->lane_count) / mipi_pixel_clk;

    double delta_t = t_input - t_output - t_preload;

    MPIX_DBG("MIPI Timing: t_input=%dns, t_output=%dns, t_preload=%dns",
             (uint32_t)(t_input * 1000), (uint32_t)(t_output * 1000), (uint32_t)(t_preload * 1000));

    if (delta_t <= 0)
    {
        *rx_fifo_fill = 0;
    }
    else
    {
        *rx_fifo_fill = ceil(delta_t * byte_clk * config->lane_count / 4 / (config->pixel_depth / 2)) * (config->pixel_depth / 2);
    }

    MPIX_DBG("Calculated RX FIFO fill=%d", *rx_fifo_fill);
    return 0;
}

// Internal function implementations
static int mipi_csi_reset_controller(void)
{
    MPIX_DBG("Reset controller");

    SCU_DP_SWRESET_T dp_swrst;
    drv_interface_get_dp_swreset(&dp_swrst);

    // Reset MIPI RX/TX
    dp_swrst.HSC_MIPIRX = 0;
    dp_swrst.HSC_MIPITX = 0;
    hx_drv_scu_set_DP_SWReset(dp_swrst);
    hx_drv_timer_cm55x_delay_us(50, TIMER_STATE_DC);

    // Release reset
    dp_swrst.HSC_MIPIRX = 1;
    dp_swrst.HSC_MIPITX = 1;
    hx_drv_scu_set_DP_SWReset(dp_swrst);

    return 0;
}

static int mipi_csi_configure_phy(const mipi_csi_config_t *config)
{
    uint32_t mipi_pixel_clk = mipi_csi_get_pixel_clock_mhz();

    // Configure HS count based on pixel clock
    MIPIRX_DPHYHSCNT_CFG_T hscnt_cfg;
    hscnt_cfg.mipirx_dphy_hscnt_clk_en = 0;
    hscnt_cfg.mipirx_dphy_hscnt_ln0_en = 1;
    hscnt_cfg.mipirx_dphy_hscnt_ln1_en = (config->lane_count >= 2) ? 1 : 0;

    if (mipi_pixel_clk == 200)
    {
        hscnt_cfg.mipirx_dphy_hscnt_clk_val = 0x03;
        hscnt_cfg.mipirx_dphy_hscnt_ln0_val = 0x10;
        hscnt_cfg.mipirx_dphy_hscnt_ln1_val = 0x10;
    }
    else if (mipi_pixel_clk == 300)
    {
        hscnt_cfg.mipirx_dphy_hscnt_clk_val = 0x03;
        hscnt_cfg.mipirx_dphy_hscnt_ln0_val = 0x18;
        hscnt_cfg.mipirx_dphy_hscnt_ln1_val = 0x18;
    }
    else
    { // RC96 default
        hscnt_cfg.mipirx_dphy_hscnt_clk_val = 0x03;
        hscnt_cfg.mipirx_dphy_hscnt_ln0_val = 0x06;
        hscnt_cfg.mipirx_dphy_hscnt_ln1_val = 0x06;
    }

    sensordplib_csirx_set_hscnt(hscnt_cfg);

    // Set pixel depth
    if (config->pixel_depth == MIPI_CSI_PIXEL_DEPTH_8 ||
        config->pixel_depth == MIPI_CSI_PIXEL_DEPTH_10)
    {
        sensordplib_csirx_set_pixel_depth(config->pixel_depth);
    }
    else
    {
        MPIX_ERR("Unsupported pixel depth %d", config->pixel_depth);
        return -1;
    }

    // Configure deskew
    sensordplib_csirx_set_deskew(config->deskew_enable ? 1 : 0);

    MPIX_DBG("PHY configured (pixel_clk=%dMHz)", mipi_pixel_clk);
    return 0;
}

static uint32_t mipi_csi_get_pixel_clock_mhz(void)
{
    SCU_PDHSC_DPCLK_CFG_T cfg;

    if (hx_drv_scu_get_pdhsc_dpclk_cfg(&cfg) != SCU_NO_ERROR)
    {
        MPIX_ERR("Get SCU PDHSC DPCLK CFG failed");
    }

    uint32_t pllfreq;

    hx_drv_swreg_aon_get_pllfreq(&pllfreq);

    cfg.mipiclk.hscmipiclksrc = SCU_HSCMIPICLKSRC_RC96M48M;
    cfg.mipiclk.hscmipiclkdiv = 0;
    cfg.dpclk = SCU_HSCDPCLKSRC_RC96M48M;

    if (pllfreq == 400000000)
    {
        cfg.mipiclk.hscmipiclksrc = SCU_HSCMIPICLKSRC_PLL;
        cfg.mipiclk.hscmipiclkdiv = 1;
    }
    else
    {
        cfg.mipiclk.hscmipiclksrc = SCU_HSCMIPICLKSRC_PLL;
        cfg.mipiclk.hscmipiclkdiv = 0;
    }

    if (hx_drv_scu_set_pdhsc_dpclk_cfg(cfg, 0, 1) != SCU_NO_ERROR)
    {
        MPIX_ERR("Set SCU PDHSC DPCLK CFG failed");
    }

    uint32_t mipi_pixel_clk = 96; // Default
    hx_drv_scu_get_freq(SCU_CLK_FREQ_TYPE_HSC_MIPI_RXCLK, &mipi_pixel_clk);
    return mipi_pixel_clk / 1000000;
}
