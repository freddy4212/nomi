#!/usr/bin/env python3
"""
Home Agent Memory Layer - 資料視覺化工具
"""
import os
import sys

# 確保可以導入當前目錄的模組
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from gui import main
except (ImportError, ValueError):
    try:
        from .gui import main
    except (ImportError, ValueError):
        # 最後的手段：直接導入
        import gui
        main = gui.main

if __name__ == "__main__":
    print("================================================")
    print("  Home Agent Memory Layer - Data Visualizer")
    print("================================================")
    print("正在啟動 GUI...")
    main()
