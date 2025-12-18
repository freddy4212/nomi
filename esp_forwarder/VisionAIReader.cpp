/**
 * VisionAIReader.cpp - Grove Vision AI V2 資料讀取類別實作
 * 
 * 專為 tflm_yolov8_pose_reid 韌體設計
 * 使用 FreeRTOS 任務在背景持續接收 UART 資料，避免 TCP 發送阻塞導致丟幀
 * 使用固定大小 char buffer 避免動態記憶體分配，提高高速接收效率
 */

#include "VisionAIReader.h"

// 接收緩衝區大小（配合 RingBuffer 的 MAX_JSON_SIZE）
#define RX_BUFFER_SIZE 16384

VisionAIReader::VisionAIReader()
    : _serial(nullptr)
    , _lastDataTime(0)
    , _frameCount(0)
    , _frameNo(0)
    , _peopleCount(0)
    , _hasNewData(false)
    , _receiveTaskHandle(nullptr)
    , _taskRunning(false)
    , _inJson(false) {
}

void VisionAIReader::begin(HardwareSerial& serial) {
    _serial = &serial;
    
    // 設定 UART 腳位和波特率
    _serial->begin(VISION_AI_BAUD, SERIAL_8N1, VISION_RX_PIN, VISION_TX_PIN);
    _serial->setRxBufferSize(8192);  // 硬體緩衝區 8KB（降低記憶體壓力）
    
    Serial.println("[VisionAI] UART 初始化完成");
    Serial.print("[VisionAI] 波特率: ");
    Serial.println(VISION_AI_BAUD);
    Serial.print("[VisionAI] RX Pin: ");
    Serial.print(VISION_RX_PIN);
    Serial.print(", TX Pin: ");
    Serial.println(VISION_TX_PIN);
    Serial.print("[VisionAI] RX 緩衝區: 8KB, 行緩衝區: ");
    Serial.print(RX_BUFFER_SIZE / 1024);
    Serial.println("KB");
    Serial.println("[VisionAI] 等待資料中...");
    
    // 啟動背景接收任務
    startBackgroundTask();
}

void VisionAIReader::startBackgroundTask() {
    if (_receiveTaskHandle != nullptr) {
        return;  // 任務已經在運行
    }
    
    _taskRunning = true;
    
    // 創建中等優先級的接收任務
    // TCP 發送任務優先級更高，確保封包轉發優先
    // 但仍高於主迴圈，確保不會漏接資料
    xTaskCreate(
        receiveTask,           // 任務函數
        "VisionRx",            // 任務名稱
        8192,                  // 堆疊大小 (bytes) - 8KB 足夠
        this,                  // 參數
        configMAX_PRIORITIES - 2,  // 次高優先級（讓 TCP 發送優先）
        &_receiveTaskHandle    // 任務句柄
    );
    
    Serial.println("[VisionAI] 背景接收任務已啟動 (次高優先級)");
}

void VisionAIReader::receiveTask(void* param) {
    VisionAIReader* reader = static_cast<VisionAIReader*>(param);
    reader->receiveLoop();
}

