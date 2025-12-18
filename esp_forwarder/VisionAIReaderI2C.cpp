/**
 * VisionAIReaderI2C.cpp - Grove Vision AI V2 I2C 資料讀取實作
 */

#include "VisionAIReaderI2C.h"

VisionAIReaderI2C::VisionAIReaderI2C()
    : _lastPollTime(0)
    , _lastDataTime(0)
    , _frameCount(0)
    , _hasNewData(false)
    , _deviceFound(false)
{
}

void VisionAIReaderI2C::begin(int sda, int scl) {
    Serial.println("[I2C] 初始化 I2C Master...");
    Serial.printf("[I2C] SDA: GPIO%d, SCL: GPIO%d\n", sda, scl);
    Serial.printf("[I2C] 目標地址: 0x%02X\n", VISION_I2C_ADDR);
    
    // 啟用內部上拉電阻 (如果沒有外部上拉電阻)
    pinMode(sda, INPUT_PULLUP);
    pinMode(scl, INPUT_PULLUP);
    delay(10);
    
    // 初始化 I2C (較低頻率以提高穩定性)
    Wire.begin(sda, scl, 50000);  // 降低到 50kHz
    Wire.setTimeOut(200);  // 設定逾時
    
    delay(100);  // 等待 I2C 穩定
    
    // 掃描 I2C 總線
    _deviceFound = scanI2C();
    
    if (_deviceFound) {
        Serial.println("[I2C] 已找到 Vision AI V2");
    } else {
        Serial.println("[I2C] 警告: 未找到 Vision AI V2，請檢查接線");
        Serial.println("[I2C] 請確認:");
        Serial.println("      1. Grove 連接線已正確插入");
        Serial.println("      2. Vision AI 韌體已設定為 I2C 輸出模式");
        Serial.println("      3. SDA/SCL 腳位是否正確 (可能需要交換)");
    }
}

bool VisionAIReaderI2C::scanI2C() {
    Serial.println("[I2C] 掃描 I2C 總線...");
    
    bool found = false;
    
    for (uint8_t addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        uint8_t error = Wire.endTransmission();
        
        if (error == 0) {
            Serial.printf("[I2C] 找到裝置: 0x%02X", addr);
            if (addr == VISION_I2C_ADDR) {
                Serial.print(" (Vision AI V2)");
                found = true;
            }
            Serial.println();
        }
    }
    
    if (!found) {
        Serial.println("[I2C] 未找到任何裝置");
    }
    
    return found;
}

bool VisionAIReaderI2C::process() {
    unsigned long now = millis();
    
    // 根據輪詢間隔讀取資料
    if (now - _lastPollTime < I2C_POLL_INTERVAL_MS) {
        return false;
    }
    _lastPollTime = now;
    
    // 嘗試從 I2C Slave 讀取資料
    int bytesRead = readFromSlave();
    
    if (bytesRead > 0) {
        _lastDataTime = now;
        
        // 嘗試解析完整的 JSON
        if (parseJsonFromBuffer()) {
            _hasNewData = true;
            _frameCount++;
            return true;
        }
    }
    
    return false;
}

int VisionAIReaderI2C::readFromSlave() {
    // 請求資料
    int bytesReceived = Wire.requestFrom((uint8_t)VISION_I2C_ADDR, 
                                          (uint8_t)I2C_READ_CHUNK_SIZE);
    
    if (bytesReceived == 0) {
        return 0;
    }
    
    int totalRead = 0;
    
    while (Wire.available()) {
        char c = Wire.read();
        
        // 忽略空字元
        if (c == 0) {
            continue;
        }
        
        _receiveBuffer += c;
        totalRead++;
    }
    
    return totalRead;
}

bool VisionAIReaderI2C::parseJsonFromBuffer() {
    // 尋找完整的 JSON 行 (以 \r{ 開始，\n 結束)
    
    int startIdx = -1;
    int endIdx = -1;
    int braceCount = 0;
    bool inJson = false;
    
    for (int i = 0; i < _receiveBuffer.length(); i++) {
        char c = _receiveBuffer.charAt(i);
        
        if (c == '{') {
            if (!inJson) {
                startIdx = i;
                inJson = true;
            }
            braceCount++;
        } else if (c == '}') {
            braceCount--;
            if (inJson && braceCount == 0) {
                endIdx = i;
                break;
            }
        }
    }
    
    if (startIdx >= 0 && endIdx > startIdx) {
        // 提取完整的 JSON
        _jsonData = _receiveBuffer.substring(startIdx, endIdx + 1);
        
        // 清除已處理的資料
        _receiveBuffer = _receiveBuffer.substring(endIdx + 1);
        
        // 防止緩衝區無限增長
        if (_receiveBuffer.length() > 4096) {
            _receiveBuffer = _receiveBuffer.substring(_receiveBuffer.length() - 2048);
        }
        
        return true;
    }
    
    // 防止緩衝區無限增長 (沒有找到 JSON 時也要清理)
    if (_receiveBuffer.length() > 8192) {
        // 保留最後一部分，可能是不完整的 JSON
        _receiveBuffer = _receiveBuffer.substring(_receiveBuffer.length() - 4096);
    }
    
    return false;
}

const String& VisionAIReaderI2C::getJsonData() const {
    return _jsonData;
}

bool VisionAIReaderI2C::hasNewData() const {
    return _hasNewData;
}

void VisionAIReaderI2C::clearNewDataFlag() {
    _hasNewData = false;
}

bool VisionAIReaderI2C::isResponding() const {
    // 如果在過去 5 秒內有收到資料，則認為有回應
    return (millis() - _lastDataTime) < 5000 || _deviceFound;
}

unsigned long VisionAIReaderI2C::getFrameCount() const {
    return _frameCount;
}
