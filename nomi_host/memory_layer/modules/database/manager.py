"""
manager.py - 資料庫管理器

這是對原有 database.py 的模組化封裝，
實際實作仍使用根目錄的 database.py。
"""

import os
# 重新導出原有的 DatabaseManager
import sys

# 確保可以導入根目錄的模組
_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _base_dir not in sys.path:
    sys.path.insert(0, _base_dir)

try:
    from memory_layer.database import DatabaseManager
except ImportError:
    # 相對導入 fallback
    from ...database import DatabaseManager

__all__ = ["DatabaseManager"]
