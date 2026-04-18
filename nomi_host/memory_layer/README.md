# NOMI Memory Layer（家庭代理人記憶層）

這是 **Home Agent** 家庭代理人框架的記憶層模組，負責儲存來自感知層（Receiver）的資料。

## 架構概述

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Home Agent Framework                            │
├─────────────────┬─────────────────────┬─────────────────────────────┤
│   感知層         │      記憶層          │         推論層              │
│   Perception    │      Memory         │        Inference            │
├─────────────────┼─────────────────────┼─────────────────────────────┤
│                 │                     │                             │
│ WiseEye2 硬體   │  ┌───────────────┐  │  ┌─────────────────────┐   │
│      ↓          │  │ MemoryLayer   │  │  │ LLM (GPT/Claude)    │   │
│ ESP32 Forwarder │  │   Thread      │  │  │                     │   │
│      ↓          │  │      ↓        │  │  │ SQL 查詢能力        │   │
│ device_simulator   │  │ PostgreSQL    │→ │  │ 自然語言推理        │   │
│      ↓ (TCP)    │  │ + TimescaleDB │  │  │ 智慧助理回應        │   │
│ observation_layer │→ │ + pgvector    │  │  └─────────────────────┘   │
│ (主要感知層)     │  │               │  │                             │
│      ↓          │  └───────────────┘  │                             │
│ memory_bridge   │                     │                             │
└─────────────────┴─────────────────────┴─────────────────────────────┘
```

### 模組說明

| 模組 | 位置 | 說明 |
|------|------|------|
| **observation_layer** | `observation_layer/` | **主要感知層**，透過網路接收骨架資料 |
| **we_mma_2** | `we_mma_2/` | 核心框架，包含動作識別、骨架處理等核心功能 |
| **device_simulator** | `../nomi_evaluation/device_simulator/` | 發送端，從攝影機/測試來源發送骨架資料 |
| **memory_bridge** | `we_mma_2/memory_bridge.py` | 橋接模組，連接感知層與記憶層 |
| **memory_layer** | `memory_layer/` | 記憶層核心，資料庫管理與持久化 |

> **注意**：未來 `we_mma_2` 的核心功能將併入 `observation_layer`，簡化架構。

## 資料流

1. **感知層** 接收 WiseEye2 的骨架和動作資料
2. **MemoryBridge** 將識別結果包裝成 `PerceptionEvent`，打上 Unix 時間戳
3. 事件進入 **MemoryQueue**（Python `queue.Queue`）
4. **MemoryLayer** 執行緒從隊列消費，批次寫入資料庫
5. **InferenceQueue** 用於未來推論層訂閱事件

## 安裝與設定

> **重要**：記憶層**僅支援** PostgreSQL + TimescaleDB + pgvector。
> 感知層的向量錄入功能已完全整合至記憶層，不再使用本地 SQLite。

### 必要條件

- PostgreSQL 15+
- TimescaleDB 擴展
- pgvector 擴展
- Python psycopg2-binary

---

## 方式一：Podman 容器化（推薦）

使用容器可快速部署完整的 PostgreSQL + TimescaleDB + pgvector 環境。

### 1. 安裝 Podman

**macOS:**
```bash
brew install podman podman-compose
podman machine init
podman machine start
```

**Ubuntu/Debian:**
```bash
sudo apt install podman podman-compose
```

### 2. 啟動容器

```bash
cd memory_layer/container
./start.sh
```

腳本會自動：
- 拉取 `timescale/timescaledb-ha:pg15-latest` 映像（已內建 pgvector）
- 啟動容器並初始化資料庫
- 啟用 TimescaleDB 和 pgvector 擴展
- 顯示連線資訊

### 3. 驗證容器狀態

```bash
# 查看容器狀態
podman ps

# 查看日誌
podman logs home_agent_db

# 連線到資料庫
podman exec -it home_agent_db psql -U home_agent -d home_agent
```

### 4. 常用容器操作

```bash
# 停止容器（保留資料）
cd memory_layer/container
./stop.sh

# 完全刪除（包含資料）
podman-compose down -v

