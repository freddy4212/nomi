"""
core.py - NOMI Memory Layer Layer 核心模組

這個模組包含與 GUI 解耦的核心邏輯，可以：
- 作為獨立執行緒運行
- 被外部程式調用
- 支援 Headless（無 GUI）模式
- 未來整合到統一網頁介面

使用方式：
    # 作為執行緒運行
    core = MemoryCore()
    core.start()  # 啟動執行緒
    ...
    core.stop()   # 停止執行緒
    
    # 或直接使用 MemoryLayer (更底層的 API)
    from memory_layer import MemoryLayer
    layer = MemoryLayer()
    layer.start()
"""

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from .config import memory_config
    from .data_models import MemberState, PerceptionEvent
    from .database import DatabaseManager
    from .memory_layer import MemoryLayer
except (ImportError, ValueError):
    from config import memory_config
    from data_models import MemberState, PerceptionEvent
    from database import DatabaseManager
    from memory_layer import MemoryLayer


@dataclass
class MemoryStatus:
    """記憶層狀態資料"""
    is_running: bool = False
    is_db_connected: bool = False
    events_received: int = 0
    events_written: int = 0
    queue_size: int = 0
    active_members: int = 0
    db_type: str = "PostgreSQL"
    db_error: Optional[str] = None


class MemoryCore:
    """
    NOMI Memory Layer Layer 核心類別
    
    與 GUI 完全解耦的核心邏輯，可以：
    - 獨立運行記憶層服務
    - 被外部程式調用
    - 透過回調函式通知狀態變化
    """
    
    def __init__(
        self,
        on_status_changed: Optional[Callable[[MemoryStatus], None]] = None,
        on_state_changed: Optional[Callable[[MemberState], None]] = None,
        on_event_received: Optional[Callable[[PerceptionEvent], None]] = None,
    ):
        """
        初始化 Memory Core
        
        Args:
            on_status_changed: 狀態變化時的回調
            on_state_changed: 成員狀態變化時的回調
            on_event_received: 收到新事件時的回調
        """
        # 回調函式
        self.on_status_changed = on_status_changed
        self.on_state_changed = on_state_changed
        self.on_event_received = on_event_received
        
        # 建立記憶層實例
        self._memory_layer = MemoryLayer(
            on_state_change=self._on_member_state_changed
        )
        
        # 資料庫管理器（用於直接查詢）
        self._db = DatabaseManager()
        
        # 狀態追蹤
        self._status = MemoryStatus()
        self._status_lock = threading.Lock()
        
        # 監控執行緒
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        
        self.debug_log("MemoryCore initialized")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if memory_config.debug:
            print(f"[MemoryCore][{time.time():.3f}] {msg}")
    
    # ==================== 公開介面 ====================
    
    @property
    def input_queue(self) -> queue.Queue:
        """取得輸入隊列（供感知層提交事件）"""
        return self._memory_layer.input_queue
    
    @property
    def inference_queue(self) -> queue.Queue:
        """取得推論隊列（供推論層讀取）"""
        return self._memory_layer.inference_queue
    
    def get_status(self) -> MemoryStatus:
        """取得目前狀態"""
        stats = self._memory_layer.get_statistics()
        
        with self._status_lock:
            self._status.is_running = self._memory_layer.is_alive()
            self._status.is_db_connected = self._memory_layer.is_db_connected
            self._status.events_received = stats.get("events_received", 0)
            self._status.events_written = stats.get("events_written", 0)
            self._status.queue_size = stats.get("queue_size", 0)
            self._status.active_members = stats.get("active_members", 0)
            self._status.db_error = self._memory_layer.db_error
            
            return MemoryStatus(
                is_running=self._status.is_running,
                is_db_connected=self._status.is_db_connected,
                events_received=self._status.events_received,
                events_written=self._status.events_written,
                queue_size=self._status.queue_size,
                active_members=self._status.active_members,
                db_type=self._status.db_type,
                db_error=self._status.db_error,
            )
    
    def get_active_states(self) -> Dict[int, MemberState]:
        """取得所有活躍成員的當前狀態"""
        return self._memory_layer.get_active_states()
    
    def get_state(self, person_id: int) -> Optional[MemberState]:
        """取得特定成員的當前狀態"""
        return self._memory_layer.get_state(person_id)
    
    def submit_event(self, event: PerceptionEvent):
        """
        提交感知事件到記憶層
        
        Args:
            event: 感知事件物件
        """
        self._memory_layer.submit(event)
        
        if self.on_event_received:
            self.on_event_received(event)
    
    def get_recent_events(self, duration_sec: int = 3600, limit: int = 50) -> List[Dict]:
        """
        取得最近的事件
        
        Args:
            duration_sec: 時間範圍（秒）
            limit: 最大數量
            
        Returns:
            事件列表
        """
        return self._db.get_recent_events(duration_sec=duration_sec, limit=limit)
    
    def get_member_states(self) -> List[Dict]:
        """取得所有成員狀態（從資料庫）"""
        return self._db.get_member_states()
    
    def get_registered_members(self) -> List[Dict]:
        """取得所有已註冊成員"""
        return self._db.get_registered_members()
    
    # ==================== 生命週期管理 ====================
    
    def start(self):
        """啟動記憶層服務"""
        if self._memory_layer.is_alive():
            self.debug_log("MemoryLayer already running")
            return
        
        self.debug_log("Starting MemoryLayer...")
        self._memory_layer.start()
        
        # 啟動狀態監控執行緒
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="MemoryCore-Monitor"
        )
        self._monitor_thread.start()
        
        self._notify_status_change()
        self.debug_log("MemoryCore started")
    
    def stop(self):
        """停止記憶層服務"""
        self.debug_log("Stopping MemoryCore...")
        
        # 停止監控執行緒
        self._stop_monitor.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        
        # 停止記憶層
        self._memory_layer.stop()
        
        # 關閉資料庫
        self._db.close()
        
        self._notify_status_change()
        self.debug_log("MemoryCore stopped")
    
    def is_running(self) -> bool:
        """檢查是否正在運行"""
        return self._memory_layer.is_alive()
    
    # ==================== 內部邏輯 ====================
    
    def _on_member_state_changed(self, state: MemberState):
        """成員狀態變化回調"""
        if self.on_state_changed:
            self.on_state_changed(state)
    
    def _notify_status_change(self):
        """通知狀態變化"""
        if self.on_status_changed:
            self.on_status_changed(self.get_status())
    
    def _monitor_loop(self):
        """狀態監控迴圈"""
        while not self._stop_monitor.is_set():
            try:
                # 定期更新狀態
                self._notify_status_change()
                
            except Exception as e:
                self.debug_log(f"Monitor error: {e}")
            
            # 每 2 秒更新一次
            self._stop_monitor.wait(2.0)


def run_headless():
    """
    以 Headless 模式運行記憶層服務
    
    這是一個簡單的 CLI 入口點，適合在伺服器環境使用
    """
    print("=" * 50)
    print("  NOMI Memory Layer Layer - Headless Mode")
    print("=" * 50)
    
    def on_status_changed(status: MemoryStatus):
        print(f"[Status] Running: {status.is_running}, DB: {status.is_db_connected}, "
              f"Events: {status.events_received}/{status.events_written}")
    
    core = MemoryCore(on_status_changed=on_status_changed)
    
    try:
        core.start()
        print("Memory Layer is running. Press Ctrl+C to stop.")
        
        while core.is_running():
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        core.stop()
        print("Memory Layer stopped.")


if __name__ == "__main__":
    run_headless()
