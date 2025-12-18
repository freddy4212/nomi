/**
 * TCPForwarder.cpp - TCP 資料轉發類別實作
 * 
 * 使用獨立的 FreeRTOS 任務進行發送，確保 TCP 轉發永遠是最高優先級
 */

#include "TCPForwarder.h"
#include "VisionAIReader.h"

TCPForwarder::TCPForwarder()
    : _isConnected(false)
    , _lastAttempt(0)
    , _sendTaskHandle(nullptr)
    , _reader(nullptr)
    , _taskRunning(false)
    , _sentCount(0)
    , _sendErrors(0)
    , _clientMutex(nullptr)
    , _targetPort(0)
    , _wifiConnected(false) {
    
    // 創建互斥鎖
    _clientMutex = xSemaphoreCreateMutex();
}

void TCPForwarder::startSendTask(VisionAIReader* reader) {
    if (_sendTaskHandle != nullptr) {
        return;  // 任務已經在運行
    }
    
    _reader = reader;
    _taskRunning = true;
    
    // 創建最高優先級的發送任務
    // 優先級比 UART 接收還高，確保封包轉發永遠優先
    xTaskCreatePinnedToCore(
        sendTask,              // 任務函數
        "TCPSend",             // 任務名稱
        4096,                  // 堆疊大小 (bytes)
        this,                  // 參數
        configMAX_PRIORITIES - 1,  // 最高優先級
        &_sendTaskHandle,      // 任務句柄
        1                      // 固定在 Core 1（讓 WiFi 在 Core 0）
    );
    
    Serial.println("[TCP] 背景發送任務已啟動 (最高優先級, Core 1)");
}

void TCPForwarder::sendTask(void* param) {
    TCPForwarder* forwarder = static_cast<TCPForwarder*>(param);
    forwarder->sendLoop();
}

void TCPForwarder::sendLoop() {
    String jsonData;
    
    while (_taskRunning) {
        // 檢查是否有資料待發送
        if (_reader && _reader->popData(jsonData)) {
            if (jsonData.length() > 0 && _isConnected) {
                // 取得互斥鎖
                if (xSemaphoreTake(_clientMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
                    if (sendInternal(jsonData)) {
                        _sentCount++;
                    } else {
                        _sendErrors++;
                    }
                    xSemaphoreGive(_clientMutex);
                }
            }
            // 有資料時不休眠，立即處理下一筆
            taskYIELD();
        } else {
            // 沒有資料時短暫休眠
            vTaskDelay(1);
        }
        
        // 背景重連邏輯
        if (_wifiConnected && !_isConnected && _targetIP.length() > 0) {
            if (millis() - _lastAttempt > TCP_RECONNECT_INTERVAL) {
                if (xSemaphoreTake(_clientMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
                    connect(_targetIP, _targetPort);
                    xSemaphoreGive(_clientMutex);
                }
            }
        }
    }
    
    vTaskDelete(NULL);
}

bool TCPForwarder::sendInternal(const String& data) {
    // 檢查連線狀態
    if (!_client.connected()) {
        _isConnected = false;
        return false;
    }
    
    // 資料長度
    size_t totalLen = data.length();
    const char* ptr = data.c_str();
    
    // 使用較短的 timeout
    _client.setTimeout(100);
    
    // 發送資料
    size_t sent = _client.write((const uint8_t*)ptr, totalLen);
    
    if (sent != totalLen) {
        _isConnected = false;
        _client.stop();
        return false;
    }
    
    // 發送換行符結尾
    if (_client.write('\n') != 1) {
        _isConnected = false;
        _client.stop();
        return false;
    }
    
    return true;
}

bool TCPForwarder::connect(const String& ip, uint16_t port) {
    if (ip.length() == 0) {
        return false;
    }
    
    // 儲存連線參數
    _targetIP = ip;
    _targetPort = port;
    
    if (_client.connect(ip.c_str(), port)) {
        _isConnected = true;
        
        // 設定 TCP_NODELAY 減少延遲（禁用 Nagle 算法）
        _client.setNoDelay(true);
        
        Serial.println("[TCP] 已連線: " + ip + ":" + String(port));
    } else {
        _isConnected = false;
        Serial.println("[TCP] 連線失敗: " + ip + ":" + String(port));
    }
    
    _lastAttempt = millis();
    return _isConnected;
}

void TCPForwarder::disconnect() {
    if (xSemaphoreTake(_clientMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        if (_client.connected()) {
            _client.stop();
        }
        _isConnected = false;
        xSemaphoreGive(_clientMutex);
    }
}

void TCPForwarder::checkConnection(bool wifiConnected, const String& ip, uint16_t port) {
    // 更新連線參數供背景任務使用
    _wifiConnected = wifiConnected;
    _targetIP = ip;
    _targetPort = port;
    
    if (!wifiConnected) {
        _isConnected = false;
        return;
    }
    
    // 檢查連線狀態（不加鎖，只讀取）
    if (!_client.connected()) {
        _isConnected = false;
    }
}

bool TCPForwarder::send(const String& data) {
    // 這個函數現在只供測試使用
    // 正常發送由背景任務處理
    if (!_isConnected || data.length() == 0) {
        return false;
    }
    
    if (xSemaphoreTake(_clientMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        bool result = sendInternal(data);
        xSemaphoreGive(_clientMutex);
        return result;
    }
    
    return false;
}

bool TCPForwarder::isConnected() const {
    return _isConnected;
}
