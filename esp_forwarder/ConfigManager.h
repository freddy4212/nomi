/**
 * ConfigManager.h - 設定儲存管理類別
 */

#ifndef CONFIG_MANAGER_H
#define CONFIG_MANAGER_H

#include <Arduino.h>
#include <Preferences.h>
#include "Config.h"

/**
 * 設定資料結構
 */
struct AppConfig {
    String wifiSSID;
    String wifiPassword;
    String targetIP;
    uint16_t targetPort;
};

/**
 * ConfigManager 類別
 * 負責管理應用程式設定的儲存與載入
 */
class ConfigManager {
public:
    ConfigManager();
    
    /**
     * 載入所有設定
     */
    void load();
    
    /**
     * 儲存 WiFi 設定
     * @param ssid WiFi SSID
     * @param password WiFi 密碼
     */
    void saveWiFi(const String& ssid, const String& password);
    
    /**
     * 儲存目標伺服器設定
     * @param ip 目標 IP 位址
     * @param port 目標埠號
     */
    void saveTarget(const String& ip, uint16_t port);
    
    /**
     * 取得目前設定
     * @return 設定資料結構的參照
     */
    const AppConfig& getConfig() const;
    
    /**
     * 取得設定的可修改參照（用於直接更新）
     */
    AppConfig& config();

private:
    AppConfig _config;
    Preferences _preferences;
};

#endif // CONFIG_MANAGER_H
