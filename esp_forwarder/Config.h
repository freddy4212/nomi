/**
 * Config.h - 全域配置常數
 */

#ifndef CONFIG_H
#define CONFIG_H

// ==================== 通訊模式選擇 ====================
// 選擇 Vision AI 的通訊模式：
//   0 = UART 模式 (透過 XIAO Connector 的 UART)
//   1 = I2C 模式 (透過 Grove 連接線的 I2C，需要 Grove 排線)
#define VISION_COMM_MODE    0  // <-- 使用 UART 模式 (XIAO Connector)

// ==================== 裝置設定 ====================
#define DEVICE_NAME         "nomi-setup"        // mDNS 名稱 (nomi-setup.local)
#define AP_SSID             "NOMI-Setup"        // AP 模式的 SSID
#define AP_PASSWORD         ""                  // AP 模式密碼 (空字串 = 開放網路)

// ==================== 網路設定 ====================
#define WEB_SERVER_PORT     80
#define DEFAULT_TARGET_IP   "192.168.1.100"
#define DEFAULT_TARGET_PORT 8000

// ==================== 序列埠設定 ====================
#define SERIAL_BAUD         115200
#define VISION_AI_BAUD      921600              // Grove Vision AI V2 預設波特率

// ==================== UART 腳位定義 (ESP32-C3 XIAO) ====================
// XIAO ESP32C3 硬體 UART 腳位：
//   D6 = GPIO21 = 硬體 TX
//   D7 = GPIO20 = 硬體 RX
// 
// XIAO Connector 連接方式 (ESP32C3 插在 Grove Vision AI V2 上):
//   Grove Vision AI V2 的 XIAO Connector TX/RX 與 ESP32C3 的 TX/RX 位置相反
//   所以會自動形成正確的交叉連接：
//     - WE2 TX (PB7) -> ESP32 RX (GPIO20/D7)
//     - WE2 RX (PB6) -> ESP32 TX (GPIO21/D6)
//
// ESP32 接收資料用 GPIO20 (D7), 發送資料用 GPIO21 (D6)
#define VISION_RX_PIN       20                  // D7/GPIO20 (硬體 RX), 接收 WE2 TX 的資料
#define VISION_TX_PIN       21                  // D6/GPIO21 (硬體 TX), 發送給 WE2 RX

// ==================== I2C 腳位定義 (ESP32-C3 XIAO) ====================
// Grove 連接線在 I2C 模式下的接線:
//   Grove Vision AI V2 的 Grove 接口:
//     - GND (黑) -> XIAO GND
//     - VCC (紅) -> XIAO 3.3V
//     - SDA (白) -> XIAO D4 (GPIO6) - I2C SDA
//     - SCL (黃) -> XIAO D5 (GPIO7) - I2C SCL
#define I2C_SDA_PIN         6                   // D4/GPIO6, I2C SDA
#define I2C_SCL_PIN         7                   // D5/GPIO7, I2C SCL
#define VISION_I2C_ADDR     0x62                // Vision AI I2C Slave 地址

// ==================== 時間間隔設定 ====================
#define WIFI_RETRY_INTERVAL     30000           // WiFi 重試間隔 (30 秒)
#define TCP_RECONNECT_INTERVAL  3000            // TCP 重連間隔 (3 秒)
#define VISION_DATA_TIMEOUT     5000            // Vision AI 資料逾時 (5 秒)

// ==================== 24/7 穩定性設定 ====================
#define WATCHDOG_TIMEOUT_S      30              // 看門狗逾時 (30 秒)
#define HEALTH_CHECK_INTERVAL   60000           // 健康檢查間隔 (1 分鐘)
#define MEM_WARNING_THRESHOLD   10000           // 記憶體警告閾值 (10KB)
#define AUTO_RESTART_HOURS      0               // 自動重啟間隔 (0 = 關閉, 單位: 小時)

// ==================== 儲存設定 ====================
#define PREFERENCES_NAMESPACE   "nomi"

#endif // CONFIG_H
