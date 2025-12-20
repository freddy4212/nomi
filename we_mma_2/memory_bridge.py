"""
memory_bridge.py - 感知層與記憶層的橋接模組

這個模組負責：
- 將 ActionRecognizer 的輸出轉換為 PerceptionEvent
- 打上 Unix 時間標籤
- 發送到記憶層的 MemoryQueue

使用方式：
    from we_mma_2.memory_bridge import MemoryBridge
    
    bridge = MemoryBridge(memory_queue)
    bridge.send_action_result(person_id, result, frame_data, ...)
"""

from __future__ import annotations

import os
import queue
import sys
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# 將上層目錄加入路徑以便導入 home_agent_memory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 類型提示用（避免運行時導入問題）
if TYPE_CHECKING:
    from home_agent_memory.data_models import PerceptionEvent

# 標記是否成功導入 home_agent_memory
_MEMORY_AVAILABLE = False

try:
    from home_agent_memory.data_models import (ActionCandidate, BoundingBox,
                                               EnvironmentData)
    from home_agent_memory.data_models import \
        PerceptionEvent as _PerceptionEvent
    from home_agent_memory.data_models import create_perception_event
    _MEMORY_AVAILABLE = True
except ImportError:
    # 如果 home_agent_memory 尚未安裝，提供一個空的佔位
    print("[MemoryBridge] Warning: home_agent_memory not found, bridge disabled")
    _PerceptionEvent = None
    BoundingBox = None
    ActionCandidate = None
    EnvironmentData = None
    create_perception_event = None

try:
    from .config import config
except ImportError:
    from config import config


