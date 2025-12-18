/**
 * WebInterface.h - Web 設定介面類別
 */

#ifndef WEB_INTERFACE_H
#define WEB_INTERFACE_H

#include <Arduino.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include "Config.h"

// 前向宣告
class ConfigManager;
class WiFiManager;
class TCPForwarder;

// 根據通訊模式選擇讀取器類型
#if VISION_COMM_MODE == 1
class VisionAIReaderI2C;
typedef VisionAIReaderI2C VisionReaderType;
#else
class VisionAIReader;
typedef VisionAIReader VisionReaderType;
#endif

/**
 * WebInterface 類別
 * 負責提供 Web 設定介面和 API
 */
class WebInterface {
public:
    WebInterface();
    
    /**
     * 初始化 Web 伺服器
     * @param configMgr 設定管理器參照
     * @param wifiMgr WiFi 管理器參照
     * @param tcpFwd TCP 轉發器參照
     * @param visionAI Vision AI 讀取器參照
     */
    void begin(ConfigManager* configMgr, WiFiManager* wifiMgr, 
               TCPForwarder* tcpFwd, VisionReaderType* visionAI);
    
    /**
     * 處理客戶端請求（在 loop 中呼叫）
     */
    void handleClient();

private:
    WebServer _server;
    
    // 元件參照
    ConfigManager* _configMgr;
    WiFiManager* _wifiMgr;
    TCPForwarder* _tcpFwd;
    VisionReaderType* _visionAI;
    
    // 路由處理函數
    void handleRoot();
    void handleStatus();
    void handleGetData();
    void handleSetWifi();
    void handleSetTarget();
    void handleReboot();
    void handleNotFound();
    
    // 靜態包裝函數（用於 WebServer 回調）
    static WebInterface* _instance;
    static void _handleRoot();
    static void _handleStatus();
    static void _handleGetData();
    static void _handleSetWifi();
    static void _handleSetTarget();
    static void _handleReboot();
    static void _handleNotFound();
};

#endif // WEB_INTERFACE_H
