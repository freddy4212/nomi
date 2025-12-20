"""
modules - NOMI Observation Layer 核心模組

這個套件包含從 we_mma_2 遷移過來的核心功能模組：

- action: 動作識別模組（MMAction2 整合）
- skeleton: 骨架處理與濾波模組
- network: 網路接收模組
- memory: 記憶層橋接模組

注意：config 已移至 observation_layer 根目錄

使用方式：
    from observation_layer.config import config
    from observation_layer.modules.action import ActionRecognizer, ActionRecognizerAsync
    from observation_layer.modules.skeleton import SkeletonProcessor, SkeletonFrame
    from observation_layer.modules.memory import MemoryBridge
"""

# 不再從這裡導出 config，config 已移至根目錄
__all__ = []