# 重新啟動
podman-compose restart
```

### 容器連線資訊

| 項目 | 值 |
|------|-----|
| Host | `localhost` |
| Port | `5432` |
| Database | `home_agent` |
| User | `home_agent` |
| Password | `home_agent_pwd` |
| 連線字串 | `postgresql://home_agent:home_agent_pwd@localhost:5432/home_agent` |

---

## 方式二：本機安裝

如果不使用容器，可以手動安裝各組件。

### 1. 安裝 PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. 安裝 TimescaleDB

**macOS:**
```bash
brew tap timescale/tap
brew install timescaledb
timescaledb-tune --pg-config=/opt/homebrew/opt/postgresql@15/bin/pg_config
brew services restart postgresql@15
```

**Ubuntu:**
```bash
sudo add-apt-repository ppa:timescale/timescaledb-ppa
sudo apt update
sudo apt install timescaledb-2-postgresql-15
sudo timescaledb-tune
sudo systemctl restart postgresql
```

### 3. 安裝 pgvector

**macOS:**
```bash
brew install pgvector
```

**Ubuntu (編譯安裝):**
```bash
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### 4. 建立資料庫與使用者

```bash
# 建立使用者
sudo -u postgres psql -c "CREATE USER home_agent WITH PASSWORD 'home_agent_pwd';"

# 建立資料庫
sudo -u postgres createdb -O home_agent home_agent

# 連接並啟用擴展
sudo -u postgres psql -d home_agent -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
sudo -u postgres psql -d home_agent -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 授權
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE home_agent TO home_agent;"
```

---

## Python 依賴安裝

不論使用哪種方式部署資料庫，都需要安裝 Python 套件：

```bash
pip install psycopg2-binary
```

## 修改配置（可選）

編輯 `memory_layer/config.py`：

```python
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "home_agent"
    user: str = "home_agent"
    password: str = "home_agent_pwd"  # ← 修改為你的密碼
```

---

## 狀態指示

Receiver 的頂部工具列會顯示記憶層連線狀態：

| 狀態 | 顏色 | 說明 |
|------|------|------|
| **🗄 PostgreSQL ✓ (N)** | 🟢 綠色 | 已連線，N = 已記錄事件數 |
| **🗄 PostgreSQL: ✗ 未連線** | 🔴 紅色 | 連線失敗（資料庫未啟動或配置錯誤） |
| **🗄 PostgreSQL: 待機** | 🟠 橘色 | 已初始化但尚未啟動 |
| **🗄 記憶層: 未安裝** | ⚪ 灰色 | `memory_layer` 模組不存在 |

---

## 資料視覺化工具 (GUI)

我們提供了一個獨立的 GUI 工具，讓你隨時查看資料庫中的歷史記錄與成員狀態。

### 啟動方式

```bash
cd memory_layer
python main.py
```

### 功能說明
- **系統狀態**：顯示當前資料庫連線資訊與統計數據。
- **最近事件**：顯示最近 1 小時內的感知事件（Telemetry）。
- **成員即時狀態**：顯示所有偵測到的人物最後出現的時間、動作與是否在場。
- **自動更新**：每 2 秒自動從資料庫抓取最新資料。

---

## 使用方式

### 基本用法

```python
from memory_layer import create_memory_system

# 建立記憶系統
memory_layer, client, inference_queue = create_memory_system()

# 啟動（會自動連線到 PostgreSQL）
memory_layer.start()

# 檢查連線狀態
if memory_layer.is_db_connected:
    print("資料庫連線成功")
else:
    print(f"連線失敗: {memory_layer.db_error}")

# 發送事件
from memory_layer.data_models import create_perception_event

event = create_perception_event(
    frame_no=1,
    person_id=0,
    bbox=(100, 50, 200, 400),
    action_label="站立",
    action_confidence=0.95,
    action_candidates=[("站立", 0.95), ("走路", 0.03), ("坐著", 0.02)],
    action_duration=5.2,
    motion_magnitude=0.5,
    reid_vector=None,
    environment={"room": "living_room"}
)

client.send_event(event)

# 查詢歷史
history = client.query_person_history(person_id=0, minutes=10)

