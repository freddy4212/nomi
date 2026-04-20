"""
result.py - 動作識別結果資料結構
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class ActionResult:
    """動作識別結果"""
    person_id: int  # 人物 ID
    action_label: str  # 動作標籤
    action_description: str  # 動作描述
    confidence: float  # 信心度
    top_k_actions: List[Tuple[str, float]]  # Top-K
    simplified_label: str = ""  # 簡化標籤
    motion_status: str = ""     # 動作強度
    duration: float = 0.0       # 該動作持續時間（秒）
    is_stable: bool = False     # 動作是否已穩定
    raw_scores: Optional[np.ndarray] = None