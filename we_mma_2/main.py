"""
main.py - WE_MMA_2 主程式入口

這個模組負責：
- 整合所有子模組
- 管理程式生命週期
- 協調各模組之間的資料流
- 連接記憶層系統（Home Agent Memory Layer）

使用方式：
    python -m we_mma_2.main
    或
    python we_mma_2/main.py
"""

import os
import sys
import threading
import time
import tkinter as tk
from typing import Optional

# 處理直接執行和作為模組執行的情況
if __name__ == "__main__" or __package__ is None:
    # 直接執行時，將父目錄加入 Python 路徑
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from we_mma_2.action_recognizer import (ActionRecognizer,
                                            ActionRecognizerAsync)
    from we_mma_2.config import config
    from we_mma_2.gui_interface import GUIInterface
    from we_mma_2.memory_bridge import (MemoryBridge,
                                        create_memory_bridge_if_available)
    from we_mma_2.serial_receiver import FrameData, SerialReceiver
    from we_mma_2.skeleton_processor import SkeletonFrame, SkeletonProcessor
else:
    # 作為模組執行時使用相對導入
    from .action_recognizer import ActionRecognizer, ActionRecognizerAsync
    from .config import config
    from .gui_interface import GUIInterface
    from .memory_bridge import MemoryBridge, create_memory_bridge_if_available
    from .serial_receiver import FrameData, SerialReceiver
    from .skeleton_processor import SkeletonFrame, SkeletonProcessor


