/**
 * VisionAIReader.h - Grove Vision AI V2 資料讀取類別
 * 
 * 專為 tflm_yolov8_pose_reid 韌體設計
 * 該韌體會持續透過 UART 輸出 JSON 格式的資料，無需發送任何命令
 * 
 * 輸出格式範例：
 * \r{"frame_info": {...}, "basic_info": {...}, "image": "...", "keypoints": [...], "reid_results": [...]}\n
 * 
 * 使用 FreeRTOS 任務在背景持續接收資料，避免 TCP 發送阻塞導致資料丟失
 */

#ifndef VISION_AI_READER_H
#define VISION_AI_READER_H

#include <Arduino.h>
#include <HardwareSerial.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "Config.h"
#include "RingBuffer.h"

/**
 * VisionAIReader 類別
 * 負責從 Grove Vision AI V2 讀取 JSON 格式的推理結果
 * 
 * 注意：此版本不使用 SSCMA 庫，而是直接讀取 UART 上的 JSON 行
 */
class VisionAIReader {
public:
    VisionAIReader();
    
    /**
     * 初始化 Vision AI 連接
     * @param serial 硬體序列埠參照
     */
    void begin(HardwareSerial& serial);
    
    /**
     * 處理並讀取 Vision AI 資料（在 loop 中呼叫）
     * @return 是否有新資料
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
     * @return 是否在逾時時間內有收到資料
     */
    bool isResponding() const;
    
    /**
     * 取得幀計數
     */
    unsigned long getFrameCount() const;
    
    /**
     * 取得原始 frame_no (從封包解析)
     */
    unsigned long getFrameNo() const;
    
    /**
     * 取得當前幀的人數
     */
    int getPeopleCount() const;

    /**
     * 從緩衝區取出一筆資料（供 TCP 發送使用）
     * @param data 用於接收資料的字串
     * @return true 有資料，false 緩衝區為空
     */
    bool popData(String& data);
    
    /**
     * 取得緩衝區中待發送的資料數量
     */
    size_t pendingCount();
    
    /**
     * 取得被丟棄的幀數
     */
    unsigned long droppedCount() const;
    
    /**
     * 啟動背景接收任務
     */
    void startBackgroundTask();
    
    /**
     * 背景接收任務（供 FreeRTOS 調用）
     */
    static void receiveTask(void* param);

private:
    HardwareSerial* _serial;
    String _jsonData;
    String _lineBuffer;
    unsigned long _lastDataTime;
    unsigned long _frameCount;
    unsigned long _frameNo;
    int _peopleCount;
    bool _hasNewData;
    
    // FreeRTOS 任務和環形緩衝區
    TaskHandle_t _receiveTaskHandle;
    RingBuffer _ringBuffer;
    volatile bool _taskRunning;
    
    // 用於 JSON 行解析
    bool _inJson;  // 是否正在接收 JSON
    
    /**
     * 處理接收到的一行資料
     * @param line 接收到的行
     * @return 是否為有效的 JSON 資料
     */
    bool processLine(const String& line);
    
    /**
     * 內部接收迴圈（在背景任務中執行）
     */
    void receiveLoop();
};

#endif // VISION_AI_READER_H
