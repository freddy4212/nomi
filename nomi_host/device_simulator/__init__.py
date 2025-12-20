"""
device_simulator - WE_MMA_2 發射端程式

這個套件負責：
- 從多種來源接收骨架資料（Serial/WiFi/Webcam）
- 透過 localhost port 發送資料到接收端
- 模擬 WiseEye2 裝置輸出 JSON 格式

支援的資料來源：
- Serial: 從 WiseEye2 串口接收
- WiFi: 從網路接收 WiseEye2 資料
- Webcam: 使用電腦攝像頭 + YOLO 辨識模擬資料
"""

from .main import NOMI Device Simulator_App, main

__all__ = ['main', 'NOMI Device Simulator_App']