class MemoryBridge:
    """
    感知層與記憶層的橋接器
    
    負責將 Receiver 的動作識別結果轉換為標準化的 PerceptionEvent，
    並發送到記憶層。
    """
    
    def __init__(self, memory_queue: Optional[queue.Queue] = None):
        """
        初始化橋接器
        
        Args:
            memory_queue: 記憶層的輸入隊列，若為 None 則只記錄不發送
        """
        self.memory_queue = memory_queue
        self._enabled = memory_queue is not None and _MEMORY_AVAILABLE
        self._events_sent = 0
        
        # 過濾短暫出現的異常人物 (Debouncing)
        self.pending_persons: Dict[int, Dict[str, Any]] = {}
        self.verified_persons: set[int] = set()
        self.min_duration_threshold = 1.0  # 至少持續出現 1.0 秒才寫入記憶層
        self.last_cleanup_time = time.time()
        
        # 動作穩定性緩衝 (Action Stability)
        self.action_buffer: Dict[int, List[Any]] = {} # {person_id: [events]}
        self.action_delay = 1.0  # 動作確認延遲時間 (秒)
        
        self.debug_log(f"MemoryBridge initialized (enabled={self._enabled})")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[MemoryBridge][{time.time():.3f}] {msg}")
    
    @property
    def enabled(self) -> bool:
        """橋接器是否啟用"""
        return self._enabled
    
    @property
    def events_sent(self) -> int:
        """已發送的事件數"""
        return self._events_sent
    
    def start(self):
        """啟動記憶層（如果可用）"""
        if hasattr(self, '_memory_layer') and self._memory_layer is not None:
            if self._memory_layer.is_alive():
                self.debug_log("Memory Layer thread already running")
                return
                
            try:
                self._memory_layer.start()
                self.debug_log("Memory Layer thread started")
            except RuntimeError:
                # 執行緒已經啟動過且已結束，無法重啟，需要重新建立
                self.debug_log("Memory Layer thread already finished, recreating...")
                self._recreate_memory_layer()
                self._memory_layer.start()
                self.debug_log("Memory Layer thread recreated and started")
    
    def _recreate_memory_layer(self):
        """重新建立記憶層執行緒（當舊執行緒已結束時）"""
        if not _MEMORY_AVAILABLE:
            return
            
        try:
            from home_agent_memory.memory_layer import MemoryLayer

            # 使用原有的隊列重新建立執行緒
            new_layer = MemoryLayer(
                input_queue=self.memory_queue,
                inference_queue=self._inference_queue
            )
            self._memory_layer = new_layer
            self.debug_log("Memory Layer thread object recreated")
        except Exception as e:
            self.debug_log(f"Failed to recreate memory layer: {e}")

    def stop(self):
        """停止記憶層（如果可用）"""
        if hasattr(self, '_memory_layer') and self._memory_layer is not None:
            if self._memory_layer.is_alive():
                self._memory_layer.stop()
                self.debug_log(f"Memory Layer stop signal sent. Total events sent: {self._events_sent}")
            else:
                self.debug_log("Memory Layer thread is not running")
    
    # ==================== 成員管理 (ReID) ====================
    
    def register_member(self, name: str, vector: Any) -> int:
        """
        註冊或更新成員向量
        
        Args:
            name: 成員名稱
            vector: ReID 特徵向量 (List 或 np.ndarray)
            
        Returns:
            成員 ID，失敗返回 -1
        """
        if not self._enabled or not hasattr(self, '_client'):
            return -1
        
        # 確保向量是列表格式
        if hasattr(vector, 'tolist'):
            vector = vector.tolist()
            
        return self._client.register_member(name, vector)

    def delete_member(self, name: str) -> bool:
        """刪除成員"""
        if not self._enabled or not hasattr(self, '_client'):
            return False
        return self._client.delete_member(name)

    def delete_all_members(self) -> bool:
        """刪除所有成員"""
        if not self._enabled or not hasattr(self, '_client'):
            return False
        return self._client.delete_all_members()

    def get_all_members(self) -> List[Dict[str, Any]]:
        """取得所有成員"""
        if not self._enabled or not hasattr(self, '_client'):
            return []
        return self._client.get_all_members()

    def find_nearest_member(self, vector: Any, threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        尋找最接近的成員
        
        Args:
            vector: 待比對的向量
            threshold: 距離閾值
            
        Returns:
            成員資料字典，包含 member_id, name, distance
        """
        if not self._enabled or not hasattr(self, '_client'):
            return None
            
        # 確保向量是列表格式
        if hasattr(vector, 'tolist'):
            vector = vector.tolist()
            
        return self._client.find_nearest_member(vector, threshold)

    def send_action_result(
        self,
        person_id: int,
        frame_no: int,
        bbox: Tuple[int, int, int, int],
        action_label: str,
        action_confidence: float,
        action_candidates: List[Tuple[str, float]],
        action_duration: float = 0.0,
        motion_magnitude: float = 0.0,
        reid_vector: Optional[List[float]] = None,
        matched_member_id: Optional[int] = None,
        environment: Optional[Dict[str, Any]] = None,
        source_device: str = "WiseEye2",
    ) -> bool:
        """
        發送動作識別結果到記憶層
        
        Args:
            person_id: 人物臨時 ID
            frame_no: 幀序號
            bbox: 邊界框 (x, y, w, h)
            action_label: 動作標籤
            action_confidence: 動作信心度
            action_candidates: 候選動作列表 [(label, confidence), ...]
            action_duration: 動作持續時間 (秒)
            motion_magnitude: 動作幅度
            reid_vector: ReID 特徵向量 (可選)
            matched_member_id: 匹配到的成員 ID (可選)
            environment: 環境資訊 (可選)
            source_device: 資料來源裝置
            
        Returns:
            是否發送成功
        """
        if not self._enabled:
            return False
        
        try:
            # 使用工廠函數建立事件 (會自動打上時間戳)
            event = create_perception_event(
                person_id=person_id,
                frame_no=frame_no,
                bbox=bbox,
                action_label=action_label,
                action_confidence=action_confidence,
                action_candidates=action_candidates,
                action_duration=action_duration,
                motion_magnitude=motion_magnitude,
                reid_vector=reid_vector,
                matched_member_id=matched_member_id,
                environment=environment,
                source_device=source_device,
            )
            
            # === 過濾邏輯 (Debouncing) ===
            
            # 1. 如果已經是驗證過的人物，進入動作穩定性處理
            if person_id in self.verified_persons:
                self._process_action_stability(person_id, event)
                return True
            
            # 2. 如果是新人物，加入待驗證清單
            current_time = time.time()
            if person_id not in self.pending_persons:
                self.pending_persons[person_id] = {
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'events': []
                }
            
            # 更新最後看到時間並暫存事件
            person_data = self.pending_persons[person_id]
            person_data['last_seen'] = current_time
            person_data['events'].append(event)
            
            # 3. 檢查是否滿足持續時間條件
            duration = current_time - person_data['first_seen']
            if duration >= self.min_duration_threshold:
                self.debug_log(f"Person {person_id} verified (duration: {duration:.2f}s), flushing {len(person_data['events'])} events")
                
                # 標記為已驗證
                self.verified_persons.add(person_id)
                
                # 發送所有暫存事件到動作穩定性處理
                for buffered_event in person_data['events']:
                    self._process_action_stability(person_id, buffered_event)
                
                # 清除暫存
                del self.pending_persons[person_id]
            
            # 4. 定期清理過期的待驗證人物 (每 5 秒清理一次)
            if current_time - self.last_cleanup_time > 5.0:
                self._cleanup_pending_persons(current_time)
                self.last_cleanup_time = current_time
                
            return True
            
        except Exception as e:
            self.debug_log(f"Failed to send action result: {e}")
            return False
    
    def _process_action_stability(self, person_id: int, event: "PerceptionEvent"):
        """
        處理動作穩定性
        
        將事件加入緩衝區，並在延遲後確認動作標籤。
        這可以過濾掉短暫的誤判動作。
        """
        if person_id not in self.action_buffer:
            self.action_buffer[person_id] = []
            
        buffer = self.action_buffer[person_id]
        buffer.append(event)
        
        # 檢查緩衝區是否足夠長
        # 我們需要確保緩衝區覆蓋了 action_delay 的時間範圍
        if not buffer:
            return
            
        last_time = buffer[-1].timestamp
        
        # 處理所有超過延遲時間的事件
        while buffer:
            oldest_event = buffer[0]
            time_diff = last_time - oldest_event.timestamp
            
            if time_diff >= self.action_delay:
                # 緩衝區已滿，可以確認最舊的事件
                # 在當前緩衝區中進行投票，決定該事件的最終動作
                confirmed_action = self._vote_action(buffer)
                
                # 更新動作標籤 (如果與原始不同)
                if confirmed_action != oldest_event.action_label:
                    # self.debug_log(f"Action corrected: {oldest_event.action_label} -> {confirmed_action}")
                    oldest_event.action_label = confirmed_action
                
                # 發送事件
                self._send_to_queue(oldest_event)
                
                # 移除已處理的事件
                buffer.pop(0)
            else:
                # 最舊的事件還沒超過延遲時間，停止處理
                break
    
    def _vote_action(self, events: List["PerceptionEvent"]) -> str:
        """
        對緩衝區內的動作進行投票
        
        Returns:
            出現頻率最高的動作標籤
        """
        if not events:
            return "Unknown"
            
        counts = {}
        for e in events:
            label = e.action_label
            counts[label] = counts.get(label, 0) + 1
            
        # 找出出現次數最多的動作
        return max(counts, key=counts.get)

    def _cleanup_pending_persons(self, current_time: float):
        """清理長時間未更新的待驗證人物"""
        timeout = 2.0  # 如果 2 秒沒出現，視為消失
        to_remove = []
        
        for pid, data in self.pending_persons.items():
            if current_time - data['last_seen'] > timeout:
                to_remove.append(pid)
        
        for pid in to_remove:
            del self.pending_persons[pid]
            # 也可以選擇從 verified_persons 移除，如果希望重新驗證
            # 但通常 ID 是由追蹤器維護的，如果追蹤器丟失 ID，下次會是新 ID
            if pid in self.verified_persons:
                self.verified_persons.remove(pid)
                # 清理該人物的動作緩衝區
                if pid in self.action_buffer:
                    # 可以選擇將剩餘的事件發送出去，或者丟棄
                    # 這裡選擇發送，避免最後幾秒的資料遺失
                    for event in self.action_buffer[pid]:
                        self._send_to_queue(event)
                    del self.action_buffer[pid]
            self.debug_log(f"Cleaned up stale person {pid}")
    
    def send_visibility_change(
        self,
        person_id: int,
        frame_no: int,
        last_bbox: Tuple[int, int, int, int],
        is_visible: bool,
        disappear_direction: Optional[str] = None,
    ) -> bool:
        """
        發送可見性變化事件 (人物消失/出現)
        
        Args:
            person_id: 人物 ID
            frame_no: 幀序號
            last_bbox: 最後已知的邊界框
            is_visible: 是否可見
            disappear_direction: 消失方向 (left, right, top, bottom)
            
        Returns:
            是否發送成功
        """
        if not self._enabled:
            return False
        
        try:
            event = PerceptionEvent(
                timestamp=time.time(),
                frame_no=frame_no,
                person_id=person_id,
                bbox=BoundingBox.from_tuple(last_bbox) if last_bbox else None,
                visibility=is_visible,
                action_label="Invisible" if not is_visible else "Appeared",
                action_confidence=1.0,
                action_candidates=[],
            )
            
            self._send_to_queue(event)
            return True
            
        except Exception as e:
            self.debug_log(f"Failed to send visibility change: {e}")
            return False
    
    def _send_to_queue(self, event: "PerceptionEvent"):
        """發送事件到隊列"""
        if self.memory_queue is None:
            self.debug_log("Queue is None, cannot send event")
            return
        
        try:
            # 非阻塞發送，如果隊列滿了則丟棄最舊的
            if self.memory_queue.full():
                try:
                    self.memory_queue.get_nowait()
                    self.debug_log("Queue full, dropped oldest event")
                except queue.Empty:
                    pass
            
            self.memory_queue.put_nowait(event)
            self._events_sent += 1
            
            # 每 10 筆輸出一次日誌
            if self._events_sent % 10 == 0:
                self.debug_log(f"Events sent: {self._events_sent}, queue size: {self.memory_queue.qsize()}")
            
        except Exception as e:
            self.debug_log(f"Queue send error: {e}")


def create_memory_bridge_if_available() -> Optional["MemoryBridge"]:
    """
    工廠函數：嘗試建立記憶橋接器
    
    如果 home_agent_memory 模組可用，則建立完整的橋接系統。
    否則返回 None。
    
    Returns:
        MemoryBridge 實例，如果記憶層不可用則返回 None
    """
    if not _MEMORY_AVAILABLE:
        print("[MemoryBridge] home_agent_memory not available")
        return None
    
    try:
        from home_agent_memory.config import memory_config
        from home_agent_memory.memory_layer import create_memory_system

        # 建立完整的記憶系統
        memory_layer, client, inference_queue = create_memory_system()
        
        # 建立橋接器，直接使用記憶層系統中的輸入隊列
        # 注意：client 內部已經持有正確的隊列，但 bridge 需要它來初始化
        bridge = MemoryBridge(memory_layer.input_queue)
        
        # 將記憶層和客戶端附加到橋接器
        bridge._memory_layer = memory_layer
        bridge._client = client
        bridge._inference_queue = inference_queue
        
        return bridge
        
    except Exception as e:
        print(f"[MemoryBridge] Failed to create memory system: {e}")
        import traceback
        traceback.print_exc()
        return None
