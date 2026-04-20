"""
core_models.py - Observation Core 共用資料模型
"""

from dataclasses import dataclass, field
from typing import List, Optional


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
    duration: float = 0.0
    top_k_actions: List[tuple] = field(default_factory=list)
    skeleton_status: str = "等待偵測..."
    motion_status: str = "-"
    bbox: Optional[tuple] = None
    reid_name: Optional[str] = None
    reid_confidence: float = 0.0
