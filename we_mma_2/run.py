#!/usr/bin/env python3
"""
run.py - 便捷啟動腳本

直接執行此腳本即可啟動 WE_MMA_2 應用程式
"""

import os
import sys

# 將父目錄加入 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from we_mma_2.main import main

if __name__ == "__main__":
    main()
