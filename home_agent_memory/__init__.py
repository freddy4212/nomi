"""
Home Agent Memory Layer - 家庭代理人記憶層

這個模組是 Home Agent 框架的核心記憶系統，負責：
- 接收來自感知層 (Receiver) 的結構化資料
- 將資料持久化儲存至 PostgreSQL (TimescaleDB)
- 維護成員狀態與歷史軌跡
- (未來) 偵測異常並觸發推論層

架構層級：
    感知層 (Receiver) -> [MemoryQueue] -> 記憶層 (MemoryLayer) -> PostgreSQL
                                              |
                                              v
                                    [InferenceQueue] -> 推論層 (LLM Agent)
"""

from .config import MemoryConfig
from .data_models import MemberState, PerceptionEvent
from .database import DatabaseManager
from .memory_layer import MemoryLayer

__version__ = "0.1.0"
__all__ = [
    "MemoryConfig",
    "PerceptionEvent", 
    "MemberState",
    "MemoryLayer",
    "DatabaseManager",
]
