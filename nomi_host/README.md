# NOMI Home Agent (Host Side)

**NOMI**: Non-verbal Observation & Minimal Interaction Home Agent.

本專案為 NOMI 系統的 **Host 端**（主機端）程式，負責運行於家庭伺服器或電腦上，處理來自 Device 端（WiseEye2）的感知資料。

## 系統架構

NOMI 系統分為兩端：

1.  **Device 端 (Firmware)**: 運行於 WiseEye2 (Himax WE2) 與 ESP32 上，負責邊緣運算與資料轉發。
2.  **Host 端 (Software)**: 本專案，負責接收資料、記憶儲存與高層推論。

本專案（Host 端）採用三層架構設計：

1.  **感知層 (Observation Layer)**: 負責接收來自 WiseEye2 等裝置的感測資料（如骨架、影像特徵），並進行初步處理與動作識別。
    *   目錄: `observation_layer/`
2.  **記憶層 (Memory Layer)**: 負責儲存與檢索長期記憶，使用 PostgreSQL + TimescaleDB + pgvector 進行向量化儲存。
    *   目錄: `memory_layer/`
3.  **推論層 (Inference Layer)**: (開發中) 負責根據感知與記憶進行決策與推論。

此外，本專案包含一個裝置模擬器，用於測試與開發：
*   **裝置模擬器 (Device Simulator)**: 模擬 WiseEye2 裝置發送骨架與特徵資料。
    *   目錄: `device_simulator/`

## 安裝與使用

### 環境需求

請參考 `requirements.txt` 安裝所需套件：

```bash
pip install -r requirements.txt
```

### 各模組說明

請參閱各子目錄下的 `README.md` 以獲取詳細說明：

*   [感知層 (Observation Layer)](observation_layer/README.md)
*   [記憶層 (Memory Layer)](memory_layer/README.md)
*   [裝置模擬器 (Device Simulator)](device_simulator/README.md)

## 授權

[LICENSE](LICENSE)
