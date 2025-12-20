"""
we_mma_receiver - WE_MMA_2 接收端程式

這個套件負責：
- 透過 localhost port 接收骨架資料
- 顯示即時辨識結果
- 動作識別分析

核心架構：
    ReceiverCore: 與 GUI 解耦的核心邏輯，可作為執行緒運行或被外部程式調用
    WE_MMA_Receiver_App: GUI 包裝層，將 ReceiverCore 與 Tkinter 整合

使用方式：
    # 作為獨立執行緒運行（無 GUI）
    from we_mma_receiver import ReceiverCore
    core = ReceiverCore()
    core.start()
    
    # 或以 GUI 模式運行
    python -m we_mma_receiver.main
"""

from .core import PersonActionInfo, ReceiverCore, ReceiverStatus
from .main import WE_MMA_Receiver_App
from .modules.network.receiver import NetworkReceiver

__all__ = [
    'ReceiverCore',
    'ReceiverStatus',
    'PersonActionInfo',
    'WE_MMA_Receiver_App', 
    'NetworkReceiver',
]
