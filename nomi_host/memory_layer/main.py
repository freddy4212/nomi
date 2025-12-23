#!/usr/bin/env python3
"""
NOMI Memory Layer Layer - 主程式入口

這個模組負責：
- 管理記憶層生命週期
- 持久化儲存感知層資料
- 維護成員即時狀態
- 提供資料視覺化工具

使用方式：
    # GUI 模式（預設）
    python -m memory_layer.main
    python memory_layer/main.py
    
    # Headless 模式（無 GUI）
    python -m memory_layer.main --headless
    python memory_layer/main.py --headless
    
    # 作為模組導入
    from memory_layer.core import MemoryCore
    core = MemoryCore()
    core.start()
"""
import os
import sys

_base_dir = os.path.dirname(os.path.abspath(__file__))
_pycache_dir = os.path.join(_base_dir, '__pycache__')

os.makedirs(_pycache_dir, exist_ok=True)
sys.pycache_prefix = _pycache_dir

import argparse

# 確保可以導入當前目錄的模組
sys.path.append(_base_dir)


def run_gui():
    """以 GUI 模式運行記憶層視覺化工具"""
    try:
        from gui import main as gui_main
    except ImportError:
        try:
            from .gui import main as gui_main
        except ImportError:
            import gui
            gui_main = gui.main
    
    print("=" * 50)
    print("  NOMI Memory Layer Layer - Data Visualizer")
    print("=" * 50)
    print("正在啟動 GUI...")
    gui_main()


def run_headless():
    """以 Headless 模式運行記憶層服務"""
    try:
        from core import run_headless as core_headless
    except ImportError:
        try:
            from .core import run_headless as core_headless
        except ImportError:
            import core
            core_headless = core.run_headless
    
    core_headless()


def main():
    """程式入口"""
    parser = argparse.ArgumentParser(
        description="NOMI Memory Layer Layer - 記憶層服務",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  python main.py              # GUI 模式（預設，資料視覺化工具）
  python main.py --headless   # Headless 模式（無 GUI，純服務）
  python main.py --gui        # 明確指定 GUI 模式
        """
    )
    parser.add_argument(
        '--headless', 
        action='store_true',
        help='以 Headless 模式運行（無 GUI，純服務）'
    )
    parser.add_argument(
        '--gui', 
        action='store_true',
        help='以 GUI 模式運行（資料視覺化工具，預設）'
    )
    
    args = parser.parse_args()
    
    if args.headless:
        run_headless()
    else:
        run_gui()


if __name__ == "__main__":
    main()
