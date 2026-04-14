"""
layer.py - 記憶層主類別 (模組化版本)

這是 memory_layer.py 的模組化重構版本，
使用 modules/ 下的子模組來實現功能。
"""

import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from .config import memory_config
    from .data_models import MemberState, PerceptionEvent
    from .database import DatabaseManager
    from .modules.rules import RuleEngine
    from .modules.state import MemberStateManager
except (ImportError, ValueError):
    from config import memory_config
    from data_models import MemberState, PerceptionEvent
    from database import DatabaseManager
    from modules.rules import RuleEngine
    from modules.state import MemberStateManager


class MemoryLayerV2(threading.Thread):
    """
    記憶層主類別 (V2 模組化版本)
    
    作為獨立執行緒運行，持續從 Queue 接收資料並處理。
    使用模組化的子組件來實現各項功能。
    """
    
    def __init__(
        self,
        input_queue: Optional[queue.Queue] = None,
        inference_queue: Optional[queue.Queue] = None,
        on_state_change: Optional[Callable[[MemberState], None]] = None,
        on_event_processed: Optional[Callable[[PerceptionEvent], None]] = None,
    ):
        """
        初始化記憶層
        
        Args:
            input_queue: 來自感知層的輸入隊列
            inference_queue: 傳送給推論層的輸出隊列
            on_state_change: 狀態變化時的回調函數
            on_event_processed: 事件處理完成時的回調函數
        """
        super().__init__(daemon=True, name="MemoryLayerV2")
        
        # 隊列
        self.input_queue = input_queue or queue.Queue(
            maxsize=memory_config.queue.memory_queue_maxsize
        )
        self.inference_queue = inference_queue or queue.Queue(
            maxsize=memory_config.queue.inference_queue_maxsize
        )
        
        # 子模組
        self.db = DatabaseManager()
        self.state_manager = MemberStateManager(on_state_change=on_state_change)
        # 傳入 db manager 給 RuleEngine
        self.rule_engine = RuleEngine(db_manager=self.db)
        
        # 回調
        self.on_event_processed = on_event_processed
        
        # 批次寫入緩衝
        self._batch_buffer: List[PerceptionEvent] = []
        self._batch_lock = threading.RLock()
        self._last_flush_time = time.time()
        
        # 控制
        self._running = False
        self._stop_event = threading.Event()
        
        # 統計
        self._events_received = 0
        self._events_written = 0
        
        self.debug_log(f"MemoryLayerV2 initialized (DB connected: {self.db.is_connected})")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if memory_config.debug:
            print(f"[MemoryLayerV2][{time.time():.3f}] {msg}")
    
    @property
    def is_db_connected(self) -> bool:
        """資料庫是否已連線"""
        return self.db.is_connected
    
    @property
    def db_error(self) -> Optional[str]:
        """資料庫連線錯誤訊息"""
        return self.db.connection_error
    
    # ==================== 公開介面 ====================
    
    def submit(self, event: PerceptionEvent):
        """
        提交感知事件到記憶層
        
        Args:
            event: 感知事件物件
        """
        try:
            if self.input_queue.full():
                try:
                    self.input_queue.get_nowait()
                except queue.Empty:
                    pass
            self.input_queue.put_nowait(event)
            self._events_received += 1
        except Exception as e:
            self.debug_log(f"Failed to submit event: {e}")
    
    def get_active_states(self) -> Dict[int, MemberState]:
        """取得所有活躍成員的當前狀態"""
        return self.state_manager.get_all_states()
    
    def get_state(self, person_id: int) -> Optional[MemberState]:
        """取得特定成員的當前狀態"""
        return self.state_manager.get_state(person_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """取得記憶層運行統計"""
        db_stats = self.db.get_statistics()
        return {
            "events_received": self._events_received,
            "events_written": self._events_written,
            "queue_size": self.input_queue.qsize(),
            "batch_buffer_size": len(self._batch_buffer),
            "active_members": self.state_manager.active_count,
            "is_running": self._running,
            **db_stats,
        }
    
    # ==================== 執行緒邏輯 ====================
    
    def run(self):
        """記憶層主迴圈"""
        self._running = True
        self.debug_log("MemoryLayerV2 started")
        
        last_retry_time = 0
        retry_interval = 10
        
        while not self._stop_event.is_set():
            # 連線重試
            if not self.is_db_connected:
                current_time = time.time()
                if current_time - last_retry_time > retry_interval:
                    self.debug_log("Database not connected, retrying...")
                    if self.db._try_connect():
                        self.debug_log("Database reconnected successfully")
                    last_retry_time = current_time

            try:
                try:
                    event = self.input_queue.get(timeout=0.1)
                    self._events_received += 1
                    
                    if self._events_received % 10 == 0:
                        self.debug_log(f"Events received: {self._events_received}")
                        
                except queue.Empty:
                    self._check_batch_timeout()
                    continue
                
                self._process_event(event)
                
                if self._events_received % 100 == 0:
                    self._cleanup_inactive()
                
            except Exception as e:
                self.debug_log(f"Error in main loop: {e}")
        
        self._flush_batch()
        self.db.close()
        
        self._running = False
        self.debug_log("MemoryLayerV2 stopped")
    
    def stop(self):
        """停止記憶層"""
        self.debug_log("Stopping MemoryLayerV2...")
        self._stop_event.set()
    
    # ==================== 內部邏輯 ====================
    
    def _process_event(self, event: PerceptionEvent):
        """處理單一感知事件"""
        self.debug_log(f"Processing event: person_id={event.person_id}")
        
        # 1. 優先觸發回調
        if self.on_event_processed:
            try:
                self.on_event_processed(event)
            except Exception as e:
                self.debug_log(f"Event callback error: {e}")

        # 2. 更新成員狀態
        state = self.state_manager.update_from_event(event)

        # 2.5 執行規則檢查
        if state:
            rule_results = self.rule_engine.process_event(event, state)
            for res in rule_results:
                self.debug_log(f"*** RULE TRIGGERED: {res.label} - {res.description} ***")
                # TODO: 可以將這些結果存入 DB (例如 Insight 資料表) 或發送到前端
        
        # 3. 同步到資料庫（節流）
        if state and self.state_manager.should_sync_to_db(event.person_id):
            try:
                self.db.update_member_state(state)
            except Exception as e:
                self.debug_log(f"Failed to update state in DB: {e}")
        
        # 4. 加入批次緩衝
        with self._batch_lock:
            self._batch_buffer.append(event)
            
            if len(self._batch_buffer) >= memory_config.queue.batch_size:
                self._flush_batch()
    
    def _check_batch_timeout(self):
        """檢查批次超時"""
        now = time.time()
        if now - self._last_flush_time >= memory_config.queue.batch_timeout_sec:
            with self._batch_lock:
                if self._batch_buffer:
                    self._flush_batch()
    
    def _flush_batch(self):
        """刷新批次緩衝到資料庫"""
        with self._batch_lock:
            if not self._batch_buffer:
                return
            
            events_to_write = self._batch_buffer.copy()
            self._batch_buffer.clear()
            self._last_flush_time = time.time()
        
        self.debug_log(f"Flushing {len(events_to_write)} events...")
        
        try:
            count = self.db.insert_perception_events_batch(events_to_write)
            self._events_written += count
            self.debug_log(f"Flushed {count} events (total: {self._events_written})")
        except Exception as e:
            self.debug_log(f"Batch write failed: {e}")
    
    def _cleanup_inactive(self, timeout_sec: float = 30.0):
        """清理不活躍成員"""
        marked = self.state_manager.cleanup_inactive(timeout_sec)
        for pid in marked:
            state = self.state_manager.get_state(pid)
            if state:
                try:
                    self.db.update_member_state(state)
                except Exception as e:
                    self.debug_log(f"Failed to update inactive state: {e}")
