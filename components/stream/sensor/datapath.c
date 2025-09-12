#include <WE2_core.h>
#include <board.h>
#include <hx_drv_timer.h>
#include <hx_drv_swreg_aon.h>
#include <sensor_dp_lib.h>

#include <mpix/utils.h>
#include <mpix/sensor/datapath.h>

static datapath_config_t g_current_config = {0};
static bool g_datapath_initialized = false;
static bool g_datapath_running = false;
static volatile bool g_frame_ready = false;
static volatile uint32_t g_wdma1_baseaddr = 0;
static volatile uint32_t g_wdma2_baseaddr = 0;
static volatile uint32_t g_wdma3_baseaddr = 0;

static void _dp_event_cb(SENSORDPLIB_STATUS_E event)
{
    switch (event)
    {
    case SENSORDPLIB_STATUS_XDMA_FRAME_READY:
        MPIX_INF("Frame ready");
        g_frame_ready = true;
        break;
    default:
        hx_drv_swreg_aon_set_sensorinit(SWREG_AON_SENSOR_INIT_NO);
        MPIX_WRN("Unknown event %d", event);
        break;
    }
}

int datapath_init(const datapath_config_t *config)
{
    if (!config)
    {
        MPIX_ERR("Invalid config");
        return -1;
    }
    memcpy(&g_current_config, config, sizeof(datapath_config_t));
    g_datapath_initialized = true;
    MPIX_INF("Datapath initialized: %dx%d, depth %d, crop %s",
             config->width, config->height, config->pixel_depth,
             config->enable_crop ? "enabled" : "disabled");

    INP_CROP_T crop;
    crop.start_x = 0;
    crop.start_y = 0;
    crop.last_x = config->width - 1;
    crop.last_y = config->height - 1;

    g_wdma2_baseaddr = (uint32_t)mpix_port_alloc(config->width * config->height);
    if (!g_wdma2_baseaddr)
    {
        MPIX_ERR("Failed to allocate WDMA2 buffer");
        return -1;
    }

    sensordplib_set_xDMA_baseaddrbyapp(g_wdma1_baseaddr, g_wdma2_baseaddr, g_wdma3_baseaddr);

    sensordplib_set_sensorctrl_inp_wi_crop(SENSORDPLIB_SENSOR_HM2130, SENSORDPLIB_STREAM_NONEAOS, config->width, config->height, INP_SUBSAMPLE_DISABLE, crop);

    sensordplib_set_raw_wdma2(config->width, config->height, _dp_event_cb);
    return 0;
}

int datapath_start(void)
{
    if (!g_datapath_initialized)
    {
        MPIX_ERR("Datapath not initialized");
        return -1;
    }
    sensordplib_set_mclkctrl_xsleepctrl_bySCMode();
    sensordplib_set_sensorctrl_start();
    g_datapath_running = true;
    MPIX_INF("Datapath started");
    return 0;
}

int datapath_stop(void)
{
    if (!g_datapath_initialized)
    {
        MPIX_ERR("Datapath not initialized");
        return -1;
    }
    sensordplib_stop_capture();
    sensordplib_start_swreset();
    sensordplib_stop_swreset_WoSensorCtrl();

    return 0;
}

bool datapath_is_frame_ready(void)
{
    return g_frame_ready;
}

uint32_t datapath_acquire_raw_buffer(void)
{
    hx_InvalidateDCache_by_Addr((volatile void *)g_wdma2_baseaddr, g_current_config.width * g_current_config.height);
    return g_wdma2_baseaddr;
}

int datapath_release_raw_buffer(void)
{
    g_frame_ready = false;
    sensordplib_retrigger_capture();
    return 0;
}

int datapath_configure(const datapath_config_t *config)
{
    if (!config)
    {
        return -1;
    }

    // If running, stop first
    if (g_datapath_running)
    {
        datapath_stop();
    }

    return datapath_init(config);
}

int datapath_get_status(void)
{
    return 1; // Assume always running for simplicity
}

int datapath_deinit(void)
{
    MPIX_INF("Datapath deinitialized");
    return 0;
}