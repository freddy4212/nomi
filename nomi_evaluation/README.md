# NOMI Evaluation Workspace

此目錄放置與評估、模擬相關的工具。

## 目前內容

- `device_simulator/`: 模擬 WiseEye2 發送骨架與 ReID 資料的發射端
- `virtual_endpoint_simulator/`: WE2 虛擬端點模擬器（含前後端與評估腳本）

## 啟動 Device Simulator

```bash
# 在 nomi_evaluation repo 根目錄下
python -m device_simulator.main
```

## 啟動 Virtual Endpoint Simulator

```bash
cd virtual_endpoint_simulator
bash start.sh
```
