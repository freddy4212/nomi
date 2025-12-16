"""
we_mma_receiver - WE_MMA_2 接收端程式

這個套件負責：
- 透過 localhost port 接收骨架資料
- 顯示即時辨識結果
- 動作識別分析

此程式為 we_mma_2 的網路版本，移除了 serial 功能，
改用 localhost socket 接收資料。
"""

from .main import WE_MMA_Receiver_App, main
from .network_receiver import NetworkReceiver

__all__ = ['main', 'WE_MMA_Receiver_App', 'NetworkReceiver']
