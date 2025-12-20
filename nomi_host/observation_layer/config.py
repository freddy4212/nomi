"""
config.py - NOMI Observation Layer 集中配置管理

負責從各模組載入預設 YAML 設定，並允許透過根目錄的 config.yaml 進行覆蓋。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

# 導入各模組的配置類別
from .modules.action.config import (ActionRecognizerConfig, MotionConfig,
                                    SimplifiedActionConfig)
from .modules.memory.config import MemoryConfig
from .modules.network.config import NetworkConfig
from .modules.skeleton.config import FrameInterpolationConfig, SkeletonConfig

# YAML 支援
try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False
    print("[Config] Warning: PyYAML not installed, using default config")


def _get_config_path() -> Path:
    """取得主 config.yaml 的路徑"""
    env_path = os.environ.get("WE_MMA_RECEIVER_CONFIG")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    
    # 程式根目錄 (observation_layer/)
    base_dir = Path(__file__).parent
    config_path = base_dir / "config.yaml"
    return config_path


def _load_yaml_config(path: Path) -> Dict[str, Any]:
    """載入指定的 YAML 配置檔"""
    if not _YAML_AVAILABLE or not path.exists():
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        print(f"[Config] Loaded config from: {path}")
        return data
    except Exception as e:
        print(f"[Config] Error loading config {path}: {e}")
        return {}


@dataclass
class GUIConfig:
    """GUI 介面配置"""
    window_title: str = "WiseEye2 Visualizer + MMAction2"
    window_size: str = "1200x900"
    canvas_width: int = 640
    canvas_height: int = 480
    action_panel_height: int = 150


@dataclass
class AppConfig:
    """應用程式總配置"""
    network: NetworkConfig = field(default_factory=NetworkConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)
    action: ActionRecognizerConfig = field(default_factory=ActionRecognizerConfig)
    interpolation: FrameInterpolationConfig = field(default_factory=FrameInterpolationConfig)
    skeleton: SkeletonConfig = field(default_factory=SkeletonConfig)
    simplified: SimplifiedActionConfig = field(default_factory=SimplifiedActionConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    debug: bool = True
    room_name: str = "Living Room"
    
    @classmethod
    def from_yaml(cls, yaml_data: Dict[str, Any]) -> "AppConfig":
        """從合併後的 YAML 資料建立配置實例"""
        def _update_dataclass(dc_instance, data: Dict[str, Any]):
            if not data: return
            for key, value in data.items():
                if hasattr(dc_instance, key):
                    if key == "skeleton_connections" and isinstance(value, list):
                        value = [tuple(pair) for pair in value]
                    setattr(dc_instance, key, value)
        
        config = cls()
        _update_dataclass(config.network, yaml_data.get('network', {}))
        _update_dataclass(config.gui, yaml_data.get('gui', {}))
        _update_dataclass(config.action, yaml_data.get('action', {}))
        _update_dataclass(config.interpolation, yaml_data.get('interpolation', {}))
        _update_dataclass(config.skeleton, yaml_data.get('skeleton', {}))
        _update_dataclass(config.simplified, yaml_data.get('simplified', {}))
        _update_dataclass(config.motion, yaml_data.get('motion', {}))
        _update_dataclass(config.memory, yaml_data.get('memory', {}))
        
        if 'debug' in yaml_data: config.debug = yaml_data['debug']
        if 'room_name' in yaml_data: config.room_name = yaml_data['room_name']
        
        # 觸發模型路徑解析
        config.action.__post_init__()
        return config


def load_config() -> AppConfig:
    """載入並合併所有配置"""
    base_dir = Path(__file__).parent
    modules_dir = base_dir / "modules"
    
    # 1. 載入各模組預設 YAML
    combined_data = {}
    combined_data.update(_load_yaml_config(modules_dir / "action" / "action_config.yaml"))
    combined_data.update(_load_yaml_config(modules_dir / "skeleton" / "skeleton_config.yaml"))
    combined_data.update(_load_yaml_config(modules_dir / "network" / "network_config.yaml"))
    combined_data.update(_load_yaml_config(modules_dir / "memory" / "memory_config.yaml"))
    
    # 2. 載入主使用者 YAML (覆蓋預設值)
    combined_data.update(_load_yaml_config(_get_config_path()))
    
    return AppConfig.from_yaml(combined_data)


# 全局配置實例
config = load_config()
