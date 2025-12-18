/**
 * ConfigManager.cpp - 設定儲存管理類別實作
 */

#include "ConfigManager.h"

ConfigManager::ConfigManager() {
    // 設定預設值
    _config.wifiSSID = "";
    _config.wifiPassword = "";
    _config.targetIP = DEFAULT_TARGET_IP;
    _config.targetPort = DEFAULT_TARGET_PORT;
}

void ConfigManager::load() {
    _preferences.begin(PREFERENCES_NAMESPACE, true);  // 唯讀模式
    
    _config.wifiSSID = _preferences.getString("ssid", "");
    _config.wifiPassword = _preferences.getString("password", "");
    _config.targetIP = _preferences.getString("targetIP", DEFAULT_TARGET_IP);
    _config.targetPort = _preferences.getUShort("targetPort", DEFAULT_TARGET_PORT);
    
    _preferences.end();
    
    Serial.println("[ConfigManager] 已載入設定:");
    Serial.println("  SSID: " + _config.wifiSSID);
    Serial.println("  Target: " + _config.targetIP + ":" + String(_config.targetPort));
}

void ConfigManager::saveWiFi(const String& ssid, const String& password) {
    _preferences.begin(PREFERENCES_NAMESPACE, false);
    _preferences.putString("ssid", ssid);
    _preferences.putString("password", password);
    _preferences.end();
    
    _config.wifiSSID = ssid;
    _config.wifiPassword = password;
    
    Serial.println("[ConfigManager] WiFi 設定已儲存");
}

void ConfigManager::saveTarget(const String& ip, uint16_t port) {
    _preferences.begin(PREFERENCES_NAMESPACE, false);
    _preferences.putString("targetIP", ip);
    _preferences.putUShort("targetPort", port);
    _preferences.end();
    
    _config.targetIP = ip;
    _config.targetPort = port;
    
    Serial.println("[ConfigManager] 轉發設定已儲存: " + ip + ":" + String(port));
}

const AppConfig& ConfigManager::getConfig() const {
    return _config;
}

AppConfig& ConfigManager::config() {
    return _config;
}
