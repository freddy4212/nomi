"""
status_models.py - Memory Layer 狀態資料模型
"""

from dataclasses import dataclass
from typing import Optional


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
