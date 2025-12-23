"""
manager.py - 成員狀態管理器

負責：
- 追蹤所有活躍成員的即時狀態
- 管理狀態的生命週期
- 提供狀態查詢介面
"""

import threading
import time
from typing import Callable, Dict, Optional

try:
    from ...config import memory_config
    from ...data_models import MemberState, PerceptionEvent
except (ImportError, ValueError):
    import os
    import sys
    _base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _base_dir not in sys.path:
        sys.path.insert(0, _base_dir)
    from memory_layer.config import memory_config
    from memory_layer.data_models import MemberState, PerceptionEvent


class MemberStateManager:
    """
    成員狀態管理器
    
    負責追蹤所有活躍成員的即時狀態，並在狀態變化時觸發回調。
    """
    
    def __init__(self, on_state_change: Optional[Callable[[MemberState], None]] = None):
        """
        初始化狀態管理器
        
        Args:
            on_state_change: 狀態變化時的回調函數
        """
        self.active_states: Dict[int, MemberState] = {}
        self._state_lock = threading.Lock()
        self._last_sync: Dict[int, float] = {}  # 用於節流 DB 更新
        self.on_state_change = on_state_change
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if memory_config.debug:
            print(f"[StateManager][{time.time():.3f}] {msg}")
    
    def update_from_event(self, event: PerceptionEvent) -> Optional[MemberState]:
        """
        從感知事件更新成員狀態
        
        Args:
            event: 感知事件
            
        Returns:
            更新後的狀態，若狀態無變化則返回 None
        """
        with self._state_lock:
            person_id = event.person_id
            
            # 取得或建立狀態
            if person_id not in self.active_states:
                self.active_states[person_id] = MemberState(
                    person_id=person_id,
                    member_id=event.matched_member_id,
                )
            
            state = self.active_states[person_id]
            old_action = state.last_action
            
            # 更新狀態
            state.last_seen_time = event.timestamp
            state.last_bbox = event.bbox
            state.is_visible = event.visibility
            state.last_action_duration = event.action_duration
            
            if event.environment and event.environment.room:
                state.last_location = event.environment.room
            
            # 檢查動作是否改變
            action_changed = event.action_label != old_action
            
            if action_changed:
                state.last_action = event.action_label
                state.last_action_start = event.timestamp
                
                # 觸發回調
                if self.on_state_change:
                    try:
                        self.on_state_change(state)
                    except Exception as e:
                        self.debug_log(f"State change callback error: {e}")
            
            return state if action_changed else None
    
    def get_state(self, person_id: int) -> Optional[MemberState]:
        """
        取得特定成員的狀態
        
        Args:
            person_id: 人物 ID
            
        Returns:
            成員狀態，若不存在則返回 None
        """
        with self._state_lock:
            return self.active_states.get(person_id)
    
    def get_all_states(self) -> Dict[int, MemberState]:
        """
        取得所有活躍成員的狀態
        
        Returns:
            以 person_id 為鍵的狀態字典
        """
        with self._state_lock:
            return self.active_states.copy()
    
    def should_sync_to_db(self, person_id: int, interval: float = 1.0) -> bool:
        """
        檢查是否應該同步到資料庫（節流用）
        
        Args:
            person_id: 人物 ID
            interval: 最小同步間隔（秒）
            
        Returns:
            是否應該同步
        """
        now = time.time()
        last_sync = self._last_sync.get(person_id, 0)
        
        if now - last_sync >= interval:
            self._last_sync[person_id] = now
            return True
        return False
    
    def cleanup_inactive(self, timeout_sec: float = 30.0) -> list:
        """
        清理長時間未更新的成員狀態
        
        Args:
            timeout_sec: 超時秒數
            
        Returns:
            被標記為不可見的 person_id 列表
        """
        now = time.time()
        marked = []
        
        with self._state_lock:
            for pid, state in self.active_states.items():
                if now - state.last_seen_time > timeout_sec:
                    if state.is_visible:
                        state.is_visible = False
                        marked.append(pid)
                        self.debug_log(f"Person {pid} marked as invisible")
        
        return marked
    
    def remove_state(self, person_id: int) -> bool:
        """
        移除成員狀態
        
        Args:
            person_id: 人物 ID
            
        Returns:
            是否成功移除
        """
        with self._state_lock:
            if person_id in self.active_states:
                del self.active_states[person_id]
                return True
            return False
    
    def clear_all(self):
        """清除所有狀態"""
        with self._state_lock:
            self.active_states.clear()
            self._last_sync.clear()
    
    @property
    def active_count(self) -> int:
        """活躍成員數量"""
        return len(self.active_states)
