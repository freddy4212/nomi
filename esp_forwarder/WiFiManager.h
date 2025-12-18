/**
 * WiFiManager.h - WiFi 連線管理類別
 */

#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include "Config.h"

/**
 * WiFiManager 類別
 * 負責管理 WiFi AP 和 STA 模式的連線
 * AP 只在未設定 WiFi 或連線失敗時啟動
 */
class WiFiManager {
public:
    WiFiManager();
    
    /**
     * 初始化 WiFi
     * @param hasConfig 是否已有 WiFi 設定
     */
    void begin(bool hasConfig);
    
    /**
     * 連接到指定的 WiFi 網路
     * @param ssid WiFi SSID
     * @param password WiFi 密碼
     * @return 是否連線成功
     */
    bool connect(const String& ssid, const String& password);
    
    /**
     * 檢查並維護 WiFi 連線（在 loop 中呼叫）
     * @param ssid 要連接的 SSID
     * @param password WiFi 密碼
     */
    void checkConnection(const String& ssid, const String& password);
    
    /**
     * 設定 mDNS
     * @param hostname 主機名稱
     * @return 是否設定成功
     */
    bool setupMDNS(const char* hostname);
    
    /**
     * 是否已連接到 WiFi
     */
    bool isConnected() const;
    
    /**
     * AP 是否正在運作
     */
    bool isAPActive() const;
    
    /**
     * 取得本機 IP 位址
     * @return IP 位址字串
     */
    String getLocalIP() const;
    
    /**
     * 取得 AP IP 位址
     * @return AP IP 位址字串
     */
    String getAPIP() const;

private:
    bool _isConnected;
    bool _apActive;
    unsigned long _lastAttempt;
    String _mdnsHostname;  // 儲存 hostname 以便 WiFi 重連時重新註冊
    
    void startAP();
    void stopAP();
};

#endif // WIFI_MANAGER_H
