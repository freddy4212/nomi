/**
 * =====================================================================================
 *
 * Filename:  app_uart.c
 *
 * Description: UART 通訊實現
 *
 * =====================================================================================
 */

#include "app_uart.h"
#include "hx_drv_uart.h"
#include "WE2_device.h"
#include <stdio.h>
#include <string.h>

// UART 設定
#define UART_BR_115200    115200

int app_uart_init(void)
{
    // UART 初始化通常在 board_init() 中完成
    // 這裡可以添加額外的配置
    return 0;
}

int app_uart_send_str(const char *str)
{
    if (!str) return 0;
    
    uint32_t len = strlen(str);
    hx_drv_uart_print(USE_DW_UART_0, (char*)str);
    return len;
}

int app_uart_send_buf(const uint8_t *buf, uint32_t len)
{
    if (!buf || len == 0) return 0;
    
    // 逐字節發送
    for (uint32_t i = 0; i < len; i++) {
        hx_drv_uart_write(USE_DW_UART_0, buf[i]);
    }
    return len;
}

int app_uart_printf(const char *format, ...)
{
    char buffer[256];
    va_list args;
    
    va_start(args, format);
    int len = vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    
    if (len > 0) {
        app_uart_send_str(buffer);
    }
    
    return len;
}

int app_uart_getchar(char *ch)
{
    if (ch == NULL) {
        return -1;
    }
    
    // 阻塞式讀取
    while (hx_drv_uart_get_available_read_data(DEBUG_UART_PORT) == 0) {
        // 等待資料
    }
    
    uint8_t data;
    if (hx_drv_uart_read(DEBUG_UART_PORT, &data, 1) == HX_DRV_LIB_PASS) {
        *ch = (char)data;
        return 0;
    }
    
    return -1;
}

int app_uart_putchar(char ch)
{
    uint8_t data = (uint8_t)ch;
    if (hx_drv_uart_write(DEBUG_UART_PORT, &data, 1) == HX_DRV_LIB_PASS) {
        return 0;
    }
    return -1;
}

int app_uart_available(void)
{
    HX_DRV_DEV_UART *uart_obj = hx_drv_uart_get_dev(USE_DW_UART_0);
    
    if (uart_obj && uart_obj->uart_read) {
        // 簡單檢查：嘗試讀取但不實際消耗數據
        // 實際實現可能需要查詢 UART 狀態暫存器
        return 1; // 假設總是有可能有數據
    }
    
    return 0;
}