class WE_MMA_2_App:
    """
    WE_MMA_2 主應用程式類
    
    整合串口接收、骨架處理、動作識別和 GUI 顯示
    """
    
    def __init__(self):
        """初始化應用程式"""
        # 建立 Tkinter 根視窗
        self.root = tk.Tk()
        
        # 初始化各模組
        self.gui = GUIInterface(self.root)
        self.serial_receiver = SerialReceiver(on_frame_received=self._on_frame_received)
        self.skeleton_processor = SkeletonProcessor()
        self.action_recognizer = ActionRecognizerAsync()
        
        # 初始化記憶層橋接（Home Agent Memory Layer）
        self.memory_bridge: Optional[MemoryBridge] = create_memory_bridge_if_available()
        if self.memory_bridge:
            self.debug_log("Memory Layer bridge initialized")
        else:
            self.debug_log("Memory Layer not available, running without persistence")
        
        # 幀編號計數器（用於記憶層）
        self.frame_counter: int = 0
        
        # 設定 GUI 回調
        self.gui.on_connect = self._on_connect
        self.gui.on_disconnect = self._on_disconnect
        
        # 動作識別更新計時器
        self.last_action_update: float = 0.0
        self.action_update_interval: float = 0.5  # 每 0.5 秒更新一次動作識別
        
        # 初始化串口列表
        self.gui.set_ports(SerialReceiver.list_ports())
        
        self.debug_log("Application initialized")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[WE_MMA_2][{time.time():.3f}] {msg}")
    
    def _on_connect(self, port: str) -> bool:
        """
        連接回調
        
        Args:
            port: 串口名稱
            
        Returns:
            是否連接成功
        """
        success = self.serial_receiver.connect(port)
        if success:
            # 清空緩衝區
            self.skeleton_processor.clear()
            # 重置幀計數器
            self.frame_counter = 0
            # 啟動異步動作識別
            self.action_recognizer.start()
            # 啟動記憶層
            if self.memory_bridge:
                self.memory_bridge.start()
                self.debug_log("Memory Layer started")
            self.debug_log(f"Connected to {port}")
        return success
    
    def _on_disconnect(self):
        """斷開連接回調"""
        self.serial_receiver.disconnect()
        self.action_recognizer.stop()
        self.skeleton_processor.clear()
        # 停止記憶層
        if self.memory_bridge:
            self.memory_bridge.stop()
            self.debug_log("Memory Layer stopped")
        self.debug_log("Disconnected")
    
    def _on_frame_received(self, frame_data: FrameData):
        """
        幀資料接收回調（在背景執行緒中調用）
        
        Args:
            frame_data: 接收到的幀資料
        """
        # 增加幀計數器
        self.frame_counter += 1
        
        # 處理骨架資料
        skeleton_frame = self.skeleton_processor.process_frame(frame_data)
        
        # 排程 GUI 更新（必須在主執行緒）
        self.root.after(0, self._update_gui, frame_data, skeleton_frame)
        
        # 嘗試進行動作識別
        if time.time() - self.last_action_update >= self.action_update_interval:
            self._try_action_recognition()
            self.last_action_update = time.time()
    
    def _update_gui(self, frame_data: FrameData, skeleton_frame: Optional[SkeletonFrame]):
        """
        更新 GUI（在主執行緒中調用）
        
        Args:
            frame_data: 幀資料
            skeleton_frame: 骨架幀資料
        """
        try:
            # 更新影像顯示
            self.gui.update_frame(frame_data, skeleton_frame)
            
            # 更新補幀狀態
            buffer_status = self.skeleton_processor.get_buffer_status()
            self.gui.update_interpolation_status(buffer_status)
            
            # 更新補幀骨架列表（用於 Interpolated 模式流暢播放）
            interp_frames = self.skeleton_processor.get_interpolated_frames()
            if interp_frames:
                self.gui.update_interpolated_frames(interp_frames)
            
            # 更新動作識別結果
            action_text = self.action_recognizer.get_formatted_description()
            self.gui.update_action_text(action_text)
            
            # === 發送動作識別結果到記憶層 ===
            if self.memory_bridge:
                self._send_to_memory_layer()
            
        except Exception as e:
            self.debug_log(f"GUI update error: {e}")
    
    def _send_to_memory_layer(self):
        """發送動作識別結果到記憶層"""
        try:
            # 獲取所有動作識別結果
            results = self.action_recognizer.get_results()
            
            for person_id, result in results.items():
                # 獲取額外的上下文資訊
                motion = self.skeleton_processor.get_motion_magnitude(person_id)
                
                # 獲取邊界框
                bbox = None
                if self.skeleton_processor.interpolated_buffer:
                    latest_frame = self.skeleton_processor.interpolated_buffer[-1]
                    for p in latest_frame.persons:
                        if p.person_id == person_id:
                            bbox = p.box
                            break
                
                # 構建候選動作列表 [(label, score), ...]
                action_candidates = result.top_k_actions if result.top_k_actions else []
                
                # 發送到記憶層
                self.memory_bridge.send_action_result(
                    person_id=person_id,
                    frame_no=self.frame_counter,
                    bbox=bbox,
                    action_label=result.simplified_label or result.action_label,
                    action_confidence=result.confidence,
                    action_candidates=action_candidates,
                    action_duration=result.duration,
                    motion_magnitude=motion,
                    reid_vector=None  # TODO: 未來加入 ReID 向量
                )
                
        except Exception as e:
            self.debug_log(f"Memory bridge error: {e}")
    
    def _try_action_recognition(self):
        """嘗試進行動作識別"""
        try:
            # 獲取所有人物的骨架序列
            sequences = self.skeleton_processor.get_all_skeleton_sequences()
            
            # 準備包含動作強度和可見性的資訊
            sequences_info = {}
            
            if sequences:
                for person_id, sequence in sequences.items():
                    motion = self.skeleton_processor.get_motion_magnitude(person_id)
                    visibility = self.skeleton_processor.analyze_visibility(person_id)
                    
                    # 獲取最新的邊界框資訊
                    bbox = None
                    if self.skeleton_processor.interpolated_buffer:
                        latest_frame = self.skeleton_processor.interpolated_buffer[-1]
                        for p in latest_frame.persons:
                            if p.person_id == person_id:
                                bbox = p.box
                                break
                    
                    sequences_info[person_id] = {
                        'sequence': sequence,
                        'motion': motion,
                        'visibility': visibility,
                        'bbox': bbox
                    }
                
                self.debug_log(f"Submitting {len(sequences)} sequence(s) for recognition")
            else:
                # 如果沒有序列，提交空字典以清理舊資料
                self.debug_log("No sequences available, clearing results")
                
            # 始終提交（即使是空字典），這樣識別器才能清理消失的人物
            self.action_recognizer.submit(sequences_info)
                
        except Exception as e:
            self.debug_log(f"Action recognition error: {e}")
    
    def run(self):
        """啟動應用程式"""
        self.debug_log("Starting application...")
        
        # 嘗試載入 MMAction2 模型（可選）
        try:
            self.action_recognizer.recognizer.load_model()
        except Exception as e:
            self.debug_log(f"MMAction2 model not loaded (using fallback): {e}")
        
        # 啟動主迴圈
        self.gui.run()
        
        # 清理
        self._cleanup()
    
    def _cleanup(self):
        """清理資源"""
        self.debug_log("Cleaning up...")
        self.serial_receiver.disconnect()
        self.action_recognizer.stop()
        # 停止記憶層
        if self.memory_bridge:
            self.memory_bridge.stop()
            self.debug_log("Memory Layer stopped during cleanup")


def main():
    """程式入口"""
    print("=" * 50)
    print("  WE_MMA_2 - WiseEye2 Visualizer + MMAction2")
    print("=" * 50)
    print()
    
    app = WE_MMA_2_App()
    app.run()


if __name__ == "__main__":
    main()
