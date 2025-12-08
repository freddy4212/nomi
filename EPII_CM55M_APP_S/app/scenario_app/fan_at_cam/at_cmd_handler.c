/**
 * =====================================================================================
 *
 * Filename:  at_cmd_handler.c
 *
 * Description: AT 指令處理器
 * - 負責監聽、解析和執行所有 AT 指令。
 * - 參考 Seeed-Studio 範例進行了重構。
 *
 * =====================================================================================
 */

#include "at_cmd_handler.h"
#include "app_platform.h"
#include "app_datapath.h"
#include "app_peripheral/app_uart.h"
#include "WE2_debug.h"
#include "hx_drv_pmu.h"
#include "hx_drv_scu.h"

#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include <stdio.h>
#include <string.h>

/* --- 模組內部全域變數 --- */

// UART 緩衝區
#define AT_CMD_BUF_LEN 256
static char g_at_cmd_buf[AT_CMD_BUF_LEN];
static uint32_t g_at_cmd_buf_idx = 0;

// JPEG 影像緩衝區
#define JPEG_BUF_SIZE (30 * 1024) // 30KB
static uint8_t g_jpeg_buf[JPEG_BUF_SIZE] __attribute__((section(".bs_data_in_DM_RAM_RW")));
static volatile uint32_t g_jpeg_total_size = 0; // 設為 volatile 因為它在 CB 中被修改
static uint32_t g_jpeg_buf_addr = (uint32_t)g_jpeg_buf;

// FreeRTOS 信號量，用於通知 AT 任務 "JPEG 已準備好"
static SemaphoreHandle_t g_jpeg_ready_sem = NULL;

// 影像流水線 (Datapath) 設定
// (將其設為靜態變數，使其僅在此檔案內可見)
static app_dp_cfg_t g_app_datapath_cfg = {
    .sensor_id = APP_SENSOR_ID,
    .sensor_fps = APP_SENSOR_FPS,
    .sensor_format = APP_SENSOR_FORMAT,
    .sensor_width = APP_SENSOR_WIDTH,
    .sensor_height = APP_SENSOR_HEIGHT,
    
    .dp_app_type = APP_DP_APP_TYPE_SYNC, // 同步模式 (由 AT 指令觸發)
    .dp_in_type = APP_DP_IN_TYPE_SENSOR,
    .dp_out_type = APP_DP_OUT_TYPE_JPEG,
    
    .out_jpeg_quality = 90,
    .out_width = APP_SENSOR_WIDTH,
    .out_height = APP_SENSOR_HEIGHT,

    .frame_ready_cb = NULL,
    .jpeg_ready_cb = NULL, // ★注意：我們將在需要時動態註冊回呼
    .md_ready_cb = NULL,
    .voc_ready_cb = NULL,
};


/* --- 內部輔助函數 --- */

/**
 * @brief JPEG 影像準備完成的回呼函數 (動態註冊)
 * (此函數在 ISR 上下文中被呼叫)
 */
static void at_jpeg_ready_cb(uint32_t jpeg_addr, uint32_t jpeg_size)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;

    if (jpeg_size > JPEG_BUF_SIZE) {
        dbg_printf(DBG_LESS_INFO, "錯誤: JPEG 緩衝區不足 (%u > %u)\n", jpeg_size, JPEG_BUF_SIZE);
        g_jpeg_total_size = 0;
    } else {
        memcpy((void*)g_jpeg_buf_addr, (void*)jpeg_addr, jpeg_size);
        g_jpeg_total_size = jpeg_size;
    }
    
    // 通知 AT 任務：影像已準備好
    xSemaphoreGiveFromISR(g_jpeg_ready_sem, &xHigherPriorityTaskWoken);
    
    // 如果信號量喚醒了更高優先級的任務，立即進行上下文切換
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

/**
 * @brief 透過 UART 發送影像數據 (仿 Seeed 格式)
 */
static void send_image_data(uint32_t addr, uint32_t size)
{
    app_uart_send_str("IMAGE_START\r\n");
    app_uart_printf("Length:%u\r\n", size);
    app_uart_send_buf((uint8_t*)addr, size);
    app_uart_send_str("\r\nIMAGE_END\r\n");
}

/**
 * @brief 取得晶片 ID 與版本號
 */
static void cmd_get_chip_id(void)
{
    // TODO: Implement chip ID reading using correct SCU API
    app_uart_send_str("Chip: WE2\r\n");
    app_uart_send_str("Version: Unknown\r\n");
    app_uart_send_str("OK\r\n");
}

/**
 * @brief 解析並執行 AT 指令
 */
