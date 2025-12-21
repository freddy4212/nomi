"""
main.py - NOMI Control Panel Backend (Orchestrator)

負責：
1. 啟動並管理三大核心層 (Observation, Memory, Inference)
2. 提供 WebSocket 服務供前端 (Control Panel Frontend) 連線
3. 協調各層之間的資料流
"""

import asyncio
import base64
import json
import os
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional

import cv2
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- 路徑設定 ---
# 確保可以導入 nomi_host 下的模組
current_dir = os.path.dirname(os.path.abspath(__file__))
nomi_host_dir = os.path.dirname(os.path.dirname(current_dir))
if nomi_host_dir not in sys.path:
    sys.path.insert(0, nomi_host_dir)

# 確保可以導入 mmaction2 (位於 observation_layer 下)
mmaction2_dir = os.path.join(nomi_host_dir, "observation_layer", "mmaction2")
if os.path.exists(mmaction2_dir) and mmaction2_dir not in sys.path:
    sys.path.insert(0, mmaction2_dir)


# 導入各層核心
try:
    from memory_layer.config import memory_config
    from memory_layer.core import MemoryCore, MemoryStatus
    from observation_layer.core import (PersonActionInfo, ReceiverCore,
                                        ReceiverStatus)
    from observation_layer.modules.network.receiver import FrameData
    from observation_layer.modules.visualization.visualizer import Visualizer

    # from inference_layer.core import InferenceCore # 假設 Inference Layer 有類似的 Core
except ImportError as e:
    print(f"[Backend] Import Error: {e}")
    print(f"[Backend] sys.path: {sys.path}")
    sys.exit(1)

# --- Helper Functions ---
def json_serializable(obj):
    """JSON serializer for objects not serializable by default json code"""
    from datetime import datetime
    if isinstance(obj, datetime):
        return obj.timestamp()
    if hasattr(obj, 'tolist'): # numpy arrays
        return obj.tolist()
    return str(obj)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# --- FastAPI 設定 ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket 管理 ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager() # For Video
data_manager = ConnectionManager() # For Data (Events, Status, DB)
data_queue = asyncio.Queue()

@app.websocket("/ws/video")
async def websocket_video_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Video socket is mostly output, but we keep it alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/data")
async def websocket_data_endpoint(websocket: WebSocket):
    await data_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                command_data = json.loads(data)
                if command_data.get("type") == "command":
                    cmd = command_data.get("command")
                    if cmd == "start_system":
                        print("[Backend] Received start_system command")
                        orchestrator.start_system()
                    elif cmd == "stop_system":
                        print("[Backend] Received stop_system command")
                        orchestrator.stop_system()
                    elif cmd == "clear_memory":
                        print(f"[Backend] Received clear_memory command from WebSocket {websocket.client}")
                        success = orchestrator.clear_all_events()
                        print(f"[Backend] Clear memory success: {success}")
                        
                        # 通知所有客戶端資料已更新
                        if success:
                            await data_manager.broadcast(json.dumps({
                                "type": "db_data",
                                "query": "recent_events",
                                "data": []
                            }))
                            
                        await websocket.send_text(json.dumps({
                            "type": "command_result",
                            "command": "clear_memory",
                            "success": success
                        }))
                
                elif command_data.get("type") == "db_query":
                    query_type = command_data.get("query")
                    if query_type == "recent_events":
                        limit = command_data.get("limit", 50)
                        duration_sec = command_data.get("duration_sec", 86400)
                        events = orchestrator.get_recent_events(limit=limit, duration_sec=duration_sec)
                        await websocket.send_text(json.dumps({
                            "type": "db_data",
                            "query": "recent_events",
                            "data": events
                        }, default=json_serializable))
                    elif query_type == "member_states":
                        states = orchestrator.get_member_states()
                        await websocket.send_text(json.dumps({
                            "type": "db_data",
                            "query": "member_states",
                            "data": states
                        }, default=json_serializable))
                    elif query_type == "all_members":
                        members = orchestrator.get_all_members()
                        await websocket.send_text(json.dumps({
                            "type": "db_data",
                            "query": "all_members",
                            "data": members
                        }, default=json_serializable))
            except Exception as e:
                print(f"[Backend] Command error: {e}")
    except WebSocketDisconnect:
        data_manager.disconnect(websocket)

