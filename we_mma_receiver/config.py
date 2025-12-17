"""
config.py - 接收端配置參數

包含：
- 網路連接設定
- GUI 介面設定
- 與 we_mma_2 共用的配置
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkConfig:
    """網路連接配置"""
    mode: str = "server"  # "server" 或 "client"
    host: str = "0.0.0.0"  # Server 模式下綁定的地址，Client 模式下連接的目標
    port: int = 9527
    buffer_size: int = 65536
    reconnect_interval: float = 2.0  # 重連間隔（秒）


@dataclass
class ReceiverGUIConfig:
    """GUI 介面配置"""
    window_title: str = "WE_MMA Receiver - WiseEye2 動作識別接收端"
    window_size: str = "1200x900"
    canvas_width: int = 640
    canvas_height: int = 480


@dataclass
class ReceiverConfig:
    """主配置類"""
    network: NetworkConfig = None
    gui: ReceiverGUIConfig = None
    debug: bool = True
    
    def __post_init__(self):
        if self.network is None:
            self.network = NetworkConfig()
        if self.gui is None:
            self.gui = ReceiverGUIConfig()


# 全域配置實例
config = ReceiverConfig()
