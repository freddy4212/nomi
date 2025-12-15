# WE_MMA_2 - WiseEye2 Visualizer with MMAction2

升級版的 WiseEye2 視覺化工具，整合 MMAction2 骨架動作識別功能。

## 功能特色

- 🎥 **即時影像顯示**：從 WiseEye2 接收並顯示即時影像
- 🦴 **骨架視覺化**：繪製人體骨架關鍵點和連線
- 🎯 **動作識別**：使用 MMAction2 分析骨架動作，識別人物行為
- 📊 **補幀處理**：自動將 1-2 FPS 的低幀率補幀至動作識別所需的幀率
- 📝 **動作描述**：在介面下方顯示人物動作的自然語言描述

## 專案結構

```
we_mma_2/
├── __init__.py           # 套件初始化
├── config.py             # 配置管理（串口、GUI、模型設定等）
├── serial_receiver.py    # 串口資料接收模組
├── skeleton_processor.py # 骨架處理與補幀模組
├── action_recognizer.py  # MMAction2 動作識別模組
├── gui_interface.py      # Tkinter 圖形介面模組
├── main.py              # 主程式入口
├── requirements.txt      # 依賴套件列表
└── README.md            # 本說明文件
```

## 安裝指南

### 步驟 1: 安裝基本依賴

```bash
cd we_mma_2
pip install -r requirements.txt
```

### 步驟 2: 安裝 MMAction2（選用，用於完整動作識別功能）

#### 2.1 安裝 PyTorch

根據你的系統選擇適當的安裝方式：

**macOS (CPU):**
```bash
pip install torch torchvision
```

**macOS (Apple Silicon MPS):**
```bash
pip install torch torchvision
# PyTorch 會自動使用 MPS 加速
```

**Linux/Windows (CUDA):**
```bash
# 請訪問 https://pytorch.org/get-started/locally/ 獲取適合你 CUDA 版本的安裝命令
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

#### 2.2 安裝 MMCV

```bash
# 安裝 mmcv
pip install -U openmim
mim install mmengine
mim install mmcv>=2.0.0
```

#### 2.3 安裝 MMAction2

```bash
# 克隆 MMAction2 倉庫
git clone https://github.com/open-mmlab/mmaction2.git
cd mmaction2

# 安裝 MMAction2
pip install -v -e .
```

#### 2.4 下載預訓練模型

MMAction2 提供多種骨架動作識別模型，推薦使用 PoseC3D：

```bash
# 在 mmaction2 目錄下
mkdir -p checkpoints

# 下載 PoseC3D 模型（NTU-60 資料集訓練）
# 適合識別日常動作
wget -P checkpoints https://download.openmmlab.com/mmaction/v1.0/skeleton/posec3d/posec3d_k400.pth

# 或下載 ST-GCN 模型
# wget -P checkpoints https://download.openmmlab.com/mmaction/skeleton/stgcn/stgcn_80e_ntu60_xsub/stgcn_80e_ntu60_xsub_keypoint-e7bb9653.pth
```

### 步驟 3: 配置模型路徑

編輯 `config.py`，設定模型配置檔案和權重路徑：

```python
@dataclass
class ActionRecognizerConfig:
    # 模型配置檔案路徑（相對於 mmaction2 安裝目錄）
    config_file: str = "/path/to/mmaction2/configs/skeleton/posec3d/slowonly_r50_8xb16-u48-240e_ntu60-xsub-keypoint.py"
    # 模型權重檔案路徑
    checkpoint_file: str = "/path/to/mmaction2/checkpoints/posec3d_k400.pth"
    # 設備：'cuda:0' 或 'cpu' 或 'mps'
    device: str = "cpu"
```

## 使用方式

### 快速啟動

```bash
# 方式 1: 作為模組執行
cd /path/to/sscma-example-we2
python -m we_mma_2.main

