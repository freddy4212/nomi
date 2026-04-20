"""
NOMI Memory Layer Layer - 家庭代理人記憶層

這個模組是 Home Agent 框架的核心記憶系統，負責：
- 接收來自感知層 (Receiver) 的結構化資料
- 將資料持久化儲存至 PostgreSQL (TimescaleDB)
- 維護成員狀態與歷史軌跡
- (未來) 偵測異常並觸發推論層

核心架構：
    MemoryCore: 與 GUI 解耦的核心邏輯，可作為服務運行或被外部程式調用
    MemoryLayer: 底層執行緒，持續從 Queue 接收資料並處理
    MemoryVisualizer: GUI 視覺化工具（可選）

使用方式：
    # 作為獨立服務運行（無 GUI）
    from memory_layer import MemoryCore
    core = MemoryCore()
    core.start()
    
    # 或以 GUI 模式運行
    python -m memory_layer.main

架構層級：
    感知層 (Receiver) -> [MemoryQueue] -> 記憶層 (MemoryLayer) -> PostgreSQL
                                              |
                                              v
                                    [InferenceQueue] -> 推論層 (LLM Agent)
"""

from .config import MemoryConfig
from .core import MemoryCore
from .data_models import MemberState, PerceptionEvent
from .database import DatabaseManager
from .memory_layer import MemoryLayer
from .status_models import MemoryStatus

__version__ = "0.1.0"
__all__ = [
    "MemoryConfig",
    "MemoryCore",
    "MemoryStatus",
    "PerceptionEvent", 
    "MemberState",
    "MemoryLayer",
    "DatabaseManager",
]
