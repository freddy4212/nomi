"""
routes.py - WebSocket 路由設定

負責：
- 定義 WebSocket 端點
- 處理 WebSocket 訊息
- 命令分發
"""

import asyncio
import json
from typing import TYPE_CHECKING, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .manager import ConnectionManager

if TYPE_CHECKING:
    from ..orchestrator import NOMIOrchestrator


def json_serializable(obj):
    """JSON serializer for objects not serializable by default json code"""
    from datetime import datetime
    if isinstance(obj, datetime):
        return obj.timestamp()
    if hasattr(obj, 'tolist'):  # numpy arrays
        return obj.tolist()
    return str(obj)


class WebSocketRouter:
    """
    WebSocket 路由器
    
    負責處理所有 WebSocket 相關的路由與訊息處理。
    """
    
    def __init__(self, orchestrator: "NOMIOrchestrator"):
        """
        初始化路由器
        
        Args:
            orchestrator: 系統編排器實例
        """
        self.orchestrator = orchestrator
        self.video_manager = ConnectionManager("video")
        self.data_manager = ConnectionManager("data")
        self.data_queue: asyncio.Queue = asyncio.Queue()
    
    def setup_routes(self, app: FastAPI):
        """
        設定 WebSocket 路由
        
        Args:
            app: FastAPI 應用實例
        """
        
        @app.websocket("/ws/video")
        async def websocket_video_endpoint(websocket: WebSocket):
            await self.video_manager.connect(websocket)
            try:
                while True:
                    # Video socket is mostly output, but we keep it alive
                    await websocket.receive_text()
            except WebSocketDisconnect:
                await self.video_manager.disconnect(websocket)

        @app.websocket("/ws/data")
        async def websocket_data_endpoint(websocket: WebSocket):
            await self.data_manager.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    await self._handle_data_message(websocket, data)
            except WebSocketDisconnect:
                await self.data_manager.disconnect(websocket)

        # Legacy support: /ws redirects to video logic
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.video_manager.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                await self.video_manager.disconnect(websocket)
    
    async def _handle_data_message(self, websocket: WebSocket, data: str):
        """
        處理資料通道訊息
        
        Args:
            websocket: 來源 WebSocket
            data: 訊息內容
        """
        try:
            command_data = json.loads(data)
            msg_type = command_data.get("type")
            
            if msg_type == "command":
                await self._handle_command(websocket, command_data)
            elif msg_type == "db_query":
                await self._handle_db_query(websocket, command_data)
                
        except Exception as e:
            print(f"[WebSocket] Message error: {e}")
    
    async def _handle_command(self, websocket: WebSocket, data: dict):
        """處理系統命令"""
        cmd = data.get("command")
        
        if cmd == "start_system":
            print("[WebSocket] Received start_system command")
            self.orchestrator.start_system()
            
        elif cmd == "stop_system":
            print("[WebSocket] Received stop_system command")
            self.orchestrator.stop_system()
            
        elif cmd == "clear_memory":
            print(f"[WebSocket] Received clear_memory command")
            success = self.orchestrator.clear_all_events()
            print(f"[WebSocket] Clear memory success: {success}")
            
            # 通知所有客戶端資料已更新
            if success:
                await self.data_manager.broadcast(json.dumps({
                    "type": "db_data",
                    "query": "recent_events",
                    "data": []
                }))
            
            await websocket.send_text(json.dumps({
                "type": "command_result",
                "command": "clear_memory",
                "success": success
            }))
            
        elif cmd == "delete_member":
            member_id = data.get("member_id")
            print(f"[WebSocket] Received delete_member command for ID: {member_id}")
            success = self.orchestrator.delete_member(member_id)
            
            if success:
                # 廣播更新後的成員列表
                members = self.orchestrator.get_all_members()
                await self.data_manager.broadcast(json.dumps({
                    "type": "db_data",
                    "query": "all_members",
                    "data": members
                }, default=json_serializable))
                
            await websocket.send_text(json.dumps({
                "type": "command_result",
                "command": "delete_member",
                "success": success,
                "member_id": member_id
            }))

        elif cmd == "update_member":
            member_id = data.get("member_id")
            new_name = data.get("name")
            print(f"[WebSocket] Received update_member command for ID: {member_id}, Name: {new_name}")
            success = self.orchestrator.update_member_name(member_id, new_name)
            
            if success:
                # 廣播更新後的成員列表
                members = self.orchestrator.get_all_members()
                await self.data_manager.broadcast(json.dumps({
                    "type": "db_data",
                    "query": "all_members",
                    "data": members
                }, default=json_serializable))
                
            await websocket.send_text(json.dumps({
                "type": "command_result",
                "command": "update_member",
                "success": success,
                "member_id": member_id
            }))

        elif cmd == "start_recording":
            name = data.get("name", "Unknown")
            print(f"[WebSocket] Received start_recording command for: {name}")
            success, message = self.orchestrator.start_recording(name)
            
            await websocket.send_text(json.dumps({
                "type": "command_result",
                "command": "start_recording",
                "success": success,
                "message": message
            }))

        elif cmd == "stop_recording":
            print("[WebSocket] Received stop_recording command")
            success = self.orchestrator.stop_recording()
            
            await websocket.send_text(json.dumps({
                "type": "command_result",
                "command": "stop_recording",
                "success": success
            }))

        elif cmd == "set_view_mode":
            mode = data.get("mode")
            print(f"[WebSocket] Received set_view_mode command: {mode}")
            success = self.orchestrator.set_view_mode(mode)
            
            await websocket.send_text(json.dumps({
                "type": "command_result",
                "command": "set_view_mode",
                "success": success,
                "mode": mode
            }))
    
    async def _handle_db_query(self, websocket: WebSocket, data: dict):
        """處理資料庫查詢"""
        query_type = data.get("query")
        
        if query_type == "recent_events":
            limit = data.get("limit", 50)
            duration_sec = data.get("duration_sec", 86400)
            events = self.orchestrator.get_recent_events(limit=limit, duration_sec=duration_sec)
            await websocket.send_text(json.dumps({
                "type": "db_data",
                "query": "recent_events",
                "data": events
            }, default=json_serializable))
            
        elif query_type == "member_states":
            states = self.orchestrator.get_member_states()
            await websocket.send_text(json.dumps({
                "type": "db_data",
                "query": "member_states",
                "data": states
            }, default=json_serializable))
            
        elif query_type == "all_members":
            members = self.orchestrator.get_all_members()
            await websocket.send_text(json.dumps({
                "type": "db_data",
                "query": "all_members",
                "data": members
            }, default=json_serializable))


# 全域路由器實例（延遲初始化）
_router: WebSocketRouter = None


def setup_websocket_routes(app: FastAPI, orchestrator: "NOMIOrchestrator") -> WebSocketRouter:
    """
    設定 WebSocket 路由的便捷函數
    
    Args:
        app: FastAPI 應用實例
        orchestrator: 系統編排器實例
        
    Returns:
        WebSocketRouter 實例
    """
    global _router
    _router = WebSocketRouter(orchestrator)
    _router.setup_routes(app)
    return _router
