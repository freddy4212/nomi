"""
main.py - WE_MMA_Receiver 主程式入口

這個模組負責：
- 整合所有子模組
- 管理程式生命週期
- 透過 localhost port 接收骨架資料
- 協調各模組之間的資料流

使用方式：
    python -m we_mma_receiver.main
    或
    python we_mma_receiver/main.py
"""

import os
import sys
import threading
import time
import tkinter as tk
from typing import Optional

# 處理直接執行和作為模組執行的情況
if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from we_mma_2.action_recognizer import ActionRecognizerAsync
    from we_mma_2.skeleton_processor import SkeletonFrame, SkeletonProcessor
    from we_mma_receiver.config import config
    from we_mma_receiver.gui_interface import ReceiverGUIInterface
    from we_mma_receiver.network_receiver import FrameData, NetworkReceiver
else:
    from we_mma_2.action_recognizer import ActionRecognizerAsync
    from we_mma_2.skeleton_processor import SkeletonFrame, SkeletonProcessor

    from .config import config
    from .gui_interface import ReceiverGUIInterface
    from .network_receiver import FrameData, NetworkReceiver


class WE_MMA_Receiver_App:
    """
    WE_MMA_Receiver 主應用程式類
    
    透過 localhost port 接收骨架資料，進行動作識別
    """
    
    def __init__(self):
        """初始化應用程式"""
        # 建立 Tkinter 根視窗
        self.root = tk.Tk()
        
        # 初始化各模組
        self.gui = ReceiverGUIInterface(self.root)
        self.network_receiver = NetworkReceiver(on_frame_received=self._on_frame_received)
        self.skeleton_processor = SkeletonProcessor()
        self.action_recognizer = ActionRecognizerAsync()
        
        # 設定 GUI 回調
        self.gui.on_start = self._on_start
        self.gui.on_stop = self._on_stop
        
        # 設定網路接收器回調
        self.network_receiver.on_connection_changed = self._on_connection_changed
        
        # 動作識別更新計時器
        self.last_action_update: float = 0.0
        self.action_update_interval: float = 0.5
        
        self.debug_log("Application initialized")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[WE_MMA_Receiver][{time.time():.3f}] {msg}")
    
    def _on_start(self) -> bool:
        """
        開始接收回調
        
        Returns:
            是否啟動成功
        """
        success = self.network_receiver.start()
        if success:
            self.skeleton_processor.clear()
            self.action_recognizer.start()
            self.debug_log("Started receiving")
        return success
    
    def _on_stop(self):
        """停止接收回調"""
        self.network_receiver.stop()
        self.action_recognizer.stop()
        self.skeleton_processor.clear()
        self.debug_log("Stopped receiving")
    
    def _on_connection_changed(self, connected: bool):
        """連接狀態變更回調（在背景執行緒中調用）"""
        status_info = self.network_receiver.get_connection_status()
        self.root.after(0, lambda: self.gui.update_connection_status(connected, status_info))
        
        if connected:
            self.root.after(0, self.gui.update_action_text, 
                          "已連接到發射端！\n正在接收骨架資料...")
            # 連接時清除之前的錯誤計數
            self.root.after(0, self.gui.clear_errors)
        else:
            reconnect_count = status_info.get("reconnect_count", 0)
            self.root.after(0, self.gui.update_action_text,
                          f"連接已斷開，正在嘗試重新連接... (第 {reconnect_count} 次)")
    
    def _on_error(self, error_msg: str):
        """錯誤回調（在背景執行緒中調用）"""
        # 排程到主執行緒更新 GUI
        self.root.after(0, self.gui.update_error, error_msg)
    
    def _on_frame_received(self, frame_data: FrameData):
        """
        幀資料接收回調（在背景執行緒中調用）
        
        Args:
            frame_data: 接收到的幀資料
        """
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
            
            # 更新補幀骨架列表
            interp_frames = self.skeleton_processor.get_interpolated_frames()
            if interp_frames:
                self.gui.update_interpolated_frames(interp_frames)
            
            # 更新動作識別結果（新版直觀風格）
            self._update_action_display()
            
            # 更新動作識別文字日誌（舊版文字）
            action_text = self.action_recognizer.get_formatted_description()
            self.gui.update_action_text(action_text)
            
        except Exception as e:
            self.debug_log(f"GUI update error: {e}")
    
    def _update_action_display(self):
        """更新動作識別結果顯示（直觀風格）"""
        try:
            # 獲取所有人的識別結果
            all_results = {}
            person_ids = list(self.skeleton_processor.person_tracker.keys())
            
            if not person_ids:
                self.gui.update_action_result(
                    action="等待偵測...",
                    confidence=0.0,
                    skeleton_status="無人偵測到"
                )
                return
            
            multi_person_info = []
            main_action = "等待識別..."
            main_confidence = 0.0
            main_top5 = []
            main_skeleton_status = "等待偵測..."
            main_motion_status = "-"
            
            for person_id in person_ids:
                result = self.action_recognizer.get_current_result(person_id)
                
                # 骨架可見性分析
                visibility = self.skeleton_processor.analyze_visibility(person_id)
                motion = self.skeleton_processor.get_motion_magnitude(person_id)
                
                if visibility['is_sitting_likely']:
                    skel_status = f"🪑 可能坐著 (上:{visibility['upper_visible']}/11 下:{visibility['lower_visible']}/6)"
                elif visibility['is_full_body']:
                    skel_status = f"🧍 全身可見 (上:{visibility['upper_visible']}/11 下:{visibility['lower_visible']}/6)"
                else:
                    skel_status = f"👤 部分可見 (上:{visibility['upper_visible']}/11 下:{visibility['lower_visible']}/6)"
                
                # 動作強度
                if motion < 5:
                    motion_text = f"{motion:.1f} (靜止)"
                elif motion > 20:
                    motion_text = f"{motion:.1f} (劇烈)"
                else:
                    motion_text = f"{motion:.1f} (移動)"
                
                person_info = {
                    'id': person_id,
                    'action': result.action_label if result else "等待識別",
                    'confidence': result.confidence if result else 0.0,
                    'top5': result.top_k_actions if result else [],
                    'skeleton_status': skel_status,
                    'motion_status': motion_text,
                    'reid_name': '-'  # 可以從 ReID 結果中獲取
                }
                multi_person_info.append(person_info)
                
                # 使用第一個人的結果作為主顯示
                if person_id == 0 or (person_id == min(person_ids)):
                    main_action = person_info['action']
                    main_confidence = person_info['confidence']
                    main_top5 = person_info['top5']
                    main_skeleton_status = skel_status
                    main_motion_status = motion_text
            
            # 更新 GUI
            self.gui.update_action_result(
                action=main_action,
                confidence=main_confidence,
                top5=main_top5,
                skeleton_status=main_skeleton_status,
                motion_status=main_motion_status,
                multi_person_info=multi_person_info if len(multi_person_info) > 1 else None
            )
            
        except Exception as e:
            self.debug_log(f"Action display update error: {e}")

    def _try_action_recognition(self):
        """嘗試進行動作識別"""
        try:
            sequences = self.skeleton_processor.get_all_skeleton_sequences()
            
            if sequences:
                sequences_info = {}
                for person_id, sequence in sequences.items():
                    motion = self.skeleton_processor.get_motion_magnitude(person_id)
                    visibility = self.skeleton_processor.analyze_visibility(person_id)
                    sequences_info[person_id] = {
                        'sequence': sequence,
                        'motion': motion,
                        'visibility': visibility
                    }
                
                self.debug_log(f"Submitting {len(sequences)} sequence(s) for recognition")
                self.action_recognizer.submit(sequences_info)
            else:
                buffer_status = self.skeleton_processor.get_buffer_status()
                self.debug_log(f"No sequences available. Buffer: {buffer_status}")
                
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
        
        # 啟動定期連線狀態更新
        self._schedule_connection_check()
        
        # 啟動主迴圈
        self.gui.run()
        
        # 清理
        self._cleanup()
    
    def _schedule_connection_check(self):
        """定期檢查並更新連線狀態"""
        try:
            # 檢查連線狀態是否有變化
            if self.network_receiver.check_connection_state():
                status_info = self.network_receiver.get_connection_status()
                self.gui.update_connection_status(
                    self.network_receiver.is_connected, 
                    status_info
                )
        except Exception as e:
            pass
        
        # 每 500ms 檢查一次
        self.root.after(500, self._schedule_connection_check)
    
    def _cleanup(self):
        """清理資源"""
        self.debug_log("Cleaning up...")
        self.network_receiver.stop()
        self.action_recognizer.stop()


def main():
    """程式入口"""
    print("=" * 50)
    print("  WE_MMA_Receiver - 骨架資料網路接收端")
    print("=" * 50)
    print()
    print(f"  監聽位址: {config.network.host}:{config.network.port}")
    print()
    
    app = WE_MMA_Receiver_App()
    app.run()


if __name__ == "__main__":
    main()
