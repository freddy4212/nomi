"""
config.py - 網路相關配置
"""

from dataclasses import dataclass


@dataclass
class NetworkConfig:
    """網路接收配置"""
    mode: str = "server"  # "server" 或 "client"
    host: str = "0.0.0.0"
    port: int = 9527
    buffer_size: int = 65536
    reconnect_interval: float = 2.0
