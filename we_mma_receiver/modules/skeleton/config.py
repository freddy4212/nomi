"""
config.py - 骨架處理相關配置
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class FrameInterpolationConfig:
    """補幀配置"""
    target_fps: int = 15
    source_fps: float = 1.5
    interpolation_method: str = "linear"
    sequence_length: int = 48
    buffer_size: int = 10
    smoothing_alpha: float = 0.25
    max_velocity: float = 40.0
    velocity_confidence_threshold: float = 0.6

@dataclass
class SkeletonConfig:
    """骨架配置"""
    skeleton_connections: List[Tuple[int, int]] = field(default_factory=lambda: [
        (0, 1), (0, 2), (1, 3), (2, 4),
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12),
        (11, 13), (13, 15), (12, 14), (14, 16)
    ])
    num_keypoints: int = 17
    confidence_threshold: float = 0.5
