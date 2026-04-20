"""
status_helpers.py - Memory Layer 狀態輔助函式
"""

from typing import Any, Callable

from .status_models import MemoryStatus


def build_status_snapshot(memory_layer: Any, status_obj: MemoryStatus, status_lock: Any) -> MemoryStatus:
    """從 MemoryLayer 讀取統計並產生狀態快照"""
    stats = memory_layer.get_statistics()

    with status_lock:
        status_obj.is_running = memory_layer.is_alive()
        status_obj.is_db_connected = memory_layer.is_db_connected
        status_obj.events_received = stats.get("events_received", 0)
        status_obj.events_written = stats.get("events_written", 0)
        status_obj.queue_size = stats.get("queue_size", 0)
        status_obj.active_members = stats.get("active_members", 0)
        status_obj.db_error = memory_layer.db_error

        return MemoryStatus(
            is_running=status_obj.is_running,
            is_db_connected=status_obj.is_db_connected,
            events_received=status_obj.events_received,
            events_written=status_obj.events_written,
            queue_size=status_obj.queue_size,
            active_members=status_obj.active_members,
            db_type=status_obj.db_type,
            db_error=status_obj.db_error,
        )


def run_monitor_loop(
    stop_event: Any,
    notify_status_change: Callable[[], None],
    debug_log: Callable[[str], None],
    interval_sec: float = 2.0,
):
    """狀態監控迴圈"""
    while not stop_event.is_set():
        try:
            notify_status_change()
        except Exception as e:
            debug_log(f"Monitor error: {e}")

        stop_event.wait(interval_sec)
