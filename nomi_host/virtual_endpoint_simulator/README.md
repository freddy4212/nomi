# Virtual Endpoint Simulator

此專案用於模擬 Himax WE2 虛擬終端，讀取 NTU RGB+D skeleton 檔案並轉換為 YOLO 17 點格式，輸出與發送相容封包。

## 專案結構

- `backend/`：FastAPI 後端 API
- `frontend/`：Quasar (Vue) 前端頁面
- `requirements.txt`：Python 套件需求
- `start.sh`：一鍵啟動後端與前端

## 功能（目前版本）

- 依檔名 `A0xx` 分類動作（A001 ~ A060）
- 瀏覽每個動作類別下的 `.skeleton` 檔案
- 選擇檔案與 frame 產生封包預覽
- 將封包送到可設定的 IP / Port
- 封包格式相容既有 `INVOKE` JSON 結構

## 使用方式

### 初始化

0. 建立本機設定檔：
   ```bash
   cp config.template.yaml config.yaml
   ```

1. 安裝後端依賴：
   ```bash
   cd config/virtual_endpoint_simulator
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. 安裝前端依賴 (需 Node.js 18+)：
   ```bash
   cd frontend
   npm install
   ```

### 啟動

開啟兩個終端機：

1. **後端 API**：
   ```bash
   ./start.sh
   # 或手動: python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```

2. **前端開發伺服器**：
   ```bash
   cd frontend
   npm run dev
   ```

- 後端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5174` (依 npm run dev 顯示為主)

## 可調整資料集路徑

目前支援三個資料集路徑，皆可在 `config.yaml` 中分別設定：

- NTU skeleton：`datasets.ntu_skeleton_dir`
- Orange4Home：`datasets.orange4home_dir`
- DALTON：`datasets.dalton_dir`

範例：

```yaml
datasets:
   ntu_skeleton_dir: "/path/to/NTU_RGB/nturgb+d_skeletons"
   orange4home_dir: "/path/to/Orange4Home/orange4home"
   dalton_dir: "/path/to/DALTON/dalton-dataset-files"
```

路徑可使用絕對路徑，或相對於 `config.yaml` 所在目錄的相對路徑。

若需改路徑，直接修改 `config.yaml`。

## LLM as a Judge 設定（YAML）

LLM Judge 現在固定從 `config.yaml` 讀取，不再讀取 `.env`。

設定位置：

- `llm.api_key`
- `llm.model_name`
- `llm.judge_model`

範例：

```yaml
llm:
   api_key: "YOUR_GEMINI_API_KEY"
   model_name: "models/gemini-3-flash-preview"
   judge_model: "gemini-2.5-flash"
```

> `config.yaml` 已設為 git ignore，不會同步；請同步 `config.template.yaml`。

（舊版環境變數寫法，保留參考）

```bash
export NTU_SKELETON_DIR="/your/path/to/nturgb+d_skeletons"
export ORANGE4HOME_DIR="/your/path/to/orange4home"
export DALTON_DIR="/your/path/to/dalton-dataset-files"
```
