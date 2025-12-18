# ESP Forwarder - Grove Vision AI V2 資料轉發器

ESP32-C3 韌體，用於讀取 Grove Vision AI Module V2 的輸出並透過 WiFi TCP 轉發。

## 🎯 功能

1. **讀取 Grove Vision AI V2** 的 JSON 輸出（YOLOv8 Pose + ReID）
2. **TCP 轉發**至指定的 IP 和 Port
3. **Web 設定介面**可設定 WiFi、目標 IP/Port
4. **智慧 AP 模式**：只在未設定或連線失敗時啟動
5. **mDNS 支援**：`http://nomi.local/`

---

## 📁 檔案結構

```
esp_forwarder/
├── esp_forwarder.ino      # 主程式（setup/loop）
├── Config.h               # 全域配置常數
├── ConfigManager.h/.cpp   # 設定儲存（Preferences）
├── WiFiManager.h/.cpp     # WiFi 連線管理
├── TCPForwarder.h/.cpp    # TCP 資料轉發
├── VisionAIReader.h/.cpp  # Vision AI 讀取與 JSON 序列化
├── WebInterface.h/.cpp    # Web 伺服器與 API
├── data/
│   └── index.html         # 設定頁面（獨立 HTML，可編輯）
└── platformio.ini         # PlatformIO 設定
```

### 各檔案說明

| 檔案 | 說明 |
|------|------|
| `esp_forwarder.ino` | 主程式，初始化各模組並執行主迴圈 |
| `Config.h` | 定義 UART pins、WiFi 參數、mDNS 名稱等常數 |
| `ConfigManager` | 使用 ESP32 Preferences API 持久化儲存設定 |
| `WiFiManager` | 管理 WiFi STA/AP 模式切換、mDNS 服務 |
| `TCPForwarder` | TCP client 連線管理與資料發送 |
| `VisionAIReader` | 使用 SSCMA 函式庫讀取 Vision AI 資料 |
| `WebInterface` | HTTP 伺服器，提供設定頁面與 REST API |
| `data/index.html` | Web 設定頁面，存放於 LittleFS 檔案系統 |

---

## 🔧 硬體需求

- **XIAO ESP32-C3** 開發板
- **Grove Vision AI Module V2**（已燒錄 tflm_yolov8n_pose_reid）
- Grove 連接線或杜邦線

### 接線方式

| Grove Vision AI V2 | XIAO ESP32-C3 |
|---------------------|---------------|
| VCC (紅)            | 3V3           |
| GND (黑)            | GND           |
| TX (白)             | GPIO20 (RX)   |
| RX (黃)             | GPIO21 (TX)   |

---

## 🚀 刷入教學（PlatformIO）

### 1. 安裝 PlatformIO

在 VS Code 中安裝 PlatformIO 擴充套件。

### 2. 開啟專案

```bash
cd esp_forwarder
```

### 3. 如果修改了網頁，先執行轉換

```bash
python3 convert_html.py
```

### 4. 編譯並上傳韌體

```bash
pio run --target upload
```

### 5. 監控輸出

```bash
pio device monitor
```

> ✅ **只需要上傳一次！** 網頁已嵌入韌體中，不需要額外上傳 LittleFS。

---

## 🚀 刷入教學（Arduino IDE）

### 1. 安裝開發板支援

在 **檔案 > 偏好設定 > 額外的開發板管理員網址** 加入：
```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

### 2. 安裝 ESP32 開發板

- **工具 > 開發板 > 開發板管理員**
- 搜尋 "esp32" 並安裝 **esp32 by Espressif Systems**

### 3. 安裝函式庫

透過 **工具 > 管理程式庫** 安裝：
- `ArduinoJson`
- `Seeed_Arduino_SSCMA`（或從 GitHub 手動安裝）

### 4. 選擇開發板

- **工具 > 開發板 > ESP32 Arduino > XIAO_ESP32C3**

### 5. 上傳設定

| 設定項目 | 值 |
|----------|-----|
| Board | XIAO_ESP32C3 |
| Upload Speed | 921600 |
| Flash Size | 4MB |
| Partition Scheme | Default 4MB with spiffs |

### 6. 上傳韌體

點擊 **上傳** 按鈕。

> ✅ **只需要上傳一次！** 網頁已嵌入韌體中。

---

## 📝 修改網頁

如果您修改了 `data/index.html`，需要重新轉換並上傳：

```bash
# 轉換 HTML → WebPage.h
python3 convert_html.py

# 重新上傳韌體
pio run --target upload
```

或者在 Arduino IDE 中重新編譯上傳。

---

## 📱 使用方式

### 首次設定

1. **上傳韌體和網頁檔案**（見上方教學）
2. **連接 WiFi**：`NOMI-Setup`（無密碼）
3. **開啟瀏覽器**：`http://192.168.4.1/`
4. **設定 WiFi**：輸入您的 WiFi SSID 和密碼
5. **設定轉發目標**：輸入接收端的 IP 和 Port

### 連線成功後

- AP 會自動關閉
- 可透過 `http://nomi.local/` 存取設定頁面
- 資料自動透過 TCP 轉發至目標

### 連線失敗時

- AP 自動重新開啟（`NOMI-Setup`）
- 可重新設定 WiFi

---

## ❓ 常見問題

### Q: 為什麼連 AP 時不能用 `http://nomi.local/`？

**A:** mDNS（Multicast DNS）需要網路上有 DNS 解析服務。當您連接到 ESP32 的 AP 時：
- 這是一個獨立的小型網路，沒有 DNS 服務
- 您的裝置無法解析 `.local` 網域名稱
- 必須使用 IP 位址：`http://192.168.4.1/`

只有當 ESP32 連接到您的 WiFi 路由器後，mDNS 才能正常運作。

### Q: mDNS 在我的電腦上不起作用？

**A:** 確認您的裝置支援 mDNS：
- **macOS**：原生支援
- **iOS**：原生支援
- **Windows**：需安裝 [Bonjour](https://support.apple.com/kb/DL999)
- **Android**：大部分新版本支援
- **Linux**：需安裝 avahi-daemon

### Q: 如何查看 ESP32 的 IP 位址？

**A:** 透過 Serial Monitor 查看輸出，或登入路由器管理頁面查看連接裝置。

---

## 📊 資料格式

TCP 發送的 JSON 格式（每筆資料以換行符結尾）：

```json
{
  "perf": {
    "preprocess": 10,
    "inference": 150,
    "postprocess": 5
  },
  "boxes": [
    {"target": 0, "score": 85, "x": 100, "y": 50, "w": 200, "h": 300}
  ],
  "keypoints": [
    {
      "box": {"target": 0, "score": 85, "x": 100, "y": 50, "w": 200, "h": 300},
      "points": [[120, 80], [130, 85], ...]
    }
  ],
  "timestamp": 123456
}
```

---

## 📝 修改設定

編輯 `Config.h` 可修改：

```cpp
#define DEVICE_NAME     "nomi"          // mDNS 名稱
#define AP_SSID         "NOMI-Setup"    // AP WiFi 名稱
#define VISION_AI_BAUD  921600          // Vision AI 波特率
#define VISION_RX_PIN   20              // RX 腳位
#define VISION_TX_PIN   21              // TX 腳位
```

---

## 📄 License

MIT License
