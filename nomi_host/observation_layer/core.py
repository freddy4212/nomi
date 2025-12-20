"""
core.py - NOMI Observation Layer 核心模組

這個模組包含與 GUI 解耦的核心邏輯，可以：
- 作為獨立執行緒運行
- 被外部程式調用
- 支援 Headless（無 GUI）模式
- 未來整合到統一網頁介面

使用方式：
    # 作為執行緒運行
    core = ReceiverCore()
    core.start()  # 啟動執行緒
    ...
    core.stop()   # 停止執行緒
    
    # 或直接在當前執行緒運行（阻塞）
    core = ReceiverCore()
    core.run_blocking()
"""

# 處理導入路徑
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_base_dir = os.path.dirname(os.path.abspath(__file__))
if _base_dir not in sys.path:
    sys.path.insert(0, os.path.dirname(_base_dir))
if os.path.join(_base_dir, 'mmaction2') not in sys.path:
    sys.path.insert(0, os.path.join(_base_dir, 'mmaction2'))

try:
    from .config import config
    from .modules.action.recognizer import ActionRecognizerAsync
    from .modules.memory import MemoryBridge, create_memory_bridge_if_available
    from .modules.network.receiver import FrameData, NetworkReceiver
    from .modules.skeleton.processor import SkeletonFrame, SkeletonProcessor
except ImportError:
    from config import config
    from modules.action.recognizer import ActionRecognizerAsync
    from modules.memory import MemoryBridge, create_memory_bridge_if_available
    from modules.network.receiver import FrameData, NetworkReceiver
    from modules.skeleton.processor import SkeletonFrame, SkeletonProcessor


@dataclass
class ReceiverStatus:
    """Receiver 狀態資料"""
    is_running: bool = False
    is_connected: bool = False
    frame_count: int = 0
    fps: float = 0.0
    persons_detected: int = 0
    memory_events_sent: int = 0
    last_error: Optional[str] = None


@dataclass
class PersonActionInfo:
    """單一人物的動作識別結果"""
    person_id: int
    action_label: str = "等待識別"
    confidence: float = 0.0
    top_k_actions: List[tuple] = field(default_factory=list)
    skeleton_status: str = "等待偵測..."
    motion_status: str = "-"
    bbox: Optional[tuple] = None
    reid_name: Optional[str] = None


