/**
 * =====================================================================================
 *
 * Filename:  app_platform.h
 *
 * Description: 平台初始化相關函數聲明
 *
 * =====================================================================================
 */

#ifndef APP_PLATFORM_H_
#define APP_PLATFORM_H_

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief 初始化平台 (UART, PMU, SCU 等)
 * @return 0 表示成功
 */
int app_platform_init(void);

#ifdef __cplusplus
}
#endif

#endif /* APP_PLATFORM_H_ */
