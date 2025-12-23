"""
NOMI Control Panel Backend

模組化的後端服務，負責：
- 啟動並管理三大核心層 (Observation, Memory, Inference)
- 提供 WebSocket 服務供前端連線
- 協調各層之間的資料流
"""

from .config import backend_config
from .modules import (ConnectionManager, NOMIOrchestrator,
                      setup_websocket_routes)

__all__ = [
    "backend_config",
    "ConnectionManager",
    "NOMIOrchestrator",
    "setup_websocket_routes",
]
