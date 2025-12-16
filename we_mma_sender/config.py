"""
config.py - 發射端配置參數

包含：
- 網路連接設定
- Serial 設定
- Webcam 設定
- GUI 介面設定
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class NetworkConfig:
    """網路傳送配置"""
    host: str = "127.0.0.1"
    port: int = 9527
    buffer_size: int = 65536


@dataclass
class SerialConfig:
    """串口連接配置"""
    default_port: str = "/dev/tty.usbmodem5A4B0478511"
    baudrate: int = 921600
    timeout: float = 1.0


@dataclass
class WiFiConfig:
    """WiFi 接收配置"""
    listen_host: str = "0.0.0.0"
    listen_port: int = 9528
    buffer_size: int = 65536


@dataclass
class WebcamConfig:
    """Webcam 設定"""
    camera_id: int = 0
    width: int = 640
    height: int = 480
    default_fps: float = 2.0
    min_fps: float = 0.5
    max_fps: float = 30.0
    yolo_model: str = ""  # 將在 __post_init__ 中設定
    yolo_conf: float = 0.5
    reid_enabled: bool = True  # 是否預設啟用 ReID
    reid_model: str = ""  # ReID 模型路徑（TFLite）
    
    def __post_init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sender_dir = os.path.dirname(os.path.abspath(__file__))
        
        if not self.yolo_model:
            # 優先使用 sender/yolo 目錄下的模型
            local_model = os.path.join(sender_dir, "yolo", "yolov8n-pose.pt")
            if os.path.exists(local_model):
                self.yolo_model = local_model
            else:
                self.yolo_model = os.path.join(base_dir, "we_mma_2", "webcam_demo", "yolov8n-pose.pt")
        
        if not self.reid_model:
            # 優先使用 sender/reid/models 目錄下的模型
            local_model = os.path.join(sender_dir, "reid", "models", "person_reid_retail_0300.tflite")
            if os.path.exists(local_model):
                self.reid_model = local_model
            else:
                self.reid_model = os.path.join(base_dir, "model_zoo", "person_reid_int8_vela_64_0x600000.tflite")


@dataclass
class SenderGUIConfig:
    """GUI 介面配置"""
    window_title: str = "WE_MMA Sender - WiseEye2 資料發射端"
    window_size: str = "900x700"
    canvas_width: int = 640
    canvas_height: int = 480


@dataclass
class SenderConfig:
    """主配置類"""
    network: NetworkConfig = None
    serial: SerialConfig = None
    wifi: WiFiConfig = None
    webcam: WebcamConfig = None
    gui: SenderGUIConfig = None
    debug: bool = True
    
    def __post_init__(self):
        if self.network is None:
            self.network = NetworkConfig()
        if self.serial is None:
            self.serial = SerialConfig()
        if self.wifi is None:
            self.wifi = WiFiConfig()
        if self.webcam is None:
            self.webcam = WebcamConfig()
        if self.gui is None:
            self.gui = SenderGUIConfig()


# 全域配置實例
config = SenderConfig()
