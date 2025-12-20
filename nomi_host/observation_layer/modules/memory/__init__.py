"""
memory - 記憶層橋接模組

提供與 NOMI Memory Layer Layer 的整合功能。
"""

from .bridge import MemoryBridge, create_memory_bridge_if_available

__all__ = [
    'MemoryBridge',
    'create_memory_bridge_if_available',
]