static void process_at_command(char *cmd)
{
    dbg_printf(DBG_LESS_INFO, "收到指令: %s\n", cmd);

    // 基礎指令
    if (strcmp(cmd, "AT") == 0) {
        app_uart_send_str("OK\r\n");
    }
    // (新) 版本查詢
    else if (strcmp(cmd, "AT+VER?") == 0) {
        app_uart_send_str("AT Command Handler V1.1 (Refactored)\r\n");
        app_uart_send_str("OK\r\n");
    }
    // (新) 晶片 ID 查詢
    else if (strcmp(cmd, "AT+ID?") == 0) {
        cmd_get_chip_id();
    }
    // (新) 狀態查詢
    else if (strcmp(cmd, "AT+STATE?") == 0) {
        app_uart_send_str("State: Idle\r\n"); // 目前總是空閒
        app_uart_send_str("OK\r\n");
    }
    // (新) 演算法查詢
    else if (strcmp(cmd, "AT+ALGO?") == 0) {
        app_uart_send_str("Algo: SNAPSHOT\r\n"); // 我們目前唯一的演算法
        app_uart_send_str("OK\r\n");
    }
    // (新) 模型查詢
    else if (strcmp(cmd, "AT+MODEL?") == 0) {
        app_uart_send_str("Model: None\r\n"); // 尚未載入模型
        app_uart_send_str("OK\r\n");
    }
    // 重啟指令 - 使用 NVIC System Reset
    else if (strcmp(cmd, "AT+RESET") == 0) {
        app_uart_send_str("OK\r\n");
        vTaskDelay(pdMS_TO_TICKS(100)); // 延遲以確保 "OK" 送出
        NVIC_SystemReset(); // ARM CMSIS system reset
    }
    // 拍照指令 (簡化版)
    else if (strcmp(cmd, "AT+CAPTURE") == 0 || strcmp(cmd, "AT+SNAPSHOT") == 0) {
        app_uart_send_str("Capturing...\r\n");
        
        g_jpeg_total_size = 0;
        
        // TODO: Implement capture logic
        // 1. 動態註冊回呼函數
        g_app_datapath_cfg.jpeg_ready_cb = at_jpeg_ready_cb;
        
        // 2. 等待 JPEG 準備完成 (由 at_jpeg_ready_cb 發出信號)
        if (xSemaphoreTake(g_jpeg_ready_sem, pdMS_TO_TICKS(5000)) == pdTRUE) {
            if (g_jpeg_total_size > 0) {
                // 成功, 發送影像
                send_image_data(g_jpeg_buf_addr, g_jpeg_total_size);
                app_uart_send_str("OK\r\n");
            } else {
                app_uart_send_str("ERROR: JPEG Buffer Overflow\r\n");
            }
        } else {
            // 超時
            app_uart_send_str("ERROR: Capture Timeout\r\n");
        }

        // 4. 解除註冊回呼函數 (恢復到 NULL)
        g_app_datapath_cfg.jpeg_ready_cb = NULL;
        app_datapath_reinit(&g_app_datapath_cfg);
    }
    // 未知指令
    else {
        app_uart_send_str("ERROR: Unknown command\r\n");
    }
}


/* --- 公共函數 --- */

/**
 * @brief 初始化 AT 指令處理器
 */
void at_cmd_init(void)
{
    g_jpeg_ready_sem = xSemaphoreCreateBinary();
    if (g_jpeg_ready_sem == NULL) {
        dbg_printf(DBG_LESS_INFO, "錯誤: 無法建立 g_jpeg_ready_sem\n");
    }
}

/**
 * @brief AT 指令監聽任務
 */
void at_cmd_task(void *pvParameters)
{
    char c;
    dbg_printf(DBG_LESS_INFO, "AT 指令任務已啟動, 監聽 UART0...\n");

    // 初始化影像流水線 (不帶回呼)
    if (app_datapath_init(&g_app_datapath_cfg) != 0) {
        dbg_printf(DBG_LESS_INFO, "錯誤: app_datapath_init 失敗\n");
        vTaskDelete(NULL);
    }
    
    // 初始化 datapath (感測器和影像處理)
    if (app_datapath_init(&g_app_datapath_cfg) != 0) {
        dbg_printf(DBG_LESS_INFO, "錯誤: app_datapath_init 失敗\n");
        vTaskDelete(NULL);
    }

    dbg_printf(DBG_LESS_INFO, "相機初始化完成。\n");
    app_uart_send_str("AT Command Ready (Refactored)\r\n");

    // 任務主迴圈
    while (1) {
        // 從 UART 讀取一個字元 (阻塞)
        app_uart_getchar(&c);

        // 處理換行符 (指令結束)
        if (c == '\r' || c == '\n') {
            if (g_at_cmd_buf_idx > 0) {
                g_at_cmd_buf[g_at_cmd_buf_idx] = '\0';
                process_at_command(g_at_cmd_buf);
                g_at_cmd_buf_idx = 0;
            }
        }
        // 處理退格鍵
        else if (c == '\b' || c == 0x7F) {
            if (g_at_cmd_buf_idx > 0) {
                g_at_cmd_buf_idx--;
                app_uart_send_buf((uint8_t*)"\b \b", 3);
            }
        }
        // 處理一般字元
        else if (g_at_cmd_buf_idx < (AT_CMD_BUF_LEN - 1)) {
            g_at_cmd_buf[g_at_cmd_buf_idx++] = c;
            app_uart_putchar(c); // 回顯
        }
    }
}