# Keep /ws for backward compatibility (redirect to video logic)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Legacy support: handle commands here too if needed, but prefer /ws/data
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def broadcast_worker():
    """從 Queue 取出資料並廣播到 Data Channel"""
    while True:
        message = await data_queue.get()
        await data_manager.broadcast(message)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_worker())

# --- 系統核心 (Orchestrator) ---
class NOMIOrchestrator:
    def __init__(self):
        self.observation_core: Optional[ReceiverCore] = None
        self.memory_core: Optional[MemoryCore] = None
        self.inference_core = None
        
        self.latest_actions = []
        self.latest_status: Optional[ReceiverStatus] = None
        self.loop = None # 用於 threadsafe call

        # 持久化資訊，避免閃爍
        self.device_info = {
            "id": "Unknown",
            "name": "Unknown",
            "version": "Unknown",
            "model": "Unknown"
        }
        self.last_db_events_written = 0
        self.last_db_active_time = 0
        self.last_tcp_active_time = 0
        self.last_algo_tick = 0
        self.last_frame_no = 0

    def start_system(self):
        if self.observation_core and self.observation_core.get_status().is_running:
             print("[Orchestrator] System already running")
             return

        print("[Orchestrator] Starting NOMI System...")
        
        # 取得當前 Event Loop 供 Thread-safe 通訊使用
        try:
            self.loop = asyncio.get_running_loop()
            print(f"[Orchestrator] Captured event loop: {self.loop}")
        except RuntimeError:
            self.loop = None
            print("[Orchestrator] Failed to capture event loop (RuntimeError)")
        
        # 1. 啟動 Memory Layer
        try:
            if not self.memory_core:
                self.memory_core = MemoryCore(
                    on_event_received=self._on_memory_event
                )
            
            # 修正：使用 get_status().is_running 檢查
            status = self.memory_core.get_status()
            if not status.is_running:
                self.memory_core.start()
                print("[Orchestrator] Memory Layer started")
        except Exception as e:
            print(f"[Orchestrator] Failed to start Memory Layer: {e}")

        # 2. 啟動 Observation Layer
        # 如果不存在，或者存在但已經停止且曾經啟動過 (ident is not None)，則重新建立
        if not self.observation_core or (not self.observation_core.is_alive() and self.observation_core.ident is not None):
            print("[Orchestrator] Creating new ReceiverCore instance...")
            self.observation_core = ReceiverCore(
                on_frame_processed=self._on_observation_frame,
                on_action_recognized=self._on_observation_action,
                on_status_changed=self._on_observation_status,
                enable_memory_bridge=True # 讓 Observation 嘗試連接 Memory
            )
        
        # 設置 Memory Bridge
        if self.memory_core and self.observation_core.memory_bridge:
            # 注入 MemoryLayer 實例與輸入隊列
            bridge = self.observation_core.memory_bridge
            memory_layer = self.memory_core._memory_layer
            
            # 注入隊列，這是寫入資料庫的關鍵
            bridge.memory_queue = memory_layer.input_queue
            bridge._enabled = True
            
            if hasattr(bridge, 'set_memory_layer'):
                 bridge.set_memory_layer(memory_layer)
            else:
                 bridge._memory_layer = memory_layer
            
            # 注入 Client 用於 ReID
            if hasattr(memory_layer, 'db'):
                # 這裡我們需要一個 Client 實例，或者直接讓 bridge 使用 db
                # 查看 bridge.py，它期望一個 _client
                # 如果 memory_layer 有 _client (通常在 create_memory_system 中建立)
                pass
            
            print("[Orchestrator] Memory Bridge linked to Memory Layer")
        
        # 修正：只有在執行緒未運行時才 start()
        if not self.observation_core.is_alive():
            try:
                self.observation_core.start()
            except RuntimeError as e:
                print(f"[Orchestrator] Warning: Failed to start Observation thread: {e}")

        if not self.observation_core.get_status().is_running:
            self.observation_core.start_receiving() # 開始監聽 Port 9527
            print("[Orchestrator] Observation Layer started")

        # 3. 啟動 Inference Layer (TODO)
        print("[Orchestrator] Inference Layer (Placeholder) started")

    def stop_system(self):
        print("[Orchestrator] Stopping system...")
        if self.observation_core:
            self.observation_core.stop_receiving()
            # self.observation_core.stop() # Don't kill the thread, just stop receiving
            # Actually, to fully stop, we might want to stop the thread too, but then we need to re-init
            # For now, let's just stop receiving to "pause"
            
        # if self.memory_core: 
        #     self.memory_core.stop()

    # --- Callbacks from Observation Layer ---
    def _on_observation_frame(self, frame_data: FrameData, skeleton_frame):
        """處理影像與骨架資料"""
        # 這裡是在 Observation 的執行緒中
        
        # 1. 伺服器端繪圖 (Server-side Rendering)
        # 使用 Visualizer 將骨架畫在影像上
        processed_image = None
        if frame_data and frame_data.image is not None:
            # 複製一份影像以免影響原始資料
            processed_image = frame_data.image.copy()
            
            # 取得插值後的骨架 (Interpolated Mode)
            # 這裡我們需要從 skeleton_processor 獲取插值後的結果，或者直接使用當前幀的骨架
            # 為了最佳效果，我們應該嘗試獲取插值結果
            display_skeletons = []
            if self.observation_core and self.observation_core.skeleton_processor:
                # 嘗試獲取插值後的幀
                interp_frames = self.observation_core.skeleton_processor.get_interpolated_frames()
                if interp_frames:
                    # 取最後一幀 (最新)
                    display_skeletons = interp_frames[-1]
                else:
                    # 降級使用原始骨架
                    display_skeletons = skeleton_frame
            else:
                display_skeletons = skeleton_frame

            # 繪製骨架
            if display_skeletons and hasattr(display_skeletons, 'persons'):
                for i, person in enumerate(display_skeletons.persons):
                    # 嘗試匹配 Person ID
                    pid = person.person_id
                    bbox = person.box
                    
                    # 繪製
                    try:
                        # 優先使用平滑後的關鍵點
                        kpts = person.smoothed_keypoints if person.smoothed_keypoints is not None else person.keypoints
                        
                        if kpts is not None and kpts.shape == (17, 3):
                            Visualizer.draw_skeleton(
                                processed_image, 
                                kpts, 
                                person_id=pid,
                                box=bbox,
                                show_confidence=False
                            )
                    except Exception as e:
                        # print(f"Draw error: {e}")
                        pass

        # 2. 影像編碼
        img_str = ""
        if processed_image is not None:
            try:
                _, buffer = cv2.imencode('.jpg', processed_image, [cv2.IMWRITE_JPEG_QUALITY, 70])
                img_str = base64.b64encode(buffer).decode('utf-8')
            except Exception:
                pass

        # 3. 準備狀態資訊
        fps = 0.0
        algo_tick = self.last_algo_tick
        frame_no = self.last_frame_no
        
        # 優先從 frame_data 獲取即時資訊
        if frame_data:
            # 獲取幀序號 (優先使用封包內的，若無則使用接收計數)
            current_frame_no = getattr(frame_data, 'frame_no', 0)
            if current_frame_no > 0:
                frame_no = current_frame_no
            elif self.latest_status:
                frame_no = self.latest_status.frame_count
            
            # 獲取 Algo Tick
            current_algo_tick = 0
            if frame_data.frame_info:
                try:
                    current_algo_tick = int(frame_data.frame_info.get("algo_tick", 0))
                except:
                    current_algo_tick = 0
            
            if current_algo_tick > 0:
                algo_tick = current_algo_tick
            elif frame_no > self.last_frame_no:
                # 如果沒有 algo_tick，但有 frame_no，且 frame_no 比上次大，則更新
                algo_tick = frame_no

            # 儲存最後一次看到的數值，供 status_update 使用
            self.last_algo_tick = algo_tick
            self.last_frame_no = frame_no

            # 獲取裝置資訊 (更強大的抓取邏輯)
            # 建立一個候選字典，包含 basic_info 與 top-level raw_data
            lookup = {}
            if frame_data.basic_info:
                lookup.update(frame_data.basic_info)
            if frame_data.raw_data:
                lookup.update(frame_data.raw_data)
            
            # 抓取 ID
            self.device_info["id"] = lookup.get("device_id", lookup.get("ID", lookup.get("id", self.device_info["id"])))
            # 抓取 Version
            self.device_info["version"] = lookup.get("ver", lookup.get("Ver", lookup.get("version", self.device_info["version"])))
            # 抓取 Model (根據用戶提供格式，name 欄位即為 Model)
            self.device_info["model"] = lookup.get("name", lookup.get("Name", lookup.get("Model", lookup.get("model", self.device_info["model"]))))
            # 抓取 Name (作為顯示名稱，若無則與 Model 同步)
            self.device_info["name"] = self.device_info["model"]
        
        elif self.latest_status:
            # 如果沒有 frame_data (例如定時狀態更新)，使用最後已知的計數
            fps = self.latest_status.fps
            # 這裡絕對不要用 self.latest_status.frame_count，否則會導致數值在裝置 Tick 與接收計數間跳變
            algo_tick = self.last_algo_tick
            frame_no = self.last_frame_no
        
        # 優先使用 NetworkReceiver 的即時 FPS
        if self.observation_core and self.observation_core.network_receiver:
            fps = self.observation_core.network_receiver.get_fps()
            # 記錄 TCP 活動時間
            if self.observation_core.network_receiver.is_connected:
                # 這裡我們假設有收到 frame_data 就是有活動
                if frame_data:
                    self.last_tcp_active_time = time.time()
        
        # 4. 準備記憶層狀態
        memory_connected = False
        db_active = False
        if self.memory_core:
            # 檢查 MemoryCore 的實際狀態
            status = self.memory_core.get_status()
            memory_connected = status.is_db_connected and status.is_running
            
            # 檢查資料庫寫入活動
            if status.events_written > self.last_db_events_written:
                self.last_db_active_time = time.time()
                self.last_db_events_written = status.events_written
            
            if time.time() - self.last_db_active_time < 0.6:
                db_active = True

        # 準備 TCP 狀態
        tcp_connected = False
        tcp_active = False
        tcp_port = 0
        if self.observation_core and self.observation_core.network_receiver:
            tcp_connected = self.observation_core.network_receiver.is_connected
            tcp_port = self.observation_core.network_receiver.port
            if time.time() - self.last_tcp_active_time < 0.6:
                tcp_active = True

        # 準備 Buffer 狀態
        buffer_status = {}
        if self.observation_core and self.observation_core.skeleton_processor:
            buffer_status = self.observation_core.skeleton_processor.get_buffer_status()

        message = {
            "type": "frame_update",
            "timestamp": time.time(),
            "image": img_str,
            "meta": {
                "fps": fps,
                "algo_tick": algo_tick,
                "frame_no": frame_no,
                "device_id": self.device_info["id"],
                "device_name": self.device_info["name"],
                "device_version": self.device_info["version"],
                "device_model": self.device_info["model"],
                "memory_connected": memory_connected,
                "db_active": db_active,
                "tcp_connected": tcp_connected,
                "tcp_active": tcp_active,
                "tcp_port": tcp_port,
                "db_port": memory_config.database.port,
                "host_ip": get_local_ip(),
                "buffer_status": buffer_status
            },
            "persons": [], # 前端主要依賴 image，這裡保留空陣列或放入識別結果供參考
            "status": "running"
        }
        
        # 放入識別結果供前端顯示文字
        if self.latest_actions:
            for action in self.latest_actions:
                message["persons"].append({
                    "id": action.person_id,
                    "action": action.action_label,
                    "confidence": action.confidence,
                    "skeleton_status": action.skeleton_status,
                    "motion_status": action.motion_status,
                    "reid_name": action.reid_name
                })

        # 5. 推送到 Queue
        global _message_buffer
        _message_buffer = json.dumps(message)

    def _on_observation_action(self, actions: List[PersonActionInfo]):
        self.latest_actions = actions

    def _on_observation_status(self, status: ReceiverStatus):
        self.latest_status = status
        self._broadcast_status_update()

    # --- Database Queries ---
    def get_recent_events(self, limit=50, duration_sec=86400):
        if not self.memory_core:
            return []
        try:
            # 直接從 MemoryCore 的 DatabaseManager 查詢
            # 注意：get_recent_events(duration_sec, action_filter, limit)
            events = self.memory_core._db.get_recent_events(duration_sec=duration_sec, limit=limit)
            # 轉換為 JSON 可序列化格式
            return events
        except Exception as e:
            print(f"[Orchestrator] DB Query Error: {e}")
            return []

    def get_member_states(self):
        if not self.memory_core:
            return []
        try:
            states = self.memory_core._db.get_member_states()
            return states
        except Exception as e:
            print(f"[Orchestrator] DB Query Error: {e}")
            return []

    def get_all_members(self):
        if not self.memory_core:
            return []
        try:
            # 查詢所有已註冊成員
            members = self.memory_core._db.query("SELECT member_id as id, name, sample_count, updated_at FROM member_registry ORDER BY member_id ASC")
            return members
        except Exception as e:
            print(f"[Orchestrator] DB Query Error: {e}")
            return []

    def clear_all_events(self):
        """清除所有事件記憶"""
        if not self.memory_core:
            print("[Orchestrator] Cannot clear memory: memory_core is None")
            return False
        try:
            print("[Orchestrator] Requesting memory clear...")
            success = self.memory_core.clear_all_events()
            print(f"[Orchestrator] Memory clear result: {success}")
            return success
        except Exception as e:
            print(f"[Orchestrator] Clear Memory Error: {e}")
            return False

    def _on_memory_event(self, event):
        """當記憶層收到新事件時的回調"""
        print(f"[Orchestrator] Received memory event: person={getattr(event, 'person_id', '?')}, action={getattr(event, 'action_label', '?')}")
        # 轉換為字典
        event_dict = {
            "timestamp": getattr(event, 'timestamp', time.time()),
            "person_id": getattr(event, 'person_id', 0),
            "frame_no": getattr(event, 'frame_no', 0),
            "bbox": getattr(event, 'bbox', []),
            "action_label": getattr(event, 'action_label', "Unknown"),
            "action_confidence": getattr(event, 'action_confidence', 0.0),
            "action_duration": getattr(event, 'action_duration', 0.0),
            "motion_magnitude": getattr(event, 'motion_magnitude', 0.0),
            "member_name": getattr(event, 'member_name', None),
            "environment": getattr(event, 'environment', {})
        }
        
        message = json.dumps({
            "type": "new_event",
            "data": event_dict
        }, default=json_serializable)
        
        # 推送到 data_queue (Thread-safe)
        if self.loop:
            print(f"[Orchestrator] Pushing new_event to WebSocket queue")
            self.loop.call_soon_threadsafe(data_queue.put_nowait, message)
        else:
            print("[Orchestrator] Warning: No event loop to send memory event")

    def _broadcast_status_update(self):
        """廣播系統狀態更新 (不含影像)"""
        # 準備記憶層狀態
        memory_connected = False
        db_active = False
        if self.memory_core:
            status = self.memory_core.get_status()
            memory_connected = status.is_db_connected and status.is_running
            
            # 檢查資料庫寫入活動
            if status.events_written > self.last_db_events_written:
                self.last_db_active_time = time.time()
                self.last_db_events_written = status.events_written
            
            if time.time() - self.last_db_active_time < 1.0:
                db_active = True

        # 準備 TCP 狀態
        tcp_connected = False
        tcp_active = False
        tcp_port = 0
        if self.observation_core and self.observation_core.network_receiver:
            tcp_connected = self.observation_core.network_receiver.is_connected
            tcp_port = self.observation_core.network_receiver.port
            # 檢查 TCP 活動 (NetworkReceiver 內部有 current_fps，如果 > 0 則視為 active)
            if self.observation_core.network_receiver.get_fps() > 0:
                self.last_tcp_active_time = time.time()
            
            if time.time() - self.last_tcp_active_time < 1.0:
                tcp_active = True

        # 準備 Buffer 狀態
        buffer_status = {}
        if self.observation_core and self.observation_core.skeleton_processor:
            buffer_status = self.observation_core.skeleton_processor.get_buffer_status()

        message = {
            "type": "status_update",
            "timestamp": time.time(),
            "meta": {
                "fps": self.latest_status.fps if self.latest_status else 0,
                "algo_tick": self.last_algo_tick,
                "frame_no": self.last_frame_no,
                "device_id": self.device_info["id"],
                "device_name": self.device_info["name"],
                "device_version": self.device_info["version"],
                "device_model": self.device_info["model"],
                "memory_connected": memory_connected,
                "db_active": db_active,
                "tcp_connected": tcp_connected,
                "tcp_active": tcp_active,
                "tcp_port": tcp_port,
                "db_port": memory_config.database.port,
                "host_ip": get_local_ip(),
                "buffer_status": buffer_status
            },
            "status": "running" if self.observation_core and self.observation_core.is_alive() else "stopped"
        }
        
        message_json = json.dumps(message)
        
        # 1. 放入 Video Buffer (供 PerceptionView 使用)
        global _message_buffer
        _message_buffer = message_json
        
        # 2. 放入 Data Queue (供 MemoryView/Footer 使用)
        if self.loop:
            self.loop.call_soon_threadsafe(data_queue.put_nowait, message_json)

# --- Global Buffer for Thread Bridge ---
_message_buffer = None

async def buffer_polling_worker():
    """輪詢 _message_buffer 並廣播"""
    global _message_buffer
    last_sent = None
    while True:
        if _message_buffer and _message_buffer != last_sent:
            await manager.broadcast(_message_buffer)
            last_sent = _message_buffer
        await asyncio.sleep(0.03) # ~30 FPS

@app.on_event("startup")
async def start_polling():
    asyncio.create_task(buffer_polling_worker())

# --- Main Entry ---
orchestrator = NOMIOrchestrator()

@app.on_event("startup")
async def startup_orchestrator():
    # 在 FastAPI 啟動時啟動後端核心
    # 使用 Thread 避免阻塞 Event Loop
    # 但 ReceiverCore 本身就是 Thread，所以可以直接 start
    orchestrator.start_system()

@app.on_event("shutdown")
async def shutdown_orchestrator():
    orchestrator.stop_system()

def main():
    """啟動後端服務"""
    print("========================================")
    print("   NOMI Control Panel - Backend Core    ")
    print("========================================")
    print("Starting WebSocket Server on 0.0.0.0:8000")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    main()
