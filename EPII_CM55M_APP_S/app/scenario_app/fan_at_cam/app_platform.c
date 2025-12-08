/**
 * =====================================================================================
 *
 * Filename:  app_platform.c
 *
 * Description: 平台初始化實現
 *
 * =====================================================================================
 */

#include "app_platform.h"
#include "board.h"
#include "WE2_debug.h"
#include "hx_drv_pmu.h"
#include "hx_drv_scu.h"

int app_platform_init(void)
{
    // 初始化板子 (UART, console 等)
    board_init();
    
    // 其他平台相關初始化可以在這裡添加
    
    return 0;
}
