"""
config.py - 記憶層相關配置
"""

from dataclasses import dataclass


@dataclass
class MemoryConfig:
    """記憶層配置"""
    enabled: bool = True
    min_duration_threshold: float = 1.0
    action_delay: float = 1.0
    person_timeout: float = 2.0
