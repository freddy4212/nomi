"""
main.py - NOMI Observation Layer 主程式入口

這個模組負責：
- 整合所有子模組
- 管理程式生命週期
- 透過 localhost port 接收骨架資料
- 協調各模組之間的資料流

使用方式：
    # GUI 模式（預設）
    python -m observation_layer.main
    python observation_layer/main.py
    
    # Headless 模式（無 GUI）
    python -m observation_layer.main --headless
    python observation_layer/main.py --headless
    
    # 作為模組導入
    from observation_layer.core import ReceiverCore
    core = ReceiverCore()
    core.start()
"""

import argparse
import os
import sys

# 設定統一的 __pycache__ 路徑，避免散落在各個模組資料夾中
# 這需要在導入任何自定義模組之前設定
if __name__ == "__main__" or __package__ is None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pycache_dir = os.path.join(base_dir, ".pycache")
    if not os.path.exists(pycache_dir):
        os.makedirs(pycache_dir, exist_ok=True)
    sys.pycache_prefix = pycache_dir

import threading
import time
from typing import Optional

# 處理直接執行和作為模組執行的情況
if __name__ == "__main__" or __package__ is None:
    # 添加專案根目錄到 path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 添加 mmaction2 submodule 到 path
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mmaction2'))
    
    from observation_layer.config import config
    from observation_layer.core import (PersonActionInfo, ReceiverCore,
                                        ReceiverStatus)
else:
    # 添加 mmaction2 submodule 到 path (當作為模組導入時)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mmaction2'))

    from .config import config
    from .core import PersonActionInfo, ReceiverCore, ReceiverStatus




class NOMIObservationLayerApp:
    """
    NOMI Observation Layer GUI 應用程式類
    
    這是一個包裝層，將 ReceiverCore 與 Tkinter GUI 整合
    """
    
    def __init__(self):
        """初始化應用程式"""
        import tkinter as tk

        # 延遲導入 GUI 相關模組
        if __name__ == "__main__" or __package__ is None:
            from observation_layer.gui_interface import ReceiverGUIInterface
        else:
            from .gui_interface import ReceiverGUIInterface
        


        # 建立 Tkinter 根視窗
        self.root = tk.Tk()
        
        # 初始化 GUI
        self.gui = ReceiverGUIInterface(self.root)
        
        # 快取最新的動作識別結果
        self.latest_actions = []
        
        # 初始化核心（設定回調）
        self.core = ReceiverCore(
            on_frame_processed=self._on_frame_processed,
            on_action_recognized=self._on_action_recognized,
            on_status_changed=self._on_status_changed,
            on_connection_changed=self._on_connection_changed,
            enable_memory_bridge=True,
        )
        
        # 設定 GUI 回調
        self.gui.on_start = self._on_gui_start
        self.gui.on_stop = self._on_gui_stop
        
        # 將記憶層橋接器傳遞給 GUI
        if self.core.memory_bridge:
            self.gui.memory_bridge = self.core.memory_bridge
        
        # 更新 GUI 上的記憶層狀態
        self._update_memory_status()
        
        self.debug_log("Application initialized")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[NOMI Observation Layer][{time.time():.3f}] {msg}")
    
    def _update_memory_status(self):
        """更新記憶層狀態顯示"""
        if self.core.memory_bridge:
            bridge = self.core.memory_bridge
            is_db_connected = False
            db_error = None
            
            if hasattr(bridge, '_memory_layer') and bridge._memory_layer:
                is_db_connected = bridge._memory_layer.is_db_connected
                db_error = bridge._memory_layer.db_error
            
            is_running = (
                hasattr(bridge, '_memory_layer') and 
                bridge._memory_layer is not None and
                bridge._memory_layer.is_alive()
            )
            
            events_sent = bridge.events_sent
            
            self.gui.update_memory_status(
                enabled=True, 
                connected=is_db_connected and is_running, 
                events_sent=events_sent,
                db_type="PostgreSQL",
                error=db_error
            )
        else:
            self.gui.update_memory_status(enabled=False, connected=False)
    
    def _on_gui_start(self) -> bool:
        """GUI 開始按鈕回調"""
        success = self.core.start_receiving()
        if success:
            self._update_memory_status()
        return success
    
    def _on_gui_stop(self):
        """GUI 停止按鈕回調"""
        self.core.stop_receiving()
        self._update_memory_status()
    
    def _on_frame_processed(self, frame_data, skeleton_frame):
        """幀處理完成回調"""
        # 排程到主執行緒更新 GUI
        self.root.after(0, self._update_gui_frame, frame_data, skeleton_frame)
        

    
    def _on_action_recognized(self, actions):
        """動作識別結果回調"""
        self.latest_actions = actions
        self.root.after(0, self._update_gui_actions, actions)
    
    def _on_status_changed(self, status: ReceiverStatus):
        """狀態變化回調"""
        self.root.after(0, self._update_memory_status)
    
    def _on_connection_changed(self, connected: bool, status_info: dict):
        """連接狀態變更回調"""
        self.root.after(0, lambda: self.gui.update_connection_status(connected, status_info))
        
        if connected:
            self.root.after(0, self.gui.update_action_text, 
                          "已連接到發射端！\n正在接收骨架資料...")
            self.root.after(0, self.gui.clear_errors)
        else:
            reconnect_count = status_info.get("reconnect_count", 0)
            self.root.after(0, self.gui.update_action_text,
                          f"連接已斷開，正在嘗試重新連接... (第 {reconnect_count} 次)")
    
    def _update_gui_frame(self, frame_data, skeleton_frame):
        """更新 GUI 幀顯示"""
        try:
            self.gui.update_frame(frame_data, skeleton_frame)
            
            buffer_status = self.core.get_buffer_status()
            self.gui.update_interpolation_status(buffer_status)
            
            interp_frames = self.core.skeleton_processor.get_interpolated_frames()
            if interp_frames:
                self.gui.update_interpolated_frames(interp_frames)
            
            action_text = self.core.action_recognizer.get_formatted_description()
            self.gui.update_action_text(action_text)
            
        except Exception as e:
            self.debug_log(f"GUI update error: {e}")
    
    def _update_gui_actions(self, actions):
        """更新 GUI 動作顯示"""
        try:
            if not actions:
                self.gui.update_action_result(
                    action="等待偵測...",
                    confidence=0.0,
                    skeleton_status="無人偵測到"
                )
                return
            
            multi_person_info = []
            for action in actions:
                person_info = {
                    'id': action.person_id,
                    'action': action.action_label,
                    'confidence': action.confidence,
                    'top5': action.top_k_actions,
                    'skeleton_status': action.skeleton_status,
                    'motion_status': action.motion_status,
                    'reid_name': action.reid_name or '-',
                    'bbox': action.bbox
                }
                multi_person_info.append(person_info)
            
            first = actions[0]
            self.gui.update_action_result(
                action=first.action_label,
                confidence=first.confidence,
                top5=first.top_k_actions,
                skeleton_status=first.skeleton_status,
                motion_status=first.motion_status,
                multi_person_info=multi_person_info if len(multi_person_info) > 1 else None
            )
            
        except Exception as e:
            self.debug_log(f"Action display update error: {e}")
    
    def run(self):
        """啟動應用程式"""
        self.debug_log("Starting application...")
        
        # 嘗試載入 MMAction2 模型
        try:
            self.core.load_model()
        except Exception as e:
            self.debug_log(f"MMAction2 model not loaded (using fallback): {e}")
        
        # 啟動定期狀態更新
        self._schedule_status_check()
        
        # 啟動 GUI 主迴圈
        self.gui.run()
        
        # 清理
        self._cleanup()
    
    def _schedule_status_check(self):
        """定期檢查並更新狀態"""
        try:
            if self.core.network_receiver.check_connection_state():
                status_info = self.core.network_receiver.get_connection_status()
                self.gui.update_connection_status(
                    self.core.network_receiver.is_connected, 
                    status_info
                )
            
            self._update_memory_status()
            
        except Exception as e:
            pass
        
        self.root.after(500, self._schedule_status_check)
    
    def _cleanup(self):
        """清理資源"""
        self.debug_log("Cleaning up...")
        self.core.stop_receiving()


