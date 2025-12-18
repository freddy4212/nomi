/**
 * TCPForwarder.h - TCP 資料轉發類別
 * 
 * 使用獨立的 FreeRTOS 任務進行發送，確保不被其他任務阻塞
 */

#ifndef TCP_FORWARDER_H
#define TCP_FORWARDER_H

#include <Arduino.h>
#include <WiFi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/semphr.h>
#include "Config.h"

// 前向宣告
class VisionAIReader;

/**
 * TCPForwarder 類別
 * 負責管理 TCP 連線和資料轉發
 * 使用獨立背景任務，以最高優先級進行發送
 */
class TCPForwarder {
public:
    TCPForwarder();
    
    /**
     * 連接到目標伺服器
     * @param ip 目標 IP 位址
     * @param port 目標埠號
     * @return 是否連線成功
     */
    bool connect(const String& ip, uint16_t port);
    
    /**
     * 斷開連線
     */
    void disconnect();
    
    /**
     * 檢查並維護 TCP 連線（在 loop 中呼叫）
     * @param wifiConnected WiFi 是否已連線
     * @param ip 目標 IP 位址
     * @param port 目標埠號
     */
    void checkConnection(bool wifiConnected, const String& ip, uint16_t port);
    
    /**
     * 發送資料（直接發送，供測試用）
     * @param data 要發送的資料字串
     * @return 是否發送成功
     */
    bool send(const String& data);
    
    /**
     * 是否已連接
     */
    bool isConnected() const;
    
    /**
     * 啟動背景發送任務
     * @param reader VisionAIReader 指標，用於取得待發送資料
     */
    void startSendTask(VisionAIReader* reader);
    
    /**
     * 取得發送統計
     */
    unsigned long getSentCount() const { return _sentCount; }
    unsigned long getSendErrors() const { return _sendErrors; }

private:
    WiFiClient _client;
    volatile bool _isConnected;
    unsigned long _lastAttempt;
    
    // 背景發送任務
    TaskHandle_t _sendTaskHandle;
    VisionAIReader* _reader;
    volatile bool _taskRunning;
    volatile unsigned long _sentCount;
    volatile unsigned long _sendErrors;
    SemaphoreHandle_t _clientMutex;  // 保護 _client 的互斥鎖
    
    // 連線參數（供背景任務重連使用）
    String _targetIP;
    uint16_t _targetPort;
    volatile bool _wifiConnected;
    
    /**
     * 背景發送任務入口
     */
    static void sendTask(void* param);
    
    /**
     * 發送迴圈
     */
    void sendLoop();
    
    /**
     * 內部發送函數（不加鎖，供 sendLoop 使用）
     */
    bool sendInternal(const String& data);
};

#endif // TCP_FORWARDER_H