# 方式 2: 直接執行 main.py
python we_mma_2/main.py
```

### 操作說明

1. **選擇串口**：在下拉選單中選擇 WiseEye2 裝置的串口
2. **連接裝置**：點擊 "Connect" 按鈕
3. **觀看結果**：
   - 上方顯示即時影像和骨架
   - 右側顯示裝置資訊和 ReID 結果
   - 下方顯示動作識別結果（需要累積足夠幀數）

### 顯示模式

- **Original**：只顯示原始影像
- **Overlay**：影像 + 骨架疊加
- **YOLO Only**：只顯示骨架（黑色背景）

## 補幀說明

由於 WiseEye2 的傳輸速度約為 1-2 FPS，而動作識別通常需要 15-30 FPS 的輸入：

1. 系統會自動對接收到的骨架資料進行線性插值
2. 將 1-2 FPS 補幀至約 15 FPS
3. 累積 48 幀（約 3-4 秒）後開始動作識別
4. 補幀會造成一定的延遲，但不影響識別準確度

可以在 `config.py` 中調整補幀參數：

```python
@dataclass
class FrameInterpolationConfig:
    target_fps: int = 15  # 目標幀率
    interpolation_method: str = "linear"  # 'linear' 或 'copy'
    sequence_length: int = 48  # 動作識別所需的幀數
```

## 回退模式

如果未安裝 MMAction2，系統會自動使用回退模式：

- 基於規則的簡單動作識別
- 透過分析骨架運動特徵來判斷動作
- 支援基本動作識別：站立、行走、跑步、跳躍、揮手等

## 模組說明

### serial_receiver.py
負責與 WiseEye2 裝置的串口通訊：
- 在背景執行緒中讀取串口資料
- 解析 JSON 格式的封包
- 解碼 Base64 影像

### skeleton_processor.py
處理骨架資料：
- 解析關鍵點座標
- 執行補幀操作
- 維護骨架序列緩衝區

### action_recognizer.py
動作識別核心：
- 載入 MMAction2 模型
- 將骨架序列轉換為模型輸入格式
- 執行推理並返回動作標籤
- 生成人類可讀的動作描述

### gui_interface.py
Tkinter 圖形介面：
- 顯示即時影像和骨架
- 顯示裝置資訊和狀態
- 顯示動作識別結果描述

## 故障排除

### 串口連接失敗
- 確認 WiseEye2 裝置已正確連接
- 檢查串口權限（macOS/Linux 可能需要 sudo）
- 嘗試重新插拔 USB 連接線

### MMAction2 載入失敗
- 確認已正確安裝 PyTorch、MMCV 和 MMAction2
- 檢查模型配置檔案和權重路徑
- 如果 GPU 記憶體不足，嘗試設定 `device: str = "cpu"`

### 動作識別延遲
- 這是正常現象，因為需要累積足夠的幀數
- 可以減少 `sequence_length` 來降低延遲（但可能影響準確度）

### 補幀效果不佳
- 嘗試將 `interpolation_method` 改為 `"copy"`
- 增加 `buffer_size` 可能有助於平滑效果

## 支援的動作類別

預設支援以下動作類別（可在 `config.py` 中修改）：

| 動作 | 描述 |
|------|------|
| 站立 | 這個人正在站立不動 |
| 行走 | 這個人正在行走移動 |
| 跑步 | 這個人正在快速奔跑 |
| 跳躍 | 這個人正在上下跳動 |
| 坐下 | 這個人正在坐下 |
| 起立 | 這個人正在從座位上起身 |
| 揮手 | 這個人正在揮手打招呼 |
| 拍手 | 這個人正在拍手 |
| 閱讀 | 這個人正在閱讀東西 |
| 打電話 | 這個人正在打電話 |
| 喝水 | 這個人正在喝水 |
| 吃東西 | 這個人正在吃東西 |
| 睡覺 | 這個人正在睡覺休息 |

## 授權

本專案基於原 we2_visualizer.py 開發，遵循相同的授權條款。

MMAction2 使用 Apache 2.0 授權。
