"""
modules - WE_MMA_Receiver 核心模組

這個套件包含從 we_mma_2 遷移過來的核心功能模組：

- action: 動作識別模組（MMAction2 整合）
- skeleton: 骨架處理與濾波模組
- network: 網路接收模組
- memory: 記憶層橋接模組

注意：config 已移至 we_mma_receiver 根目錄

使用方式：
    from we_mma_receiver.config import config
    from we_mma_receiver.modules.action import ActionRecognizer, ActionRecognizerAsync
    from we_mma_receiver.modules.skeleton import SkeletonProcessor, SkeletonFrame
    from we_mma_receiver.modules.memory import MemoryBridge
"""

# 不再從這裡導出 config，config 已移至根目錄
__all__ = []
