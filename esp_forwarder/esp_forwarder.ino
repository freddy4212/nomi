/**
 * ESP32-C3 Grove Vision AI V2 Forwarder
 * 
 * 功能：
 * 1. 透過 UART 或 I2C 讀取 Grove Vision AI Module V2 (tflm_yolov8n_pose_reid) 的 JSON 輸出
 * 2. 透過 WiFi TCP 將資料轉發至指定的 IP 和 Port
 * 3. 提供 Web 介面設定 WiFi SSID/密碼、目標 IP 和 Port
 * 4. 支援 AP + STA 混合模式
 * 5. 使用 mDNS，可透過 http://nomi.local/ 存取設定介面
 * 6. 24/7 穩定運行：看門狗、記憶體監控、自動恢復
 * 
 * 通訊模式（在 Config.h 中設定 VISION_COMM_MODE）：
 * - UART 模式 (0): Grove 連接線使用 UART 通訊（需韌體 OUTPUT_MODE=0）
 * - I2C 模式 (1): Grove 連接線使用 I2C 通訊（需韌體 OUTPUT_MODE=1）
 * 
 * 硬體連接（I2C 模式）：
 * - Grove Vision AI V2 的 Grove 接口連接到 ESP32-C3：
 *   - GND (黑) -> XIAO GND
 *   - VCC (紅) -> XIAO 3.3V
 *   - SDA (白) -> XIAO D4 (GPIO6)
 *   - SCL (黃) -> XIAO D5 (GPIO7)
 */

#include "Config.h"
#include <esp_task_wdt.h>  // 看門狗

// 根據通訊模式選擇讀取器
#if VISION_COMM_MODE == 1
  #include "VisionAIReaderI2C.h"
  VisionAIReaderI2C visionReader;   // I2C 模式讀取器
#else
  #include <HardwareSerial.h>
  #include "VisionAIReader.h"
  HardwareSerial visionSerial(0);   // Vision AI UART
  VisionAIReader visionReader;      // UART 模式讀取器
#endif

#include "ConfigManager.h"
#include "WiFiManager.h"
#include "TCPForwarder.h"
#include "WebInterface.h"

// ==================== 全域物件 ====================
ConfigManager configManager;     // 設定管理器
WiFiManager wifiManager;         // WiFi 管理器
TCPForwarder tcpForwarder;       // TCP 轉發器
WebInterface webInterface;       // Web 介面

// ==================== 24/7 穩定性變數 ====================
static unsigned long g_startTime = 0;           // 系統啟動時間
static unsigned long g_lastHealthCheck = 0;     // 上次健康檢查時間
static uint32_t g_minFreeHeap = UINT32_MAX;     // 最小可用記憶體

// ==================== 設定函數 ====================
void setup() {
    // 初始化除錯序列埠
    Serial.begin(SERIAL_BAUD);
    delay(1000);
    
    // 記錄啟動時間
    g_startTime = millis();
    
    // 初始化看門狗 (Task Watchdog)
    esp_task_wdt_init(WATCHDOG_TIMEOUT_S, true);  // true = 逾時時重啟
    esp_task_wdt_add(NULL);  // 添加當前任務到看門狗監控
    Serial.println("[看門狗] 已啟用，逾時: " + String(WATCHDOG_TIMEOUT_S) + " 秒");
    
    Serial.println();
    Serial.println("========================================");
    Serial.println("  NOMI Agent - ESP32-C3 Vision Forwarder");
    Serial.println("  24/7 穩定版");
    Serial.println("========================================");
    
#if VISION_COMM_MODE == 1
    Serial.println("[模式] I2C 通訊");
#else
    Serial.println("[模式] UART 通訊");
#endif
    
    // 載入儲存的設定
    configManager.load();
    
    // 初始化 Vision AI
#if VISION_COMM_MODE == 1
    visionReader.begin(I2C_SDA_PIN, I2C_SCL_PIN);
#else
    visionReader.begin(visionSerial);
#endif
    
    // 取得設定
    const AppConfig& config = configManager.getConfig();
    bool hasWifiConfig = config.wifiSSID.length() > 0;
    
    // 初始化 WiFi（根據是否有設定決定模式）
    wifiManager.begin(hasWifiConfig);
    
    // 嘗試連線到已儲存的 WiFi
    if (config.wifiSSID.length() > 0) {
        wifiManager.connect(config.wifiSSID, config.wifiPassword);
    }
    
    // 設定 mDNS
    wifiManager.setupMDNS(DEVICE_NAME);
    
    // 啟動 Web 伺服器
    webInterface.begin(&configManager, &wifiManager, &tcpForwarder, &visionReader);
    
    // 啟動 TCP 背景發送任務（最高優先級）
    tcpForwarder.startSendTask(&visionReader);
    
    Serial.println("[系統] 已就緒");
}

