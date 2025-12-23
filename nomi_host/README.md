# NOMI Host (Home Agent)

**NOMI**: Non-verbal Observation & Minimal Interaction Home Agent.

本專案為 NOMI 系統的 **Host 端**（主機端）程式，負責運行於家庭伺服器或電腦上，處理來自 Device 端（WiseEye2）的感知資料，並提供視覺化操作介面。

## 系統架構

NOMI Host 端採用模組化架構設計，由 **Control Panel** 統一調度：

1.  **Control Panel (控制面板)**: 系統的核心樞紐。
    *   **Backend (Orchestrator)**: 負責啟動與管理感知層、記憶層與推論層，並提供 WebSocket 服務供前端串接。
    *   **Frontend (Web Console)**: 基於 Vue 3 + Vite 的現代化操作介面，提供系統監控、向量錄入與設定功能。
    *   目錄: `control_panel/`
2.  **感知層 (Observation Layer)**: 負責接收來自 WiseEye2 的骨架與影像資料，進行動作識別 (MMAction2)。
    *   目錄: `observation_layer/`
3.  **記憶層 (Memory Layer)**: 負責長期記憶儲存，使用 PostgreSQL + TimescaleDB + pgvector。
    *   目錄: `memory_layer/`
4.  **裝置模擬器 (Device Simulator)**: 用於開發測試，模擬 WiseEye2 發送資料。
    *   目錄: `device_simulator/`

---

## 🚀 快速開始 (Quick Start)

### 1. 環境準備

*   **Python**: 3.10 或以上版本
*   **Node.js**: 16.0 或以上版本 (用於前端)
*   **PostgreSQL**: 需安裝 TimescaleDB 與 pgvector 擴充套件 (用於記憶層)
*   **Git Submodules**: 確保已下載所有子模組
    ```bash
    git submodule update --init --recursive
    ```

### 2. 安裝後端依賴

在專案根目錄 (`nomi_host/`) 下執行：

```bash
# 安裝 Python 套件
pip install -r requirements.txt
```

### 3. 啟動系統 (Control Panel)

現在您只需要啟動 Control Panel 的後端與前端，系統會自動管理其他子模組。

**終端機 A - 啟動後端 Orchestrator**
這將會自動啟動感知層接收資料，並開啟 WebSocket 服務 (Port 8000)。
```bash
# 確保在 nomi_host 目錄下
python -m control_panel.backend.main
```

**終端機 B - 啟動前端 Web Console**

```bash
# 進入前端目錄
cd control_panel/frontend

# 安裝依賴 (初次執行需執行)
npm install

# 啟動開發伺服器
npm run dev
```

啟動後，請用瀏覽器開啟顯示的網址 (通常為 `http://localhost:5173`)。

### 4. (選用) 啟動裝置模擬器

若無實體 WiseEye2 裝置，可使用模擬器發送測試資料。

**終端機 C - 啟動模擬器**
```bash
python -m device_simulator.main
```
在模擬器視窗中點擊 **「開始發送」** 即可。

---

## 📂 目錄結構說明

*   `control_panel/`: **控制面板**
    *   `backend/`: 系統編排器 (Orchestrator)，使用 FastAPI 管理各層級生命週期。
    *   `frontend/`: 前端專案 (Vue 3)，原 `web_console`。
*   `observation_layer/`: **感知核心** (Python)
    *   整合 MMAction2 動作識別模型。
    *   處理 TCP 資料串流。
*   `memory_layer/`: **記憶核心** (Python)
    *   管理 PostgreSQL 資料庫連線。
    *   處理 ReID 特徵向量的儲存與檢索。
*   `device_simulator/`: **裝置模擬器** (Python)
    *   使用 YOLO-Pose 從影片產生骨架資料，模擬真實裝置行為。

## 授權

[LICENSE](LICENSE)