# 停止
memory_layer.stop()
```

### 與 Receiver 整合

`we_mma_2/memory_bridge.py` 已經整合到以下感知層入口：

- **`observation_layer/main.py`**（主要）- 網路接收模式
- **`we_mma_2/main.py`** - 串口直連模式

啟動 Receiver 時會自動連接記憶層。

```bash
# 主要使用方式（網路接收）
cd sscma-example-we2
python -m observation_layer.main

# 串口直連模式
python -m we_mma_2.main
```

## 資料表結構

### `member_registry` - 成員註冊表
| 欄位 | 類型 | 說明 |
|------|------|------|
| member_id | SERIAL | 主鍵 |
| first_seen | TIMESTAMP | 首次出現時間 |
| last_seen | TIMESTAMP | 最後出現時間 |
| reid_vector | VECTOR(512) | 外觀特徵向量 |
| display_name | TEXT | 顯示名稱 |
| metadata | JSONB | 額外資訊 |

### `unified_telemetry` - 統一時序資料（TimescaleDB Hypertable）
| 欄位 | 類型 | 說明 |
|------|------|------|
| timestamp | TIMESTAMPTZ | 時間戳（主鍵） |
| frame_no | INTEGER | 幀編號 |
| person_id | INTEGER | 人物 ID |
| bbox_x, bbox_y, bbox_w, bbox_h | INTEGER | 邊界框 |
| action_label | TEXT | 動作標籤 |
| action_confidence | FLOAT | 信心度 |
| action_candidates | JSONB | 候選動作 JSON |
| action_duration | FLOAT | 動作持續時間 |
| motion_magnitude | FLOAT | 動作強度 |
| reid_vector | VECTOR(512) | 外觀向量 |
| environment | JSONB | 環境資訊 |

### `member_state_snapshot` - 成員即時狀態
| 欄位 | 類型 | 說明 |
|------|------|------|
| person_id | INTEGER | 主鍵 |
| current_action | TEXT | 目前動作 |
| current_location | TEXT | 當前位置 |
| last_updated | TIMESTAMPTZ | 更新時間 |
| is_active | BOOLEAN | 是否活躍 |
| session_start | TIMESTAMPTZ | 本次出現開始時間 |

## 配置選項

```python
from memory_layer.config import (
    MemoryConfig, 
    DatabaseConfig, 
    QueueConfig,
    RetentionConfig
)

# 自訂配置
config = MemoryConfig(
    database=DatabaseConfig(
        db_type="postgresql",
        host="localhost",
        port=5432,
        database="home_agent",
        user="home_agent",
        password="your_password"
    ),
    queue=QueueConfig(
        max_size=10000,
        batch_size=50,
        batch_timeout=1.0
    ),
    retention=RetentionConfig(
        telemetry_days=30,
        snapshot_days=7,
        cleanup_interval_hours=24
    )
)
```

## 未來功能 (TODO)

- [x] **整合 ReID 向量錄入**：將 `we_mma_2/reid_database.py` 的 SQLite 向量儲存遷移到記憶層
- [ ] **ReID 向量更新**：當新的骨架資料到來時，更新成員的外觀特徵向量
- [ ] **空間感知**：分析人物在場景中的位置關係，判斷互動
- [ ] **事件觸發機制**：當偵測到特定動作（如跌倒）時，推送通知到推論層
- [ ] **推論層查詢接口**：讓 LLM 能透過 SQL 查詢歷史資料
- [ ] **資料壓縮**：將歷史資料壓縮成摘要（例如「10:00-11:00 主要在客廳走動」）
- [ ] **多攝影機融合**：支援多個 WiseEye2 設備的資料整合
- [ ] **異常偵測**：偵測異常行為模式並自動標記
- [ ] **合併 we_mma_2 核心功能到 observation_layer**：簡化架構

## 疑難排解

### 找不到 memory_layer 模組

確保從專案根目錄執行，或將專案加入 `PYTHONPATH`：
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/sscma-example-we2"
```

### PostgreSQL 連線失敗

1. 確認 PostgreSQL 服務正在運行：
   ```bash
   brew services list  # macOS
   sudo systemctl status postgresql  # Linux
   ```

2. 檢查 `pg_hba.conf` 允許本地連線

### TimescaleDB 擴展未啟用

```sql
-- 在 PostgreSQL 中執行
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
```

## 授權

MIT License
