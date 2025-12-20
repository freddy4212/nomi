"""
skeleton - 骨架處理與濾波模組
"""

# 為了避免循環導入，這裡不直接導入 processor.py
# 請從 .processor 導入具體類別
from .config import FrameInterpolationConfig, SkeletonConfig
