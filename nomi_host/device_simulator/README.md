# NOMI Device Simulator - 骨架資料網路發射端

此程式負責從多種來源接收骨架資料，並透過 localhost socket 發送給接收端，模擬 WiseEye2 裝置的輸出（tflm_yolov8n_pose_reid）。

## 功能特點

- 三種資料來源：WiFi / Serial / Webcam
- 透過 localhost TCP 發送骨架資料
- Webcam 模式支援：
  - 切換攝像頭
  - YOLO-Pose 骨架辨識
  - **ReID 特徵提取**（模擬 WiseEye2 的 512 維特徵向量）
  - 可調整採樣率（模擬低 FPS 環境）
  - **一卡一卡的預覽效果**（與採樣率同步）
- 輸出格式與 WiseEye2 tflm_yolov8n_pose_reid 相容

## 架構

```
device_simulator/
├── __init__.py          # 套件入口
├── config.py            # 配置參數
├── gui_interface.py     # 圖形介面（三分頁）
├── main.py              # 主程式
├── requirements.txt     # 依賴套件
├── sources/             # 資料來源模組
│   ├── __init__.py
│   ├── serial_source.py   # Serial 串口來源
│   └── webcam_source.py   # Webcam 攝像頭來源
├── reid/                # ReID 特徵提取模組
│   ├── __init__.py
│   └── reid_extractor.py  # ReID 提取器（支援 TorchReID/TFLite/模擬）
└── yolo/                # YOLO 姿態估計模組
    ├── __init__.py
    └── pose_extractor.py  # YOLO-Pose 提取器
```

## 使用方式

### 啟動發射端

```bash
cd /path/to/sscma-example-we2
python -m device_simulator.main
```

或直接執行：

```bash
python device_simulator/main.py
```

### 配置

修改 `config.py` 中的設定：

```python
# 網路傳送配置
host = "127.0.0.1"  # 目標位址（接收端）
port = 9527         # 目標埠號

# Webcam 設定
camera_id = 0       # 預設攝像頭
default_fps = 2.0   # 預設採樣率
```

## 介面說明

### 頂部工具列
- **Target Server**: 顯示目標接收端位址
- **Client**: 顯示接收端連接狀態

### 📡 WiFi 接收分頁
- 監聽 WiseEye2 的 WiFi 資料傳輸
- 設定監聽位址和埠號

### 🔌 Serial 接收分頁
- 連接 WiseEye2 的串口
- 選擇串口、設定鮑率
- 顯示裝置資訊

### 📷 Webcam 測試分頁
- 使用電腦攝像頭模擬 WiseEye2
- 攝像頭選擇與切換
- FPS 滑桿控制（模擬低幀率）
- **ReID 開關**：啟用/停用 ReID 特徵提取
- **預覽模式選擇**：
  - 採樣幀率預覽（一卡一卡，模擬 WiseEye2 效果）
  - 即時幀率預覽（流暢顯示）
- 即時預覽與骨架顯示

## 輸出格式

發送的 JSON 資料格式與 WiseEye2 tflm_yolov8n_pose_reid 相容：

```json
{
  "type": 0,
  "name": "INVOKE",
  "code": 0,
  "data": {
    "image": "<base64 encoded JPEG>",
    "keypoints": [
      [
        [x, y, w, h, confidence, target],  // 邊界框
        [x, y, conf, target],              // 關鍵點 0 (鼻子)
        [x, y, conf, target],              // 關鍵點 1 (左眼)
        // ... 共 17 個關鍵點 (COCO 格式)
      ]
    ],
    "reid_results": [
      {
        "id": 0,
        "feature": [0.1, 0.2, ...],  // 512 維特徵向量
        "confidence": 0.95,
        "box": [x1, y1, x2, y2]
      }
    ],
    "basic_info": {
      "device_id": "WEBCAM_SIM",
      "name": "Webcam Simulator (tflm_yolov8n_pose_reid)",
      "ver": "1.0.0"
    },
    "frame_info": {
      "frame_no": 123,
      "source": "webcam",
      "sample_fps": 2.0,
      "reid_enabled": true
    }
  }
}
```

## 與接收端配合使用

1. 先啟動 `observation_layer` 接收端程式
2. 再啟動本發射端程式
3. 選擇資料來源分頁（WiFi / Serial / Webcam）
4. 點擊開始按鈕
5. 資料會自動傳送到接收端

## 依賴

```bash
pip install -r requirements.txt
```

主要依賴：
- `opencv-python`: 影像處理
- `numpy`: 數值運算
- `Pillow`: 影像顯示
- `pyserial`: 串口通訊
- `ultralytics`: YOLO-Pose 骨架辨識
