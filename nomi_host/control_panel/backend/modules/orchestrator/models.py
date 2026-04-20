"""
models.py - Orchestrator 資料模型
"""

from dataclasses import dataclass


@dataclass
class DeviceInfo:
    id: str = "Unknown"
    name: str = "Unknown"
    version: str = "Unknown"
    model: str = "Unknown"