// ==================== 主迴圈 ====================
void loop() {
    // 餵食看門狗，證明系統還活著
    esp_task_wdt_reset();
    
    const AppConfig& config = configManager.getConfig();
    
    // Web 伺服器請求
    webInterface.handleClient();
    
    // 檢查 WiFi 連線（低頻率）
    static uint32_t lastWifiCheck = 0;
    if (millis() - lastWifiCheck >= 1000) {
        wifiManager.checkConnection(config.wifiSSID, config.wifiPassword);
        lastWifiCheck = millis();
    }
    
    // 更新 TCP 連線狀態（供背景任務使用）
    tcpForwarder.checkConnection(
        wifiManager.isConnected(),
        config.targetIP,
        config.targetPort
    );
    
    // 檢查待發送隊列深度
    static uint32_t lastPendingWarning = 0;
    size_t pending = visionReader.pendingCount();
    if (pending > 3 && millis() - lastPendingWarning > 5000) {
        Serial.print("[警告] 待發送隊列積壓: ");
        Serial.println(pending);
        lastPendingWarning = millis();
    }
    
    // 定期健康檢查（每分鐘）
    if (millis() - g_lastHealthCheck > HEALTH_CHECK_INTERVAL) {
        g_lastHealthCheck = millis();
        performHealthCheck();
    }
    
    // 讓出 CPU
    delay(5);
}

// ==================== 健康檢查函數 ====================
void performHealthCheck() {
    static bool firstCheck = true;
    
    // 運行時間計算
    unsigned long uptimeSec = (millis() - g_startTime) / 1000;
    unsigned long days = uptimeSec / 86400;
    unsigned long hours = (uptimeSec % 86400) / 3600;
    unsigned long minutes = (uptimeSec % 3600) / 60;
    unsigned long seconds = uptimeSec % 60;
    
    // 記憶體檢查
    uint32_t freeHeap = ESP.getFreeHeap();
    if (freeHeap < g_minFreeHeap) {
        g_minFreeHeap = freeHeap;
    }
    
    // 第一次顯示標題
    if (firstCheck) {
        Serial.println("========== Health Check ==========");
        firstCheck = false;
    }
    
    // 運行時間
    Serial.print("Uptime: ");
    if (days > 0) {
        Serial.print(days);
        Serial.print("d ");
    }
    char timeBuf[16];
    sprintf(timeBuf, "%02lu:%02lu:%02lu", hours, minutes, seconds);
    Serial.println(timeBuf);
    
    // 記憶體
    Serial.print("Heap: ");
    Serial.print(freeHeap / 1024.0, 1);
    Serial.print("KB (min: ");
    Serial.print(g_minFreeHeap / 1024.0, 1);
    Serial.println("KB)");
    
    // 幀統計
    Serial.print("Frames: ");
    Serial.print(visionReader.getFrameCount());
    Serial.print(", dropped: ");
    Serial.println(visionReader.droppedCount());
    
    // 連線狀態
    Serial.print("WiFi: ");
    Serial.print(wifiManager.isConnected() ? "OK" : "--");
    Serial.print(", TCP: ");
    Serial.println(tcpForwarder.isConnected() ? "OK" : "--");
    
    Serial.println("===================================");
    
    // 記憶體過低警告
    if (freeHeap < MEM_WARNING_THRESHOLD) {
        Serial.println("[警告] 記憶體過低！考慮重啟...");
    }
    
    // 自動重啟檢查（如果設定了）
    #if AUTO_RESTART_HOURS > 0
    if (uptimeSec > (AUTO_RESTART_HOURS * 3600UL)) {
        Serial.println("[系統] 達到自動重啟時間，重啟中...");
        delay(1000);
        ESP.restart();
    }
    #endif
}
