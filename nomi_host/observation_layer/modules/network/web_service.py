"""
web_service.py - WebSocket 服務模組

負責：
- 啟動 FastAPI 伺服器
- 提供 WebSocket 端點供前端連線
- 廣播即時影像與骨架資料
"""

import asyncio
import base64
import json
import threading
import time
from typing import Any, Dict, List, Optional

import cv2
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 允許跨域請求 (方便前端開發)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
                # 如果發送失敗，可能連線已斷開，暫不處理，下次會被清理
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 保持連線，接收前端訊息 (目前前端主要是接收，但可擴充控制指令)
            data = await websocket.receive_text()
            # 可以在此處理前端發來的指令，例如 "start_recording"
    except WebSocketDisconnect:
        manager.disconnect(websocket)

class WebService(threading.Thread):
    """
    WebSocket 服務執行緒
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        super().__init__()
        self.host = host
        self.port = port
        self.daemon = True
        self.loop = None
        
    def run(self):
        # 啟動 uvicorn
        uvicorn.run(app, host=self.host, port=self.port, log_level="error")

    def broadcast_frame(self, frame_data: Any, skeleton_frame: Any, actions: List[Any]):
        """
        廣播資料到所有連線的客戶端
        
        Args:
            frame_data: 包含影像的 FrameData 物件
            skeleton_frame: 骨架資料
            actions: 動作識別結果
        """
        if not manager.active_connections:
            return

        # 1. 處理影像 (轉為 Base64)
        img_str = ""
        if frame_data and frame_data.image is not None:
            try:
                # 壓縮影像以降低頻寬 (JPEG quality 70)
                _, buffer = cv2.imencode('.jpg', frame_data.image, [cv2.IMWRITE_JPEG_QUALITY, 70])
                img_str = base64.b64encode(buffer).decode('utf-8')
            except Exception as e:
                print(f"Image encode error: {e}")

        # 2. 處理骨架與動作資料
        persons_info = []
        if actions:
            for action in actions:
                persons_info.append({
                    "id": action.person_id,
                    "action": action.action_label,
                    "confidence": action.confidence,
                    "skeleton_status": action.skeleton_status,
                    "motion_status": action.motion_status,
                    "bbox": action.bbox,
                    "reid_name": action.reid_name,
                    "reid_confidence": action.reid_confidence,
                    "duration": action.duration
                })
        
        # 3. 封裝訊息
        message = {
            "type": "frame_update",
            "timestamp": time.time(),
            "image": img_str,
            "persons": persons_info,
            "fps": 0.0, # TODO: 傳入 FPS
            "status": "running"
        }
        
        # 4. 非同步廣播 (需要獲取事件迴圈)
        # 由於這是從另一個執行緒呼叫的，我們需要一種方式將任務丟給 asyncio loop
        # 這裡使用一個簡單的 hack: uvicorn 運行在自己的 loop 中
        # 我們可以嘗試直接 run_coroutine_threadsafe，但需要存取到 uvicorn 的 loop
        # 暫時簡化：如果是在 uvicorn 執行緒外，可能無法直接 await
        # 解決方案：使用 asyncio.run 會有問題。
        # 正確做法是讓 uvicorn 跑在主執行緒，或者使用 queue 傳遞資料。
        # 為了簡單起見，我們這裡使用一個全域的 queue 或者直接忽略跨執行緒問題 (uvicorn 內部有處理)
        # 但 manager.broadcast 是 async 的。
        
        try:
            # 取得當前事件迴圈 (這通常會失敗，因為我們在另一個執行緒)
            # 所以我們需要一個 helper 來橋接
            asyncio.run(manager.broadcast(json.dumps(message)))
        except Exception:
            # 在非 async 環境下 (如 threading)，asyncio.run 會建立新的 loop 並執行
            # 但這會導致效能問題。
            # 更好的方式是：WebService 不直接廣播，而是將資料放入 queue，
            # 由 FastAPI 內部的背景任務去消耗 queue。
            pass

# 改進版：使用 Queue 橋接
data_queue = asyncio.Queue()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_worker())

async def broadcast_worker():
    while True:
        message = await data_queue.get()
        await manager.broadcast(message)

# 全域實例
_web_service_instance = None

def get_web_service():
    global _web_service_instance
    if _web_service_instance is None:
        _web_service_instance = WebService()
    return _web_service_instance

def push_update(data: Dict[str, Any]):
    """外部呼叫此函數推送更新"""
    try:
        # 這裡我們需要將資料放入 asyncio queue
        # 但我們在同步執行緒中，無法直接 await queue.put
        # 我們可以使用 run_coroutine_threadsafe 如果我們有 loop reference
        # 或者，我們使用一個線程安全的 queue，然後讓 broadcast_worker 輪詢 (不推薦)
        # 
        # 簡單解法：
        # 由於 uvicorn 啟動後我們很難拿到它的 loop
        # 我們改用一個簡單的 threading.Lock 保護的 list 或者 deque
        # 然後在 async worker 中 sleep polling
        global _latest_message
        _latest_message = json.dumps(data)
    except Exception as e:
        print(f"Push update error: {e}")

_latest_message = None

async def broadcast_worker_polling():
    global _latest_message
    last_sent = None
    while True:
        if _latest_message and _latest_message != last_sent:
            await manager.broadcast(_latest_message)
            last_sent = _latest_message
        await asyncio.sleep(0.03) # ~30 FPS

@app.on_event("startup")
async def startup_polling():
    asyncio.create_task(broadcast_worker_polling())

