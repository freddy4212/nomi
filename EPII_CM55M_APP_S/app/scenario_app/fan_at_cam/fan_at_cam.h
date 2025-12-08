#ifndef APP_MAIN_H_
#define APP_MAIN_H_

/**
 * @brief 應用程式主入口
 */
int app_main(void);

// 宣告 AT 指令任務的進入點
void at_cmd_task(void *pvParameters);

#endif // APP_MAIN_H_