# NOMI Observation Layer - 骨架資料網路接收端

此程式為 `we_mma_2` 的網路版本，移除了 Serial 串口功能，改用 localhost socket 接收骨架資料。

## 功能特點

- 透過 localhost TCP 連接接收骨架資料
- 支援即時骨架視覺化
- 整合 MMAction2 動作識別
- ReID 人物識別與向量錄入
- 四種視圖模式：Original / Overlay / YOLO Only / Interpolated
- 開始/停止接收按鈕控制

## 架構

```
observation_layer/
├── __init__.py          # 套件入口
├── config.py            # 配置參數
├── gui_interface.py     # 圖形介面
├── main.py              # 主程式
├── network_receiver.py  # 網路接收模組
└── requirements.txt     # 依賴套件
```

## 使用方式

### 啟動接收端

```bash
cd /path/to/sscma-example-we2
python -m observation_layer.main
```

或直接執行：

```bash
python observation_layer/main.py
```

### 配置

修改 `config.py` 中的設定：

```python
# 網路連接配置
host = "127.0.0.1"  # 監聽位址
port = 9527         # 監聽埠號
```

## 與發射端配合使用

1. 先啟動本接收端程式
2. 再啟動 `../nomi_evaluation/device_simulator` 發射端程式
3. 接收端會自動連接到發射端
4. 切換發射端的資料來源（Serial/Webcam）即可看到資料

## 介面說明

### 頂部工具列
- **Server**: 顯示監聽位址
- **開始接收 / 停止接收**: 控制接收狀態
- **View Mode**: 切換視圖模式

### 即時辨識分頁
- 左側：影像顯示區域
- 右側：連接資訊、裝置資訊、幀資訊、ReID 結果
- 底部：動作識別結果

### 向量錄入分頁
- 用於錄入人物 ReID 向量
- 可管理已註冊的人物列表

## 依賴

此套件依賴 `we_mma_2` 的以下模組：
- `action_recognizer`
- `skeleton_processor`
- `visualizer`
- `reid_database`
- `config`

請確保 `we_mma_2` 資料夾存在且可正確導入。
