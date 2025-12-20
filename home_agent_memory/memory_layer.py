"""
memory_layer.py - 記憶層核心模組

這是 Home Agent 框架的核心，負責：
- 從 MemoryQueue 接收感知層資料
- 持久化儲存至資料庫
- 維護成員即時狀態
- (未來) 偵測異常並觸發推論層
"""

import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from .config import memory_config
    from .data_models import BoundingBox, MemberState, PerceptionEvent
    from .database import DatabaseManager
except (ImportError, ValueError):
    from config import memory_config
    from data_models import BoundingBox, MemberState, PerceptionEvent
    from database import DatabaseManager


class MemoryLayer(threading.Thread):
    """
    記憶層主類別
    
    作為獨立執行緒運行，持續從 Queue 接收資料並處理。
    """
    
    def __init__(
        self,
        input_queue: Optional[queue.Queue] = None,
        inference_queue: Optional[queue.Queue] = None,
        on_state_change: Optional[Callable[[MemberState], None]] = None,
    ):
        """
        初始化記憶層
        
        Args:
            input_queue: 來自感知層的輸入隊列，若未提供則自動建立
            inference_queue: 傳送給推論層的輸出隊列，若未提供則自動建立
            on_state_change: 狀態變化時的回調函數 (可選)
        """
        super().__init__(daemon=True, name="MemoryLayer")
        
        # 隊列
        self.input_queue = input_queue or queue.Queue(
            maxsize=memory_config.queue.memory_queue_maxsize
        )
        self.inference_queue = inference_queue or queue.Queue(
            maxsize=memory_config.queue.inference_queue_maxsize
        )
        
        # 資料庫
        self.db = DatabaseManager()
        
        # 當前狀態追蹤
        self.active_states: Dict[int, MemberState] = {}
        self._state_lock = threading.Lock()
        
        # 批次寫入緩衝
        self._batch_buffer: List[PerceptionEvent] = []
        self._batch_lock = threading.RLock()  # 使用可重入鎖避免死鎖
        self._last_flush_time = time.time()
        
        # 回調
        self.on_state_change = on_state_change
        
        # 控制
        self._running = False
        self._stop_event = threading.Event()
        
        # 統計
        self._events_received = 0
        self._events_written = 0
        
        # 連線狀態
        self._db_connected = self.db.is_connected
        self._db_error = self.db.connection_error
        
        self.debug_log(f"MemoryLayer initialized (DB connected: {self._db_connected})")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if memory_config.debug:
            print(f"[MemoryLayer][{time.time():.3f}] {msg}")
    
    @property
    def is_db_connected(self) -> bool:
        """資料庫是否已連線"""
        return self._db_connected
    
    @property
    def db_error(self) -> Optional[str]:
        """資料庫連線錯誤訊息"""
        return self._db_error
    
    # ==================== 公開介面 ====================
    
    def submit(self, event: PerceptionEvent):
        """
        提交感知事件到記憶層
        
        這是感知層 (Receiver) 調用的主要介面。
        非阻塞操作，如果隊列滿了會丟棄最舊的資料。
        
        Args:
            event: 感知事件物件
        """
        try:
            if self.input_queue.full():
                # 丟棄最舊的資料以騰出空間
                try:
                    self.input_queue.get_nowait()
                except queue.Empty:
                    pass
            self.input_queue.put_nowait(event)
            self._events_received += 1
        except Exception as e:
            self.debug_log(f"Failed to submit event: {e}")
    
    def get_active_states(self) -> Dict[int, MemberState]:
        """
        取得所有活躍成員的當前狀態
        
        Returns:
            以 person_id 為鍵的狀態字典
        """
        with self._state_lock:
            return self.active_states.copy()
    
    def get_state(self, person_id: int) -> Optional[MemberState]:
        """
        取得特定成員的當前狀態
        
        Args:
            person_id: 人物 ID
            
        Returns:
            成員狀態，若不存在則返回 None
        """
        with self._state_lock:
            return self.active_states.get(person_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        取得記憶層運行統計
        
        Returns:
            統計資訊字典
        """
        db_stats = self.db.get_statistics()
        return {
            "events_received": self._events_received,
            "events_written": self._events_written,
            "queue_size": self.input_queue.qsize(),
            "batch_buffer_size": len(self._batch_buffer),
            "active_members": len(self.active_states),
            "is_running": self._running,
            **db_stats,
        }
    
    # ==================== 執行緒邏輯 ====================
    
    def run(self):
        """記憶層主迴圈"""
        self._running = True
        self.debug_log("MemoryLayer started")
        
        last_retry_time = 0
        retry_interval = 10  # 每 10 秒重試一次連線
        
        while not self._stop_event.is_set():
            # 如果尚未連線，嘗試重試
            if not self._db_connected:
                current_time = time.time()
                if current_time - last_retry_time > retry_interval:
                    self.debug_log("Database not connected, retrying...")
                    if self.db._try_connect():
                        self._db_connected = True
                        self._db_error = None
                        self.debug_log("Database reconnected successfully")
                    else:
                        self._db_error = self.db.connection_error
                    last_retry_time = current_time

            try:
                # 嘗試從隊列取得資料 (帶超時以便檢查停止信號)
                try:
                    event = self.input_queue.get(timeout=0.1)
                    self._events_received += 1
                    
                    # 每 10 筆輸出一次日誌
                    if self._events_received % 10 == 0:
                        self.debug_log(f"Events received: {self._events_received}, queue size: {self.input_queue.qsize()}")
                        
                except queue.Empty:
                    # 檢查是否需要強制刷新批次緩衝
                    self._check_batch_timeout()
                    continue
                
                # 處理事件
                self._process_event(event)
                
                # 定期清理不活躍成員 (每 100 個事件檢查一次，避免過於頻繁)
                if self._events_received % 100 == 0:
                    self._cleanup_inactive_members()
                
            except Exception as e:
                self.debug_log(f"Error in main loop: {e}")
        
        # 停止前刷新所有緩衝資料
        self._flush_batch()
        self.db.close()
        
        self._running = False
        self.debug_log("MemoryLayer stopped")
    
    def stop(self):
        """停止記憶層"""
        self.debug_log("Stopping MemoryLayer...")
        self._stop_event.set()
    
    # ==================== 內部邏輯 ====================
    
    def _process_event(self, event: PerceptionEvent):
        """
        處理單一感知事件
        
        Args:
            event: 感知事件
        """
        self.debug_log(f"Processing event: person_id={event.person_id}, frame={event.frame_no}")
        
        # 1. 更新成員狀態
        self._update_member_state(event)
        
        # 2. 加入批次緩衝
        with self._batch_lock:
            self._batch_buffer.append(event)
            self.debug_log(f"Batch buffer size: {len(self._batch_buffer)}, batch_size config: {memory_config.queue.batch_size}")
            
            # 檢查是否達到批次大小
            if len(self._batch_buffer) >= memory_config.queue.batch_size:
                self.debug_log("Batch size reached, flushing...")
                self._flush_batch()
    
    def _update_member_state(self, event: PerceptionEvent):
        """
        更新成員即時狀態
        
        Args:
            event: 感知事件
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
            
            # 如果動作改變，重設開始時間
            if event.action_label != old_action:
                state.last_action = event.action_label
                state.last_action_start = event.timestamp
                
                # 觸發狀態變化回調
                if self.on_state_change:
                    try:
                        self.on_state_change(state)
                    except Exception as e:
                        self.debug_log(f"State change callback error: {e}")
            
            # 同步更新到資料庫快照表
            self.db.update_member_state(state)
    
    def _check_batch_timeout(self):
        """檢查批次超時並強制刷新"""
        now = time.time()
        if now - self._last_flush_time >= memory_config.queue.batch_timeout_sec:
            with self._batch_lock:
                if self._batch_buffer:
                    self._flush_batch()
    
    def _flush_batch(self):
        """刷新批次緩衝到資料庫"""
        with self._batch_lock:
            if not self._batch_buffer:
                self.debug_log("Flush called but buffer is empty")
                return
            
            events_to_write = self._batch_buffer.copy()
            self._batch_buffer.clear()
            self._last_flush_time = time.time()
        
        self.debug_log(f"Flushing {len(events_to_write)} events to database...")
        
        # 批次寫入
        try:
            count = self.db.insert_perception_events_batch(events_to_write)
            self._events_written += count
            self.debug_log(f"Successfully flushed {count} events to database (total: {self._events_written})")
        except Exception as e:
            self.debug_log(f"Batch write failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _cleanup_inactive_members(self, timeout_sec: float = 30.0):
        """
        清理長時間未更新的成員狀態
        
        Args:
            timeout_sec: 超時秒數
        """
        now = time.time()
        with self._state_lock:
            inactive = [
                pid for pid, state in self.active_states.items()
                if now - state.last_seen_time > timeout_sec
            ]
            for pid in inactive:
                # 標記為不可見，但保留在追蹤中 (可能只是暫時離開鏡頭)
                state = self.active_states[pid]
                if state.is_visible: # 只在狀態改變時更新
                    state.is_visible = False
                    self.db.update_member_state(state)
                    self.debug_log(f"Person {pid} marked as invisible")


class MemoryLayerClient:
    """
    記憶層客戶端
    
    供感知層 (Receiver) 使用的輕量級介面，
    負責打包資料發送到 MemoryQueue，並提供同步查詢資料庫的能力。
    """
    
    def __init__(self, memory_queue: queue.Queue, db_manager: Optional[DatabaseManager] = None):
        """
        初始化客戶端
        
        Args:
            memory_queue: 記憶層的輸入隊列
            db_manager: 資料庫管理器 (可選)
        """
        self.memory_queue = memory_queue
        self._event_count = 0
        self.db = db_manager or DatabaseManager()
    
    def send(self, event: PerceptionEvent):
        """
        發送感知事件到記憶層
        
        Args:
            event: 感知事件
        """
        try:
            self.memory_queue.put_nowait(event)
            self._event_count += 1
        except queue.Full:
            # 隊列滿了，嘗試丟棄最舊的
            try:
                self.memory_queue.get_nowait()
                self.memory_queue.put_nowait(event)
            except:
                pass
    
    # ==================== 成員管理 (ReID) ====================
    
    def register_member(self, name: str, vector: List[float]) -> int:
        """註冊或更新成員向量"""
        return self.db.register_member(name, vector)

    def delete_member(self, name: str) -> bool:
        """刪除成員"""
        return self.db.delete_member(name)

    def delete_all_members(self) -> bool:
        """刪除所有成員"""
        return self.db.delete_all_members()

    def get_all_members(self) -> List[Dict[str, Any]]:
        """取得所有成員"""
        return self.db.get_all_members()

    def find_nearest_member(self, vector: List[float], threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        """尋找最接近的成員"""
        return self.db.find_nearest_member(vector, threshold)

    @property
    def events_sent(self) -> int:
        """已發送的事件數"""
        return self._event_count


def create_memory_system() -> tuple:
    """
    工廠函數：建立完整的記憶層系統
    
    Returns:
        (MemoryLayer, MemoryLayerClient, InferenceQueue) 三元組
    """
    # 建立隊列
    memory_queue = queue.Queue(maxsize=memory_config.queue.memory_queue_maxsize)
    inference_queue = queue.Queue(maxsize=memory_config.queue.inference_queue_maxsize)
    
    # 建立記憶層
    memory_layer = MemoryLayer(
        input_queue=memory_queue,
        inference_queue=inference_queue,
    )
    
    # 建立客戶端，共享資料庫管理器
    client = MemoryLayerClient(memory_queue, db_manager=memory_layer.db)
    
    return memory_layer, client, inference_queue
