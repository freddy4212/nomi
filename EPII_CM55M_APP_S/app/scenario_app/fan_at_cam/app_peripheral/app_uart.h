/**
 * =====================================================================================
 *
 * Filename:  app_uart.h
 *
 * Description: UART 通訊相關函數
 *
 * =====================================================================================
 */

#ifndef APP_UART_H_
#define APP_UART_H_

#include <stdint.h>
#include <stdarg.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief 初始化 UART
 * @return 0 表示成功
 */
int app_uart_init(void);

/**
 * @brief 發送字串到 UART
 * @param str 要發送的字串
 * @return 發送的字節數
 */
int app_uart_send_str(const char *str);

/**
 * @brief 發送緩衝區數據到 UART
 * @param buf 數據緩衝區
 * @param len 數據長度
 * @return 發送的字節數
 */
int app_uart_send_buf(const uint8_t *buf, uint32_t len);

/**
 * @brief printf 風格的 UART 輸出
 * @param format 格式字串
 * @param ... 可變參數
 * @return 輸出的字符數
 */
int app_uart_printf(const char *format, ...);

/**
 * @brief 從 UART 讀取一個字元 (阻塞)
 * @param ch 指向儲存讀取字元的指標
 * @return 0 成功, -1 失敗
 */
int app_uart_getchar(char *ch);

/**
 * @brief 發送一個字元到 UART
 * @param ch 要發送的字元
 * @return 0 成功, -1 失敗
 */
int app_uart_putchar(char ch);

/**
 * @brief 檢查 UART 是否有可讀取的資料
 * @return >0 表示有數據，0 表示無數據
 */
int app_uart_available(void);

#ifdef __cplusplus
}
#endif

#endif /* APP_UART_H_ */
