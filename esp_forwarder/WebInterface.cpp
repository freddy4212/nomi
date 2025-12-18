/**
 * WebInterface.cpp - Web 設定介面類別實作
 */

#include "WebInterface.h"
#include "ConfigManager.h"
#include "WiFiManager.h"
#include "TCPForwarder.h"

// 根據通訊模式引入對應的讀取器
#if VISION_COMM_MODE == 1
#include "VisionAIReaderI2C.h"
#else
#include "VisionAIReader.h"
#endif

#include "WebPage.h"

// 靜態成員初始化
WebInterface* WebInterface::_instance = nullptr;

WebInterface::WebInterface()
    : _server(WEB_SERVER_PORT)
    , _configMgr(nullptr)
    , _wifiMgr(nullptr)
    , _tcpFwd(nullptr)
    , _visionAI(nullptr) {
    _instance = this;
}

void WebInterface::begin(ConfigManager* configMgr, WiFiManager* wifiMgr,
                         TCPForwarder* tcpFwd, VisionReaderType* visionAI) {
    _configMgr = configMgr;
    _wifiMgr = wifiMgr;
    _tcpFwd = tcpFwd;
    _visionAI = visionAI;
    
    // 設定路由
    _server.on("/", HTTP_GET, _handleRoot);
    _server.on("/api/status", HTTP_GET, _handleStatus);
    _server.on("/api/data", HTTP_GET, _handleGetData);
    _server.on("/api/wifi", HTTP_POST, _handleSetWifi);
    _server.on("/api/target", HTTP_POST, _handleSetTarget);
    _server.on("/api/reboot", HTTP_POST, _handleReboot);
    _server.onNotFound(_handleNotFound);
    
    _server.begin();
}

void WebInterface::handleClient() {
    _server.handleClient();
}

// ==================== 路由處理函數 ====================

void WebInterface::handleRoot() {
    // 發送 GZIP 壓縮的 HTML，瀏覽器會自動解壓
    _server.sendHeader("Content-Encoding", "gzip");
    _server.send_P(200, "text/html", (const char*)INDEX_HTML_GZ, INDEX_HTML_GZ_LEN);
}

void WebInterface::handleStatus() {
    StaticJsonDocument<512> doc;
    
    const AppConfig& config = _configMgr->getConfig();
    
    doc["wifi_connected"] = _wifiMgr->isConnected();
    doc["ssid"] = config.wifiSSID;
    doc["tcp_connected"] = _tcpFwd->isConnected();
    doc["target_ip"] = config.targetIP;
    doc["target_port"] = config.targetPort;
    doc["vision_connected"] = _visionAI->isResponding();
    doc["frame_count"] = _visionAI->getFrameNo();
    doc["people_count"] = _visionAI->getPeopleCount();
    
    // Uptime（毫秒轉秒）
    doc["uptime_sec"] = millis() / 1000;
    
    if (_wifiMgr->isConnected()) {
        doc["ip_address"] = _wifiMgr->getLocalIP();
    } else {
        doc["ip_address"] = _wifiMgr->getAPIP();
    }
    
    String response;
    serializeJson(doc, response);
    _server.send(200, "application/json", response);
}

void WebInterface::handleGetData() {
    const String& data = _visionAI->getJsonData();
    if (data.length() > 0) {
        _server.send(200, "application/json", data);
    } else {
        _server.send(200, "application/json", "{\"message\": \"no data\"}");
    }
}

void WebInterface::handleSetWifi() {
    if (_server.hasArg("ssid")) {
        String newSSID = _server.arg("ssid");
        String newPassword = _server.arg("password");
        
        _configMgr->saveWiFi(newSSID, newPassword);
        
        Serial.printf("[設定] WiFi 已變更: %s (重新啟動後生效)\n", newSSID.c_str());
        
        _server.send(200, "application/json", "{\"success\": true, \"message\": \"請重新啟動以套用設定\"}");
    } else {
        _server.send(400, "application/json", 
                     "{\"success\": false, \"message\": \"Missing SSID\"}");
    }
}

void WebInterface::handleSetTarget() {
    if (_server.hasArg("ip") && _server.hasArg("port")) {
        String newIP = _server.arg("ip");
        uint16_t newPort = _server.arg("port").toInt();
        
        if (newPort > 0 && newPort <= 65535) {
            // 斷開現有連線
            _tcpFwd->disconnect();
            
            // 儲存新設定
            _configMgr->saveTarget(newIP, newPort);
            
            Serial.printf("[設定] 轉發目標已變更: %s:%d\n", newIP.c_str(), newPort);
            
            _server.send(200, "application/json", "{\"success\": true}");
        } else {
            _server.send(400, "application/json", 
                         "{\"success\": false, \"message\": \"Invalid port\"}");
        }
    } else {
        _server.send(400, "application/json", 
                     "{\"success\": false, \"message\": \"Missing IP or port\"}");
    }
}

void WebInterface::handleReboot() {
    Serial.println("[系統] 收到重新啟動請求...");
    _server.send(200, "application/json", "{\"success\": true, \"message\": \"正在重新啟動...\"}");
    delay(500);
    ESP.restart();
}

void WebInterface::handleNotFound() {
    _server.send(404, "text/plain", "Not Found");
}

// ==================== 靜態包裝函數 ====================

void WebInterface::_handleRoot() {
    if (_instance) _instance->handleRoot();
}

void WebInterface::_handleStatus() {
    if (_instance) _instance->handleStatus();
}

void WebInterface::_handleGetData() {
    if (_instance) _instance->handleGetData();
}

void WebInterface::_handleSetWifi() {
    if (_instance) _instance->handleSetWifi();
}

void WebInterface::_handleSetTarget() {
    if (_instance) _instance->handleSetTarget();
}

void WebInterface::_handleReboot() {
    if (_instance) _instance->handleReboot();
}

void WebInterface::_handleNotFound() {
    if (_instance) _instance->handleNotFound();
}
