"""
modules - WE_MMA_Receiver 核心模組

這個套件包含從 we_mma_2 遷移過來的核心功能模組：

- config: 集中管理所有配置參數
- action: 動作識別模組（MMAction2 整合）
- skeleton: 骨架處理與濾波模組
- visualization: 視覺化模組
- memory: 記憶層橋接模組

使用方式：
    from we_mma_receiver.modules import config
    from we_mma_receiver.modules.action import ActionRecognizer, ActionRecognizerAsync
    from we_mma_receiver.modules.skeleton import SkeletonProcessor, SkeletonFrame
    from we_mma_receiver.modules.visualization import Visualizer, SkeletonPlayer
    from we_mma_receiver.modules.memory import MemoryBridge
"""

from .config import config

__all__ = ['config']