void VisionAIReader::receiveLoop() {
    // 使用固定大小的 char buffer，避免動態記憶體分配
    static char lineBuffer[RX_BUFFER_SIZE];
    size_t linePos = 0;
    
    // 批量讀取緩衝區
    static char readBuffer[1024];
    
    while (_taskRunning) {
        int available = _serial->available();
        
        if (available > 0) {
            // 批量讀取，而不是逐字元
            int toRead = min(available, (int)sizeof(readBuffer));
            int bytesRead = _serial->readBytes(readBuffer, toRead);
            
            // 處理讀取的資料
            for (int i = 0; i < bytesRead; i++) {
                char c = readBuffer[i];
                
                if (c == '\n') {
                    // 行結束，推入環形緩衝區
                    if (linePos > 0) {
                        lineBuffer[linePos] = '\0';
                        _ringBuffer.push(lineBuffer, linePos);
                        _lastDataTime = millis();
                        _frameCount++;
                        
                        // 解析人數 - 從 keypoints 陣列計算
                        // keypoints 結構: [[[person1 nodes...]],[[person2 nodes...]]]
                        // 計算最外層 [[ 的數量
                        char* kpPtr = strstr(lineBuffer, "\"keypoints\":");
                        if (kpPtr) {
                            kpPtr = strchr(kpPtr, '[');
                            if (kpPtr) {
                                kpPtr++; // 跳過第一個 [
                                int count = 0;
                                int depth = 0;
                                while (*kpPtr && !(*kpPtr == ']' && depth == 0)) {
                                    if (*kpPtr == '[') {
                                        if (depth == 0) count++;
                                        depth++;
                                    } else if (*kpPtr == ']') {
                                        depth--;
                                    }
                                    kpPtr++;
                                }
                                _peopleCount = count;
                            }
                        }
                        
                        // 解析原始 frame_no
                        char* framePtr = strstr(lineBuffer, "\"frame_no\":");
                        if (framePtr) {
                            framePtr += 11;  // 跳過 "frame_no":
                            while (*framePtr == ' ' || *framePtr == '\t') framePtr++;
                            if (*framePtr >= '0' && *framePtr <= '9') {
                                _frameNo = atol(framePtr);
                            }
                        }
                    }
                    linePos = 0;
                } else if (c != '\r') {
                    // 累積資料（排除 \r）
                    if (linePos < RX_BUFFER_SIZE - 1) {
                        lineBuffer[linePos++] = c;
                    } else {
                        // 緩衝區滿，丟棄這行
                        Serial.println("[VisionAI] 警告：行過長，丟棄");
                        linePos = 0;
                    }
                }
            }
        } else {
            // 沒有資料時非常短暫地休眠
            vTaskDelay(1);
        }
    }
    
    vTaskDelete(nullptr);
}

bool VisionAIReader::process() {
    // 在新架構下，process() 只用於檢查是否有待發送的資料
    // 實際接收已經在背景任務中完成
    return _ringBuffer.count() > 0;
}

bool VisionAIReader::popData(String& data) {
    return _ringBuffer.pop(data);
}

size_t VisionAIReader::pendingCount() {
    return _ringBuffer.count();
}

unsigned long VisionAIReader::droppedCount() const {
    return _ringBuffer.dropped();
}

bool VisionAIReader::processLine(const String& line) {
    // 簡化版本：任何非空行都視為有效
    if (line.length() > 0) {
        _jsonData = line;
        _lastDataTime = millis();
        _frameCount++;
        _hasNewData = true;
        
        // 解析 frame_info 中的 count (人數)
        // 格式: "count": 1 或 "count":1
        int countIdx = line.indexOf("\"count\":");
        if (countIdx >= 0) {
            int startIdx = countIdx + 8; // 跳過 "count":
            // 跳過空格
            while (startIdx < (int)line.length() && (line[startIdx] == ' ' || line[startIdx] == '\t')) {
                startIdx++;
            }
            // 讀取數字
            int endIdx = startIdx;
            while (endIdx < (int)line.length() && line[endIdx] >= '0' && line[endIdx] <= '9') {
                endIdx++;
            }
            if (endIdx > startIdx) {
                _peopleCount = line.substring(startIdx, endIdx).toInt();
            }
        }
        
        return true;
    }
    return false;
}

const String& VisionAIReader::getJsonData() const {
    return _jsonData;
}

bool VisionAIReader::hasNewData() const {
    return _hasNewData;
}

void VisionAIReader::clearNewDataFlag() {
    _hasNewData = false;
}

bool VisionAIReader::isResponding() const {
    return (_lastDataTime > 0 && (millis() - _lastDataTime < VISION_DATA_TIMEOUT));
}

unsigned long VisionAIReader::getFrameCount() const {
    return _frameCount;
}

unsigned long VisionAIReader::getFrameNo() const {
    return _frameNo;
}

int VisionAIReader::getPeopleCount() const {
    return _peopleCount;
}