def run_headless():
    """
    以 Headless 模式運行 Receiver
    
    這是一個 CLI 入口點，適合在伺服器環境或自動化腳本中使用
    """
    print("=" * 50)
    print("  NOMI Observation Layer - Headless Mode")
    print("=" * 50)
    print()
    print(f"  監聽位址: {config.network.host}:{config.network.port}")
    print()
    
    def on_status_changed(status: ReceiverStatus):
        print(f"[Status] Running: {status.is_running}, Connected: {status.is_connected}, "
              f"Frames: {status.frame_count}, FPS: {status.fps:.1f}, Persons: {status.persons_detected}")
    
    def on_action_recognized(actions):
        if actions:
            for action in actions:
                print(f"[Action] Person {action.person_id}: {action.action_label} ({action.confidence:.1%})")
    
    core = ReceiverCore(
        on_status_changed=on_status_changed,
        on_action_recognized=on_action_recognized,
    )
    
    try:
        print("Loading model...")
        core.load_model()
        
        print("Starting receiver...")
        core.start()
        core.join()  # 等待執行緒結束
        
    except KeyboardInterrupt:
        print("\n[NOMI Observation Layer] 收到中斷信號，正在關閉...")
    finally:
        core.stop()
        print("Receiver stopped.")


def run_gui():
    """以 GUI 模式運行 Receiver"""
    print("=" * 50)
    print("  NOMI Observation Layer - 骨架資料網路接收端")
    print("=" * 50)
    print()
    print(f"  監聽位址: {config.network.host}:{config.network.port}")
    print()
    
    app = NOMIObservationLayerApp()
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[NOMI Observation Layer] 收到中斷信號，正在關閉...")
        app._cleanup()
        try:
            app.root.destroy()
        except:
            pass
        sys.exit(0)
    except Exception as e:
        print(f"\n[NOMI Observation Layer] 發生未預期的錯誤: {e}")
        app._cleanup()
        sys.exit(1)


def main():
    """程式入口"""
    parser = argparse.ArgumentParser(
        description="NOMI Observation Layer - 骨架資料網路接收端",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  python main.py              # GUI 模式（預設）
  python main.py --headless   # Headless 模式（無 GUI）
  python main.py --gui        # 明確指定 GUI 模式
        """
    )
    parser.add_argument(
        '--headless', 
        action='store_true',
        help='以 Headless 模式運行（無 GUI）'
    )
    parser.add_argument(
        '--gui', 
        action='store_true',
        help='以 GUI 模式運行（預設）'
    )
    
    args = parser.parse_args()
    
    if args.headless:
        run_headless()
    else:
        run_gui()


if __name__ == "__main__":
    main()
