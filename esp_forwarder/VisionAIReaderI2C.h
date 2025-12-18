/**
 * VisionAIReaderI2C.h - Grove Vision AI V2 I2C 資料讀取類別
 * 
 * 專為 tflm_yolov8_pose_reid 韌體 (I2C 輸出模式) 設計
 * 
 * Grove Vision AI V2 作為 I2C Slave，ESP32 作為 I2C Master 來請求資料
 * 
 * I2C 接線 (Grove 連接器):
 *   - PA2 (SCL) -> ESP32 SCL (GPIO6 預設)
 *   - PA3 (SDA) -> ESP32 SDA (GPIO7 預設)
 *   - GND -> GND
 *   - 3.3V -> 3.3V
 * 
 * I2C 地址: 0x62 (與 SSCMA 相同)
 */

#ifndef VISION_AI_READER_I2C_H
#define VISION_AI_READER_I2C_H

#include <Arduino.h>
#include <Wire.h>
#include "Config.h"

// I2C 設定 (腳位和地址從 Config.h 讀取，這裡定義預設值供備用)
#ifndef VISION_I2C_ADDR
#define VISION_I2C_ADDR      0x62    // Grove Vision AI V2 I2C 地址
#endif
#ifndef I2C_SDA_PIN
#define I2C_SDA_PIN          6       // ESP32-C3 I2C SDA 腳位 (D4/GPIO6)
#endif
#ifndef I2C_SCL_PIN
#define I2C_SCL_PIN          7       // ESP32-C3 I2C SCL 腳位 (D5/GPIO7)
#endif
#define I2C_FREQ             100000  // I2C 頻率 100kHz
#define I2C_READ_CHUNK_SIZE  32      // 每次讀取的最大位元組數 (減小避免問題)
#define I2C_READ_TIMEOUT_MS  100     // 讀取逾時時間
#define I2C_POLL_INTERVAL_MS 100     // 輪詢間隔 (增加以減少錯誤)

/**
 * VisionAIReaderI2C 類別
 * 使用 I2C Master 模式從 Grove Vision AI V2 讀取 JSON 資料
 */
class VisionAIReaderI2C {
public:
    VisionAIReaderI2C();
    
    /**
     * 初始化 I2C 連接
     * @param sda SDA 腳位 (預設 GPIO7)
     * @param scl SCL 腳位 (預設 GPIO6)
     */
    void begin(int sda = I2C_SDA_PIN, int scl = I2C_SCL_PIN);
    
    /**
     * 處理並讀取 Vision AI 資料（在 loop 中呼叫）
     * @return 是否有新的完整 JSON 資料
     */
    bool process();
    
    /**
     * 取得最新的 JSON 資料
     * @return JSON 字串
     */
    const String& getJsonData() const;
    
    /**
     * 是否有新資料待處理
     */
    bool hasNewData() const;
    
    /**
     * 清除新資料旗標
     */
    void clearNewDataFlag();
    
    /**
     * 檢查 Vision AI 是否有回應
     * @return 是否偵測到 I2C 裝置
     */
    bool isResponding() const;
    
    /**
     * 取得幀計數
     */
    unsigned long getFrameCount() const;
    
    /**
     * 掃描 I2C 總線，尋找裝置
     * @return 是否找到 Vision AI
     */
    bool scanI2C();

private:
    String _jsonData;           // 完整的 JSON 資料
    String _receiveBuffer;      // 接收緩衝區 (累積中)
    unsigned long _lastPollTime;
    unsigned long _lastDataTime;
    unsigned long _frameCount;
    bool _hasNewData;
    bool _deviceFound;
    
    /**
     * 從 I2C Slave 讀取資料
     * @return 讀取到的位元組數
     */
    int readFromSlave();
    
    /**
     * 解析接收緩衝區中的 JSON
     * @return 是否找到完整的 JSON
     */
    bool parseJsonFromBuffer();
};

#endif // VISION_AI_READER_I2C_H
