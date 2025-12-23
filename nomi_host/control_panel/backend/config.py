"""
config.py - Control Panel Backend 設定

負責：
- 伺服器設定
- WebSocket 設定
- 其他後端相關設定
"""

from dataclasses import dataclass


@dataclass
class ServerConfig:
    """伺服器設定"""
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


@dataclass
class WebSocketConfig:
    """WebSocket 設定"""
    video_fps: int = 30
    data_broadcast_interval: float = 0.1
    buffer_poll_interval: float = 0.03


@dataclass
class BackendConfig:
    """後端總設定"""
    server: ServerConfig
    websocket: WebSocketConfig
    debug: bool = False


# 預設設定
backend_config = BackendConfig(
    server=ServerConfig(),
    websocket=WebSocketConfig(),
    debug=False
)
