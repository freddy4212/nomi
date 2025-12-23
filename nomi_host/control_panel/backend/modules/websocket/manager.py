"""
manager.py - WebSocket 連線管理器

負責：
- 管理 WebSocket 連線池
- 提供廣播功能
- 連線生命週期管理
"""

import asyncio
from typing import List

from fastapi import WebSocket


class ConnectionManager:
    """
    WebSocket 連線管理器
    
    管理一組 WebSocket 連線，提供廣播功能。
    """
    
    def __init__(self, name: str = "default"):
        """
        初始化連線管理器
        
        Args:
            name: 管理器名稱（用於日誌）
        """
        self.name = name
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """
        接受並管理新連線
        
        Args:
            websocket: WebSocket 連線
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        print(f"[WS:{self.name}] Client connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """
        移除連線
        
        Args:
            websocket: WebSocket 連線
        """
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        print(f"[WS:{self.name}] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """
        廣播訊息給所有連線
        
        Args:
            message: 要廣播的訊息（JSON 字串）
        """
        # 複製列表避免在迭代時修改
        async with self._lock:
            connections = self.active_connections.copy()
        
        disconnected = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        # 清理斷開的連線
        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    if conn in self.active_connections:
                        self.active_connections.remove(conn)

    async def send_personal(self, websocket: WebSocket, message: str):
        """
        發送訊息給特定連線
        
        Args:
            websocket: 目標 WebSocket 連線
            message: 訊息內容
        """
        try:
            await websocket.send_text(message)
        except Exception as e:
            print(f"[WS:{self.name}] Send error: {e}")

    @property
    def connection_count(self) -> int:
        """當前連線數"""
        return len(self.active_connections)
