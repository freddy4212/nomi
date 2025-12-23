"""
core.py - NOMI 系統編排器 (Slim Hub)

職責：
- 作為系統中樞，協調各模組
- 轉發資料到前端 WebSocket
"""

import asyncio
import base64
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

try:
    from memory_layer.config import memory_config
except ImportError:
    memory_config = None

from observation_layer.modules.visualization.visualizer import SkeletonPlayer

from .layers import LayerManager
from .processor import DataProcessor


@dataclass
class DeviceInfo:
    id: str = "Unknown"
    name: str = "Unknown"
    version: str = "Unknown"
    model: str = "Unknown"

class NOMIOrchestrator:
    def __init__(self):
        # 核心組件
        self.layers = LayerManager(
            on_memory_event=self._on_memory_event,
            on_frame_processed=self._on_frame_processed,
            on_action_recognized=self._on_action_recognized
        )
        
        # 狀態快取
        self.device_info = DeviceInfo()
        self.view_mode = "overlay"  # original, overlay, yolo_only, interpolated
        self.skeleton_player = SkeletonPlayer()
        self._latest_actions = []
        self._message_buffer: Optional[str] = None
        self._last_active_time = {"tcp": 0, "db": 0}
        self._last_db_events_written = 0
        self._last_frame_data = None
        self._interpolation_task = None
        
        # 錄製狀態
        self.is_recording = False
        self.recording_name = ""
        self.recording_vectors = []
        
        # 通訊
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_event_update: Optional[Callable[[str], None]] = None
        self._video_broadcast: Optional[Callable[[str], None]] = None  # Direct video broadcast
        
        print("[Orchestrator] Slim Hub Initialized")

    # ==================== 生命週期 ====================
    def set_event_loop(self, loop: asyncio.AbstractEventLoop): self.loop = loop
    def set_callbacks(self, on_event_update: Optional[Callable[[str], None]] = None, on_video_broadcast: Optional[Callable[[str], None]] = None, **kwargs):
        self._on_event_update = on_event_update
        self._video_broadcast = on_video_broadcast

    def start_system(self): self.layers.start_all()
    def stop_system(self): self.layers.stop_all()
    def get_message_buffer(self) -> Optional[str]: return self._message_buffer

    def set_view_mode(self, mode: str):
        if mode in ["original", "overlay", "yolo_only", "interpolated"]:
            self.view_mode = mode
            print(f"[Orchestrator] View mode set to: {mode}")
            
            # Manage interpolation task
            if mode == "interpolated":
                self._start_interpolation_loop()
            else:
                self._stop_interpolation_loop()
                
            return True
        return False

    def _start_interpolation_loop(self):
        if self._interpolation_task is None or self._interpolation_task.done():
            if self.loop:
                self._interpolation_task = self.loop.create_task(self._run_interpolation_loop())

    def _stop_interpolation_loop(self):
        if self._interpolation_task and not self._interpolation_task.done():
            self._interpolation_task.cancel()
            self._interpolation_task = None

    async def _run_interpolation_loop(self):
        """
        播放補幀動畫的獨立迴圈
        """
        print("[Orchestrator] Starting interpolation loop")
        frame_count = 0
        
        # 獲取目標 FPS
        target_fps = 15
        if self.layers.observation_core and hasattr(self.layers.observation_core, 'config'):
            target_fps = self.layers.observation_core.config.interpolation.target_fps
        
        base_interval_ms = 1000.0 / target_fps
        print(f"[Orchestrator] Target FPS: {target_fps}, Base Interval: {base_interval_ms:.1f}ms")
        
        # 使用 clear() 而不是 reset()，確保重置 _last_consumed_count 並從頭開始拉取緩存
        self.skeleton_player.clear()
        
        try:
            while self.view_mode == "interpolated":
                loop_start = time.time()
                
                if self._last_frame_data:
                    # 使用線性獲取，避免智慧調速造成的卡頓
                    interp_frame = self.skeleton_player.get_next_frame_linear()
                    
                    # 渲染 (如果沒有補幀資料，則退而求其次顯示原始 OSD)
                    rendered = DataProcessor.render_frame(
                        self._last_frame_data, 
                        interp_frame, 
                        self.layers.observation_core, 
                        "interpolated" if interp_frame else "overlay", 
                        None
                    )
                    
                    if rendered is not None:
                        # 這裡我們手動呼叫 encode_image 並指定較低的品質
                        _, buf = cv2.imencode('.jpg', rendered, [cv2.IMWRITE_JPEG_QUALITY, 50])
                        img_b64 = base64.b64encode(buf).decode('utf-8')
                        
                        # 收集狀態
                        status, events_written = DataProcessor.collect_status(
                            self._last_frame_data, self.layers.observation_core, self.layers.memory_core,
                            self.device_info, self._last_active_time, self._last_db_events_written,
                            memory_config
                        )
                        self._last_db_events_written = events_written
                        
                        message = {
                            "type": "frame_update", "timestamp": time.time(), "image": img_b64,
                            "meta": status, "persons": self._get_persons_list(), "status": "running"
                        }
                        msg_str = json.dumps(message)
                        
                        if self._video_broadcast:
                            await self._video_broadcast(msg_str)
                        else:
                            self._message_buffer = msg_str
                
                # 動態調整間隔
                buf_status = self.skeleton_player.get_buffer_status()
                remaining = buf_status.get("remaining", 0)
                
                if remaining <= 2:
                    interval_ms = base_interval_ms * 1.5  # 緩衝不足，減速
                elif remaining > 20:
                    interval_ms = base_interval_ms * 0.8  # 緩衝過多，加速
                else:
                    interval_ms = base_interval_ms
                
                # Debug log
                frame_count += 1
                if frame_count % 30 == 0:
                    print(f"[Interpolation] Frame #{frame_count} | Remaining: {remaining} | Interval: {interval_ms:.1f}ms")
                
                elapsed = time.time() - loop_start
                sleep_time = max(0.001, (interval_ms / 1000.0) - elapsed)
                await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            print("[Orchestrator] Interpolation loop cancelled")
        except Exception as e:
            print(f"[Orchestrator] Interpolation loop error: {e}")
            import traceback
            traceback.print_exc()

    def start_recording(self, name: str):
        if not self.layers.observation_core: return False, "感知層未啟動"
        
        # 檢查是否只有一個人
        status = self.layers.observation_core.get_status()
        if status.persons_detected != 1:
            return False, "只能在畫面中只有一個人的情況下開始錄製"
        
        self.is_recording = True
        self.recording_name = name
        self.recording_vectors = []
        print(f"[Orchestrator] Started recording for: {name}")
        return True, "開始錄製"

    def stop_recording(self):
        if not self.is_recording: return False
        
        success = False
        if self.recording_vectors:
            avg_vector = np.mean(self.recording_vectors, axis=0)
            norm = np.linalg.norm(avg_vector)
            if norm > 0: avg_vector = avg_vector / norm
            
            if self.layers.observation_core.memory_bridge:
                self.layers.observation_core.memory_bridge.register_member(self.recording_name, avg_vector)
                success = True
        
        self.is_recording = False
        self.recording_name = ""
        self.recording_vectors = []
        print(f"[Orchestrator] Stopped recording. Success: {success}")
        return success

    def get_system_status(self) -> Dict:
        """取得當前系統狀態 (用於 Data Channel 廣播)"""
        status, events_written = DataProcessor.collect_status(
            None, self.layers.observation_core, self.layers.memory_core,
            self.device_info, self._last_active_time, self._last_db_events_written,
            memory_config
        )
        self._last_db_events_written = events_written
        return status

    # ==================== 查詢代理 (直接調用各層) ====================
    def get_recent_events(self, **kwargs): return self.layers.memory_core._db.get_recent_events(**kwargs) if self.layers.memory_core else []
    def get_member_states(self): return self.layers.memory_core._db.get_member_states() if self.layers.memory_core else []
    def get_all_members(self):
        if not self.layers.memory_core: return []
        return self.layers.memory_core._db.query("SELECT member_id as id, name, sample_count, updated_at FROM member_registry ORDER BY member_id ASC")
    
    def delete_member(self, member_id: int):
        if not self.layers.memory_core: return False
        return self.layers.memory_core._db.delete_member_by_id(member_id)
        
    def update_member_name(self, member_id: int, new_name: str):
        if not self.layers.memory_core: return False
        return self.layers.memory_core._db.update_member_name(member_id, new_name)

    def clear_all_events(self): return self.layers.memory_core.clear_all_events() if self.layers.memory_core else False

    # ==================== 資料流處理 ====================
    def _on_frame_processed(self, frame_data, skeleton_frame):
        # Cache frame data for interpolation loop
        self._last_frame_data = frame_data

        # Connect skeleton_player to processor (like GUI does)
        if self.layers.observation_core and self.layers.observation_core.skeleton_processor:
            if self.skeleton_player.processor is None:
                self.skeleton_player.processor = self.layers.observation_core.skeleton_processor
                print("[Orchestrator] SkeletonPlayer connected to processor")
        
        # If in interpolated mode, skip normal rendering/sending
        # The interpolation loop will handle it
        if self.view_mode == "interpolated":
            # Ensure the loop is running (in case it wasn't started properly)
            self._start_interpolation_loop()
            return

        # 1. 渲染與編碼
        rendered = DataProcessor.render_frame(frame_data, skeleton_frame, self.layers.observation_core, self.view_mode, self.skeleton_player)
        img_b64 = DataProcessor.encode_image(rendered)
        
        # 2. 更新快取
        self._update_device_cache(frame_data)
        
        # 3. 處理錄製邏輯
        if self.is_recording:
            persons = skeleton_frame.persons if skeleton_frame and hasattr(skeleton_frame, 'persons') else []
            if len(persons) > 1:
                # 多於一人，立刻停止
                self.is_recording = False
                self.recording_name = ""
                self.recording_vectors = []
                if self.loop and self._on_event_update:
                    msg = json.dumps({"type": "recording_status", "status": "error", "message": "偵測到多於一人，錄製已停止"})
                    self.loop.call_soon_threadsafe(lambda: self._on_event_update(msg))
            elif len(persons) == 1:
                person = persons[0]
                if hasattr(person, 'reid_vector') and person.reid_vector is not None:
                    self.recording_vectors.append(person.reid_vector)
                    # 通知進度
                    if self.loop and self._on_event_update:
                        msg = json.dumps({
                            "type": "recording_status", 
                            "status": "recording", 
                            "progress": len(self.recording_vectors),
                            "max": 30
                        })
                        self.loop.call_soon_threadsafe(lambda: self._on_event_update(msg))
                    
                    if len(self.recording_vectors) >= 30:
                        success = self.stop_recording()
                        if self.loop and self._on_event_update:
                            msg = json.dumps({
                                "type": "recording_status", 
                                "status": "completed" if success else "error",
                                "message": "錄製完成" if success else "錄製失敗"
                            })
                            self.loop.call_soon_threadsafe(lambda: self._on_event_update(msg))

        # 4. 收集狀態並組裝
        status, events_written = DataProcessor.collect_status(
            frame_data, self.layers.observation_core, self.layers.memory_core,
            self.device_info, self._last_active_time, self._last_db_events_written,
            memory_config
        )
        self._last_db_events_written = events_written
        
        message = {
            "type": "frame_update", "timestamp": time.time(), "image": img_b64,
            "meta": status, "persons": self._get_persons_list(), "status": "running"
        }
        self._message_buffer = json.dumps(message)

    def _on_action_recognized(self, actions): self._latest_actions = actions

    def _on_memory_event(self, event):
        data = {k: getattr(event, k, None) for k in ['timestamp', 'person_id', 'frame_no', 'bbox', 'action_label', 'action_confidence', 'action_duration', 'motion_magnitude', 'member_name']}
        msg = json.dumps({"type": "new_event", "data": data}, default=str)
        if self.loop and self._on_event_update:
            self.loop.call_soon_threadsafe(lambda: self._on_event_update(msg))

    def _update_device_cache(self, frame_data):
        lookup = {**getattr(frame_data, 'basic_info', {}), **getattr(frame_data, 'raw_data', {})}
        if any(k in lookup for k in ['device_id', 'ID', 'id']):
            self.device_info.id = lookup.get('device_id', lookup.get('ID', lookup.get('id')))
        if any(k in lookup for k in ['ver', 'version']):
            self.device_info.version = lookup.get('ver', lookup.get('version'))
        if any(k in lookup for k in ['name', 'Model', 'model']):
            self.device_info.model = self.device_info.name = lookup.get('name', lookup.get('Model', lookup.get('model')))

    def _get_persons_list(self) -> List[Dict]:
        return [
            {
                "id": a.person_id, 
                "action": a.action_label, 
                "confidence": a.confidence, 
                "reid_name": a.reid_name,
                "reid_confidence": a.reid_confidence,
                "skeleton_status": a.skeleton_status,
                "motion_status": a.motion_status,
                "duration": a.duration,
                "bbox": a.bbox
            } for a in self._latest_actions
        ]
