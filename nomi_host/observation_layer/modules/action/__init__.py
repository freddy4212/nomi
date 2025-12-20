"""
action - 動作識別模組
"""

# 為了避免循環導入，這裡不直接導入 recognizer.py
# 請從 .recognizer 導入具體類別
from .config import (ActionRecognizerConfig, MotionConfig,
                     SimplifiedActionConfig)
