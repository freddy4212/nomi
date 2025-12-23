"""
layers.py - 核心層管理員

負責管理 Observation Layer 與 Memory Layer 的生命週期與橋接。
"""

from typing import Callable, Optional

from memory_layer.core import MemoryCore
from observation_layer.core import ReceiverCore


class LayerManager:
    def __init__(self, on_memory_event: Callable, on_frame_processed: Callable, on_action_recognized: Callable):
        self.observation_core: Optional[ReceiverCore] = None
        self.memory_core: Optional[MemoryCore] = None
        
        self._on_memory_event = on_memory_event
        self._on_frame_processed = on_frame_processed
        self._on_action_recognized = on_action_recognized

    def start_all(self):
        """啟動所有核心層"""
        # 1. Memory Layer
        if not self.memory_core:
            self.memory_core = MemoryCore(on_event_received=self._on_memory_event)
        if not self.memory_core.get_status().is_running:
            self.memory_core.start()

        # 2. Observation Layer
        if not self.observation_core or (not self.observation_core.is_alive() and self.observation_core.ident is not None):
            self.observation_core = ReceiverCore(
                on_frame_processed=self._on_frame_processed,
                on_action_recognized=self._on_action_recognized,
                enable_memory_bridge=True
            )
        
        if not self.observation_core.is_alive():
            self.observation_core.start()
        
        if not self.observation_core.get_status().is_running:
            self.observation_core.start_receiving()

        # 3. Bridge
        self._connect_bridge()

    def stop_all(self):
        """停止所有核心層"""
        if self.observation_core:
            self.observation_core.stop_receiving()

    def _connect_bridge(self):
        """連接感知層與記憶層"""
        if self.memory_core and self.observation_core and self.observation_core.memory_bridge:
            bridge = self.observation_core.memory_bridge
            memory_layer = self.memory_core._memory_layer
            bridge.memory_queue = memory_layer.input_queue
            bridge._enabled = True
            if hasattr(bridge, 'set_memory_layer'):
                bridge.set_memory_layer(memory_layer)
            else:
                bridge._memory_layer = memory_layer