class ReceiverCore(threading.Thread):
    """
    NOMI Observation Layer 核心類別
    
    與 GUI 完全解耦的核心邏輯，可以：
    - 作為獨立執行緒運行
    - 被外部程式調用
    - 透過回調函式通知狀態變化
    """
    
    def __init__(
        self,
        on_frame_processed: Optional[Callable[[FrameData, Optional[SkeletonFrame]], None]] = None,
        on_action_recognized: Optional[Callable[[List[PersonActionInfo]], None]] = None,
        on_status_changed: Optional[Callable[[ReceiverStatus], None]] = None,
        on_connection_changed: Optional[Callable[[bool, Dict[str, Any]], None]] = None,
        enable_memory_bridge: bool = True,
    ):
        """
        初始化 Receiver 核心
        
        Args:
            on_frame_processed: 幀處理完成時的回調
            on_action_recognized: 動作識別結果更新時的回調
            on_status_changed: 狀態變化時的回調
            on_connection_changed: 連接狀態變化時的回調
            enable_memory_bridge: 是否啟用記憶層橋接
        """
        super().__init__(daemon=True, name="ReceiverCore")
        
        # 回調函式
        self.on_frame_processed = on_frame_processed
        self.on_action_recognized = on_action_recognized
        self.on_status_changed = on_status_changed
        self.on_connection_changed = on_connection_changed
        
        # 核心模組
        self.network_receiver = NetworkReceiver(on_frame_received=self._on_frame_received)
        self.skeleton_processor = SkeletonProcessor()
        self.action_recognizer = ActionRecognizerAsync()
        
        # 記憶層橋接
        self.memory_bridge: Optional[MemoryBridge] = None
        if enable_memory_bridge:
            self.memory_bridge = create_memory_bridge_if_available()
            if self.memory_bridge:
                self.debug_log("Memory Layer bridge initialized")
        
        # 設定網路接收器回調
        self.network_receiver.on_connection_changed = self._on_network_connection_changed
        
        # 狀態追蹤
        self._status = ReceiverStatus()
        self._status_lock = threading.Lock()
        self._frame_counter: int = 0
        self._stop_event = threading.Event()
        
        # 動作識別更新計時器
        self._last_action_update: float = 0.0
        self._action_update_interval: float = 0.5
        
        # FPS 計算
        self._fps_counter: int = 0
        self._fps_last_time: float = time.time()
        
        self.debug_log("ReceiverCore initialized")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[ReceiverCore][{time.time():.3f}] {msg}")
    
    # ==================== 公開介面 ====================
    
    def get_status(self) -> ReceiverStatus:
        """取得目前狀態"""
        with self._status_lock:
            return ReceiverStatus(
                is_running=self._status.is_running,
                is_connected=self._status.is_connected,
                frame_count=self._status.frame_count,
                fps=self._status.fps,
                persons_detected=self._status.persons_detected,
                memory_events_sent=self._status.memory_events_sent,
                last_error=self._status.last_error,
            )
    
    def get_connection_status(self) -> Dict[str, Any]:
        """取得連線狀態詳情"""
        return self.network_receiver.get_connection_status()
    
    def get_buffer_status(self) -> Dict[str, Any]:
        """取得骨架緩衝狀態"""
        return self.skeleton_processor.get_buffer_status()
    
    def get_current_actions(self) -> List[PersonActionInfo]:
        """取得當前所有人的動作識別結果"""
        results = []
        
        if not self.skeleton_processor.interpolated_buffer:
            return results
        
        latest_frame = self.skeleton_processor.interpolated_buffer[-1]
        if not latest_frame.persons:
            return results
        
        for person in latest_frame.persons:
            person_id = person.person_id
            result = self.action_recognizer.get_current_result(person_id)
            visibility = self.skeleton_processor.analyze_visibility(person_id)
            motion = self.skeleton_processor.get_motion_magnitude(person_id)
            
            # 骨架狀態描述
            if visibility['is_sitting_likely']:
                skel_status = f"可能坐著 (上:{visibility['upper_visible']}/11 下:{visibility['lower_visible']}/6)"
            elif visibility['is_full_body']:
                skel_status = f"全身可見 (上:{visibility['upper_visible']}/11 下:{visibility['lower_visible']}/6)"
            else:
                skel_status = f"部分可見 (上:{visibility['upper_visible']}/11 下:{visibility['lower_visible']}/6)"
            
            # 動作強度描述
            if motion < 5:
                motion_text = f"{motion:.1f} (靜止)"
            elif motion > 20:
                motion_text = f"{motion:.1f} (劇烈)"
            else:
                motion_text = f"{motion:.1f} (移動)"
            
            info = PersonActionInfo(
                person_id=person_id,
                action_label=result.action_label if result else "等待識別",
                confidence=result.confidence if result else 0.0,
                top_k_actions=result.top_k_actions if result else [],
                skeleton_status=skel_status,
                motion_status=motion_text,
                bbox=person.box,
            )
            results.append(info)
        
        return results
    
    def start_receiving(self) -> bool:
        """
        開始接收資料
        
        Returns:
            是否啟動成功
        """
        success = self.network_receiver.start()
        if success:
            self.skeleton_processor.clear()
            self._frame_counter = 0
            self.action_recognizer.start()
            
            if self.memory_bridge:
                try:
                    self.memory_bridge.start()
                    self.debug_log("Memory Layer started")
                except Exception as e:
                    self.debug_log(f"Failed to start Memory Layer: {e}")
            
            with self._status_lock:
                self._status.is_running = True
            
            self._notify_status_change()
            self.debug_log("Started receiving")
        return success
    
    def stop_receiving(self):
        """停止接收資料"""
        self.network_receiver.stop()
        self.action_recognizer.stop()
        self.skeleton_processor.clear()
        
        if self.memory_bridge:
            self.memory_bridge.stop()
            self.debug_log("Memory Layer stopped")
        
        with self._status_lock:
            self._status.is_running = False
        
        self._notify_status_change()
        self.debug_log("Stopped receiving")
    
    def load_model(self) -> bool:
        """
        載入 MMAction2 模型
        
        Returns:
            是否載入成功
        """
        try:
            return self.action_recognizer.recognizer.load_model()
        except Exception as e:
            self.debug_log(f"Failed to load model: {e}")
            return False
    
    # ==================== 執行緒模式 ====================
    
    def run(self):
        """執行緒主迴圈"""
        self.debug_log("ReceiverCore thread started")
        
        # 嘗試載入模型
        self.load_model()
        
        # 自動開始接收
        self.start_receiving()
        
        # 主迴圈：定期更新狀態
        while not self._stop_event.is_set():
            try:
                # 更新 FPS
                self._update_fps()
                
                # 檢查連線狀態
                if self.network_receiver.check_connection_state():
                    status_info = self.network_receiver.get_connection_status()
                    with self._status_lock:
                        self._status.is_connected = self.network_receiver.is_connected
                    
                    if self.on_connection_changed:
                        self.on_connection_changed(
                            self.network_receiver.is_connected,
                            status_info
                        )
                
                # 更新記憶層狀態
                if self.memory_bridge:
                    with self._status_lock:
                        self._status.memory_events_sent = self.memory_bridge.events_sent
                
                time.sleep(0.5)
                
            except Exception as e:
                self.debug_log(f"Error in main loop: {e}")
                with self._status_lock:
                    self._status.last_error = str(e)
        
        # 清理
        self.stop_receiving()
        self.debug_log("ReceiverCore thread stopped")
    
    def stop(self):
        """停止執行緒"""
        self.debug_log("Stopping ReceiverCore...")
        self._stop_event.set()
    
    def run_blocking(self):
        """
        在當前執行緒中阻塞運行（非執行緒模式）
        適用於簡單的 CLI 使用場景
        """
        self.debug_log("Running in blocking mode")
        self.load_model()
        self.start_receiving()
        
        try:
            while not self._stop_event.is_set():
                self._update_fps()
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.debug_log("Interrupted")
        finally:
            self.stop_receiving()
    
    # ==================== 內部邏輯 ====================
    
    def _on_frame_received(self, frame_data: FrameData):
        """幀資料接收回調（在背景執行緒中調用）"""
        self._frame_counter += 1
        self._fps_counter += 1
        
        with self._status_lock:
            self._status.frame_count = self._frame_counter
        
        # 處理骨架資料
        skeleton_frame = self.skeleton_processor.process_frame(frame_data)
        
        # 更新偵測到的人數
        if skeleton_frame:
            with self._status_lock:
                self._status.persons_detected = len(skeleton_frame.persons)
        
        # 發送到記憶層
        if self.memory_bridge:
            self._send_to_memory_layer()
        
        # 通知回調
        if self.on_frame_processed:
            self.on_frame_processed(frame_data, skeleton_frame)
        
        # 嘗試動作識別
        if time.time() - self._last_action_update >= self._action_update_interval:
            self._try_action_recognition()
            self._last_action_update = time.time()
            
            # 通知動作識別結果
            if self.on_action_recognized:
                actions = self.get_current_actions()
                self.on_action_recognized(actions)
    
    def _on_network_connection_changed(self, connected: bool):
        """網路連接狀態變更回調"""
        with self._status_lock:
            self._status.is_connected = connected
        
        status_info = self.network_receiver.get_connection_status()
        
        if self.on_connection_changed:
            self.on_connection_changed(connected, status_info)
        
        self._notify_status_change()
    
    def _update_fps(self):
        """更新 FPS 計算"""
        current_time = time.time()
        elapsed = current_time - self._fps_last_time
        
        if elapsed >= 1.0:
            with self._status_lock:
                self._status.fps = self._fps_counter / elapsed
            self._fps_counter = 0
            self._fps_last_time = current_time
    
    def _notify_status_change(self):
        """通知狀態變化"""
        if self.on_status_changed:
            self.on_status_changed(self.get_status())
    
    def _send_to_memory_layer(self):
        """發送感知資料到記憶層"""
        try:
            if not self.skeleton_processor.interpolated_buffer:
                return
            
            latest_frame = self.skeleton_processor.interpolated_buffer[-1]
            if not latest_frame.persons:
                return
            
            for person in latest_frame.persons:
                person_id = person.person_id
                result = self.action_recognizer.get_current_result(person_id)
                motion = self.skeleton_processor.get_motion_magnitude(person_id)
                bbox = person.box
                reid_vector = person.reid_vector
                
                matched_member_id = None
                if reid_vector is not None and self.memory_bridge:
                    match = self.memory_bridge.find_nearest_member(reid_vector, threshold=0.3)
                    if match:
                        matched_member_id = match['member_id']
                
                action_label = "偵測中"
                action_confidence = 0.0
                action_candidates = []
                action_duration = 0.0
                
                if result:
                    action_label = result.simplified_label or result.action_label
                    action_confidence = result.confidence
                    action_candidates = result.top_k_actions if result.top_k_actions else []
                    action_duration = result.duration
                
                self.memory_bridge.send_action_result(
                    person_id=person_id,
                    frame_no=self._frame_counter,
                    bbox=bbox,
                    action_label=action_label,
                    action_confidence=action_confidence,
                    action_candidates=action_candidates,
                    action_duration=action_duration,
                    motion_magnitude=motion,
                    reid_vector=reid_vector,
                    matched_member_id=matched_member_id,
                    environment={"room": config.room_name}
                )
                
        except Exception as e:
            self.debug_log(f"Memory bridge error: {e}")
    
    def _try_action_recognition(self):
        """嘗試進行動作識別"""
        try:
            sequences = self.skeleton_processor.get_all_skeleton_sequences()
            
            if sequences:
                sequences_info = {}
                for person_id, sequence in sequences.items():
                    motion = self.skeleton_processor.get_motion_magnitude(person_id)
                    visibility = self.skeleton_processor.analyze_visibility(person_id)
                    
                    bbox = None
                    if self.skeleton_processor.interpolated_buffer:
                        latest_frame = self.skeleton_processor.interpolated_buffer[-1]
                        for p in latest_frame.persons:
                            if p.person_id == person_id:
                                bbox = p.box
                                break
                    
                    sequences_info[person_id] = {
                        'sequence': sequence,
                        'motion': motion,
                        'visibility': visibility,
                        'bbox': bbox
                    }
                
                self.action_recognizer.submit(sequences_info)
                
        except Exception as e:
            self.debug_log(f"Action recognition error: {e}")
