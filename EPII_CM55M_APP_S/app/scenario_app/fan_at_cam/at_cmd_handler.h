#ifndef AT_CMD_HANDLER_H_
#define AT_CMD_HANDLER_H_

#include <stdint.h>

/**
 * @brief 初始化 AT 指令處理器。
 * (例如：建立所需的信號量)
 */
void at_cmd_init(void);

/**
 * @brief AT 指令處理任務的主函數。
 * 此任務將永久執行，監聽 UART 輸入。
 */
void at_cmd_task(void *pvParameters);

#endif // AT_CMD_HANDLER_H_
