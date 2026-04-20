"""
models.py - 骨架處理資料模型
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class PersonSkeleton:
    """單一人物的骨架資料"""

    person_id: int  # 人物 ID（來自追蹤）
    box: Tuple[int, int, int, int]  # (x, y, w, h) 邊界框
    score: float  # 檢測信心度
    keypoints: np.ndarray  # shape: (17, 3) - (x, y, score) - 原始關鍵點
    timestamp: float  # 時間戳
    smoothed_keypoints: Optional[np.ndarray] = None  # 平滑後的關鍵點（用於補幀和動作識別）
    reid_vector: Optional[np.ndarray] = None  # ReID 特徵向量
    is_visible: bool = True  # 人物是否在畫面中
    last_seen_time: float = 0.0  # 最後一次被偵測到的時間戳
    disappear_direction: Optional[str] = None  # 消失方向 (left, right, top, bottom)
    _visibility_event_sent: bool = False  # 內部標記：是否已發送離開事件

    def get_keypoints(self, use_smoothed: bool = False) -> np.ndarray:
        """
        獲取關鍵點

        Args:
            use_smoothed: 是否使用平滑後的關鍵點

        Returns:
            關鍵點陣列
        """
        if use_smoothed and self.smoothed_keypoints is not None:
            return self.smoothed_keypoints
        return self.keypoints


@dataclass
class SkeletonFrame:
    """單一幀的所有人物骨架"""

    timestamp: float
    frame_no: int
    persons: List[PersonSkeleton]
    environment: Dict[str, Any] = field(default_factory=dict)
