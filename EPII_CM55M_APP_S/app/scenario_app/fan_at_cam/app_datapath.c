/**
 * =====================================================================================
 *
 * Filename:  app_datapath.c
 *
 * Description: 影像流水線 (Datapath) 實現
 *
 * =====================================================================================
 */

#include "app_datapath.h"
#include "WE2_debug.h"
#include "hx_drv_sensorctrl.h"
#include "hx_drv_inp.h"
#include "sensor_dp_lib.h"
#include <string.h>

// 全局配置
static app_dp_cfg_t g_dp_cfg;
static uint8_t g_dp_initialized = 0;

int app_datapath_init(app_dp_cfg_t *cfg)
{
    if (!cfg) {
        return -1;
    }
    
    // 複製配置
    memcpy(&g_dp_cfg, cfg, sizeof(app_dp_cfg_t));
    
    // TODO: 初始化感測器
    // TODO: 初始化 INP (Image and Neural Processor)
    // TODO: 配置 JPEG 編碼器
    
    dbg_printf(DBG_LESS_INFO, "Datapath 初始化完成\n");
    dbg_printf(DBG_LESS_INFO, "  Sensor: %dx%d @ %d fps\n", 
               cfg->sensor_width, cfg->sensor_height, cfg->sensor_fps);
    
    g_dp_initialized = 1;
    return 0;
}

int app_datapath_start(void)
{
    if (!g_dp_initialized) {
        dbg_printf(DBG_LESS_INFO, "錯誤: Datapath 未初始化\n");
        return -1;
    }
    
    // TODO: 啟動感測器數據流
    
    dbg_printf(DBG_LESS_INFO, "Datapath 已啟動\n");
    return 0;
}

int app_datapath_stop(void)
{
    if (!g_dp_initialized) {
        return -1;
    }
    
    // TODO: 停止感測器數據流
    
    dbg_printf(DBG_LESS_INFO, "Datapath 已停止\n");
    return 0;
}

int app_datapath_capture_one_frame(void)
{
    if (!g_dp_initialized) {
        dbg_printf(DBG_LESS_INFO, "錯誤: Datapath 未初始化\n");
        return -1;
    }
    
    // TODO: 捕捉單張影像
    // 1. 觸發感測器捕捉
    // 2. 等待影像數據
    // 3. 進行 JPEG 編碼
    // 4. 調用回呼函數
    
    dbg_printf(DBG_LESS_INFO, "捕捉單張影像...\n");
    
    // 模擬：延遲後調用回呼
    if (g_dp_cfg.jpeg_ready_cb) {
        // TODO: 實際的 JPEG 數據地址和大小
        // g_dp_cfg.jpeg_ready_cb(jpeg_addr, jpeg_size);
    }
    
    return 0;
}

int app_datapath_set_jpeg_callback(app_jpeg_ready_cb_t jpeg_cb)
{
    g_dp_cfg.jpeg_ready_cb = jpeg_cb;
    dbg_printf(DBG_LESS_INFO, "JPEG 回呼已更新\n");
    return 0;
}
