/**
 * =====================================================================================
 *
 * Filename:  app_main.c
 *
 * Description: AT 指令拍照應用程式 (主入口)
 * - 僅負責平台初始化和建立 FreeRTOS 任務
 * - 所有 AT 指令邏輯已移至 at_cmd_handler.c
 *
 * =====================================================================================
 */

#include "app_platform.h"
#include "WE2_debug.h"
#include "FreeRTOS.h"
#include "task.h"

// 引入新的 AT 指令處理器標頭檔
#include "at_cmd_handler.h"


/* --- 主函數 --- */

int app_main(void)
{
    // 初始化平台 (UART, PMU, SCU)
    app_platform_init();
    
    dbg_printf(DBG_LESS_INFO, "系統啟動 (Refactored AT CMD App)\n");

    // 初始化 AT 指令處理器 (建立信號量等)
    at_cmd_init();

    // 建立 AT 指令任務
    if (xTaskCreate(at_cmd_task, "AT_CMD_TASK", 1024, NULL, (configMAX_PRIORITIES - 2), NULL) != pdPASS) {
        dbg_printf(DBG_LESS_INFO, "錯誤: 無法建立 at_cmd_task\n");
        return -1;
    }
    
    dbg_printf(DBG_LESS_INFO, "啟動 FreeRTOS 排程器...\n");

    // 啟動 FreeRTOS 排程器
    vTaskStartScheduler();

    // 理論上不會執行到這裡
    while(1);
    return 0;
}
