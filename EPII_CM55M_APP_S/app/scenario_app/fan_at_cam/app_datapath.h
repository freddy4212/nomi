/**
 * =====================================================================================
 *
 * Filename:  app_datapath.h
 *
 * Description: 影像流水線 (Datapath) 配置和控制
 *
 * =====================================================================================
 */

#ifndef APP_DATAPATH_H_
#define APP_DATAPATH_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- 常數定義 --- */

// Sensor 設定
#define APP_SENSOR_ID         0
#define APP_SENSOR_FPS        30
#define APP_SENSOR_FORMAT     0  // RGB
#define APP_SENSOR_WIDTH      640
#define APP_SENSOR_HEIGHT     480

/* --- 類型定義 --- */

// Datapath 應用類型
typedef enum {
    APP_DP_APP_TYPE_SYNC = 0,    // 同步模式 (由指令觸發)
    APP_DP_APP_TYPE_ASYNC        // 異步模式 (持續運行)
} app_dp_app_type_t;

// Datapath 輸入類型
typedef enum {
    APP_DP_IN_TYPE_SENSOR = 0,   // 從感測器輸入
    APP_DP_IN_TYPE_MEMORY        // 從記憶體輸入
} app_dp_in_type_t;

// Datapath 輸出類型
typedef enum {
    APP_DP_OUT_TYPE_RAW = 0,     // 原始數據
    APP_DP_OUT_TYPE_JPEG,        // JPEG 圖像
    APP_DP_OUT_TYPE_INFERENCE    // 推理結果
} app_dp_out_type_t;

// 回呼函數類型定義
typedef void (*app_frame_ready_cb_t)(uint32_t frame_addr, uint32_t frame_size);
typedef void (*app_jpeg_ready_cb_t)(uint32_t jpeg_addr, uint32_t jpeg_size);
typedef void (*app_md_ready_cb_t)(void);
typedef void (*app_voc_ready_cb_t)(void);

// Datapath 配置結構
typedef struct {
    // Sensor 設定
    uint8_t sensor_id;
    uint8_t sensor_fps;
    uint8_t sensor_format;
    uint16_t sensor_width;
    uint16_t sensor_height;
    
    // Datapath 類型
    app_dp_app_type_t dp_app_type;
    app_dp_in_type_t dp_in_type;
    app_dp_out_type_t dp_out_type;
    
    // 輸出設定
    uint8_t out_jpeg_quality;
    uint16_t out_width;
    uint16_t out_height;
    
    // 回呼函數
    app_frame_ready_cb_t frame_ready_cb;
    app_jpeg_ready_cb_t jpeg_ready_cb;
    app_md_ready_cb_t md_ready_cb;
    app_voc_ready_cb_t voc_ready_cb;
} app_dp_cfg_t;

/* --- 函數聲明 --- */

/**
 * @brief 初始化 Datapath
 * @param cfg Datapath 配置
 * @return 0 表示成功
 */
int app_datapath_init(app_dp_cfg_t *cfg);

/**
 * @brief 啟動 Datapath (開始捕捉影像)
 * @return 0 表示成功
 */
int app_datapath_start(void);

/**
 * @brief 停止 Datapath
 * @return 0 表示成功
 */
int app_datapath_stop(void);

/**
 * @brief 捕捉單張影像 (同步模式)
 * @return 0 表示成功
 */
int app_datapath_capture_one_frame(void);

/**
 * @brief 更新 JPEG 回呼函數
 * @param jpeg_cb 新的回呼函數
 * @return 0 表示成功
 */
int app_datapath_set_jpeg_callback(app_jpeg_ready_cb_t jpeg_cb);

#ifdef __cplusplus
}
#endif

#endif /* APP_DATAPATH_H_ */
