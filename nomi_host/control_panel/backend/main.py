"""
main.py - NOMI Control Panel Backend 入口

這是一個精簡的入口點，實際邏輯已模組化到 modules/ 目錄下。
"""

import asyncio
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- 路徑設定 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
nomi_host_dir = os.path.dirname(os.path.dirname(current_dir))
if nomi_host_dir not in sys.path:
    sys.path.insert(0, nomi_host_dir)

# 確保可以導入 mmaction2
mmaction2_dir = os.path.join(nomi_host_dir, "observation_layer", "mmaction2")
if os.path.exists(mmaction2_dir) and mmaction2_dir not in sys.path:
    sys.path.insert(0, mmaction2_dir)

# --- 導入模組 ---
from control_panel.backend.modules.orchestrator import NOMIOrchestrator
from control_panel.backend.modules.websocket import setup_websocket_routes

# --- FastAPI 設定 ---
app = FastAPI(
    title="NOMI Control Panel Backend",
    description="統一管理 Observation、Memory、Inference 三大核心層",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 全域實例 ---
orchestrator = NOMIOrchestrator()
ws_router = None
data_queue: asyncio.Queue = asyncio.Queue()


# --- WebSocket 路由設定 ---
ws_router = setup_websocket_routes(app, orchestrator)


# --- 背景任務 ---
async def buffer_polling_worker():
    """輪詢訊息緩衝並廣播到 Video Channel"""
    last_sent = None
    while True:
        buffer = orchestrator.get_message_buffer()
        if buffer and buffer != last_sent:
            await ws_router.video_manager.broadcast(buffer)
            last_sent = buffer
        await asyncio.sleep(0.03)  # ~30 FPS


async def data_broadcast_worker():
    """從 Queue 取出資料並廣播到 Data Channel"""
    while True:
        message = await data_queue.get()
        await ws_router.data_manager.broadcast(message)


async def status_broadcast_worker():
    """定期廣播系統狀態到 Data Channel (1Hz)"""
    import json
    while True:
        try:
            status = orchestrator.get_system_status()
            message = json.dumps({
                "type": "status_update",
                "meta": status
            })
            await ws_router.data_manager.broadcast(message)
        except Exception as e:
            print(f"[Backend] Status broadcast error: {e}")
        await asyncio.sleep(0.1)


# --- 生命週期事件 ---
@app.on_event("startup")
async def startup_event():
    """應用啟動時執行"""
    # 設定事件循環
    loop = asyncio.get_running_loop()
    orchestrator.set_event_loop(loop)
    
    # 設定事件回調
    orchestrator.set_callbacks(
        on_event_update=lambda msg: data_queue.put_nowait(msg),
        on_video_broadcast=ws_router.video_manager.broadcast
    )
    
    # 啟動背景任務
    asyncio.create_task(buffer_polling_worker())
    asyncio.create_task(data_broadcast_worker())
    asyncio.create_task(status_broadcast_worker())
    
    # 啟動系統
    orchestrator.start_system()
    
    print("[Backend] System started")


@app.on_event("shutdown")
async def shutdown_event():
    """應用關閉時執行"""
    orchestrator.stop_system()
    print("[Backend] System stopped")


# --- 健康檢查 ---
@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {
        "status": "ok",
        "video_clients": ws_router.video_manager.connection_count,
        "data_clients": ws_router.data_manager.connection_count
    }


# --- 主函式 ---
def main():
    """啟動後端服務"""
    print("=" * 50)
    print("   NOMI Control Panel - Backend v2.0")
    print("=" * 50)
    print("Starting WebSocket Server on 0.0.0.0:8000")
    print("")
    print("Endpoints:")
    print("  - WS Video: ws://localhost:8000/ws/video")
    print("  - WS Data:  ws://localhost:8000/ws/data")
    print("  - Health:   http://localhost:8000/health")
    print("")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
