from typing import Any, Dict, List, Optional

from memory_layer.database import DatabaseManager


class IoTManager:
    def __init__(self):
        self.db = DatabaseManager()

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """獲取所有 IoT 裝置列表"""
        return self.db.get_iot_devices()

    def add_device(self, name: str, type: str, location: str = "", description: str = "", icon: str = "Cpu") -> bool:
        """新增一個 IoT 裝置"""
        return self.db.add_iot_device(
            name=name,
            type=type,
            location=location,
            description=description,
            icon=icon
        )

# 全域實例
_iot_manager_instance = None

def get_iot_manager():
    global _iot_manager_instance
    if _iot_manager_instance is None:
        _iot_manager_instance = IoTManager()
    return _iot_manager_instance
