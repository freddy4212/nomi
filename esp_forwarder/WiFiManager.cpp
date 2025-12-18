/**
 * WiFiManager.cpp - WiFi 連線管理類別實作
 */

#include "WiFiManager.h"

WiFiManager::WiFiManager() 
    : _isConnected(false)
    , _apActive(false)
    , _lastAttempt(0) {
}

void WiFiManager::begin(bool hasConfig) {
    if (hasConfig) {
        WiFi.mode(WIFI_STA);
    } else {
        WiFi.mode(WIFI_AP);
        startAP();
    }
}

void WiFiManager::startAP() {
    if (_apActive) return;
    
    if (_isConnected) {
        WiFi.mode(WIFI_AP_STA);
    } else {
        WiFi.mode(WIFI_AP);
    }
    
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    IPAddress apIP = WiFi.softAPIP();
    
    _apActive = true;
    
    Serial.printf("[WiFi] AP 已啟動: %s (%s)\n", AP_SSID, apIP.toString().c_str());
}

void WiFiManager::stopAP() {
    if (!_apActive) return;
    
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
    
    _apActive = false;
    
    Serial.println("[WiFi] AP 已關閉");
}

bool WiFiManager::connect(const String& ssid, const String& password) {
    if (ssid.length() == 0) {
        startAP();
        return false;
    }
    
    Serial.printf("[WiFi] 連線中: %s", ssid.c_str());
    
    if (_apActive) {
        WiFi.mode(WIFI_AP_STA);
    } else {
        WiFi.mode(WIFI_STA);
    }
    
    WiFi.begin(ssid.c_str(), password.c_str());
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        _isConnected = true;
        Serial.printf(" OK (%s)\n", WiFi.localIP().toString().c_str());
        stopAP();
    } else {
        _isConnected = false;
        Serial.println(" 失敗");
        startAP();
    }
    
    _lastAttempt = millis();
    return _isConnected;
}

void WiFiManager::checkConnection(const String& ssid, const String& password) {
    if (WiFi.status() == WL_CONNECTED) {
        if (!_isConnected) {
            _isConnected = true;
            Serial.printf("[WiFi] 已重新連線: %s\n", WiFi.localIP().toString().c_str());
            stopAP();
            
            // WiFi 重連後重新註冊 mDNS
            if (_mdnsHostname.length() > 0) {
                setupMDNS(_mdnsHostname.c_str());
            }
        }
    } else {
        if (_isConnected) {
            _isConnected = false;
            Serial.println("[WiFi] 連線中斷");
            startAP();
        }
        
        if (millis() - _lastAttempt > WIFI_RETRY_INTERVAL && ssid.length() > 0) {
            connect(ssid, password);
        }
    }
}

bool WiFiManager::setupMDNS(const char* hostname) {
    _mdnsHostname = hostname;  // 儲存 hostname 以便重連時使用
    
    MDNS.end();  // 先結束舊的 mDNS 服務
    
    if (MDNS.begin(hostname)) {
        Serial.printf("[mDNS] http://%s.local/\n", hostname);
        MDNS.addService("http", "tcp", WEB_SERVER_PORT);
        return true;
    }
    Serial.println("[mDNS] 啟動失敗");
    return false;
}

bool WiFiManager::isConnected() const {
    return _isConnected;
}

bool WiFiManager::isAPActive() const {
    return _apActive;
}

String WiFiManager::getLocalIP() const {
    return WiFi.localIP().toString();
}

String WiFiManager::getAPIP() const {
    return WiFi.softAPIP().toString();
}
