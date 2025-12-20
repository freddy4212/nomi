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
import tkinter as tk
from typing import Optional

# 處理直接執行和作為模組執行的情況
if __name__ == "__main__" or __package__ is None:
    # 添加專案根目錄到 path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 添加 mmaction2 submodule 到 path
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mmaction2'))
    
    from we_mma_receiver.config import config
    from we_mma_receiver.gui_interface import ReceiverGUIInterface
    from we_mma_receiver.modules.action.recognizer import ActionRecognizerAsync
    from we_mma_receiver.modules.memory import (
        MemoryBridge, create_memory_bridge_if_available)
    from we_mma_receiver.modules.network.receiver import (FrameData,
                                                          NetworkReceiver)
    from we_mma_receiver.modules.skeleton.processor import (SkeletonFrame,
                                                            SkeletonProcessor)
else:
    # 添加 mmaction2 submodule 到 path (當作為模組導入時)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mmaction2'))

    from .config import config
    from .gui_interface import ReceiverGUIInterface
    from .modules.action.recognizer import ActionRecognizerAsync
    from .modules.memory import MemoryBridge, create_memory_bridge_if_available
    from .modules.network.receiver import FrameData, NetworkReceiver
    from .modules.skeleton.processor import SkeletonFrame, SkeletonProcessor


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
        
        # 初始化記憶層橋接（Home Agent Memory Layer）
        self.memory_bridge: Optional[MemoryBridge] = create_memory_bridge_if_available()
        if self.memory_bridge:
            self.debug_log("Memory Layer bridge initialized")
            # 將記憶層橋接器傳遞給 GUI
            self.gui.memory_bridge = self.memory_bridge
        else:
            self.debug_log("Memory Layer not available, running without persistence")
        
        # 幀編號計數器（用於記憶層）
        self.frame_counter: int = 0
        
        # 動作識別更新計時器
        self.last_action_update: float = 0.0
        self.action_update_interval: float = 0.5
        
        # 更新 GUI 上的記憶層狀態
        self._update_memory_status()
        
        self.debug_log("Application initialized")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[WE_MMA_Receiver][{time.time():.3f}] {msg}")
    
    def _update_memory_status(self):
        """更新記憶層狀態顯示"""
        if self.memory_bridge:
            # 檢查資料庫連線狀態
            is_db_connected = False
            db_error = None
            
            if hasattr(self.memory_bridge, '_memory_layer') and self.memory_bridge._memory_layer:
                is_db_connected = self.memory_bridge._memory_layer.is_db_connected
                db_error = self.memory_bridge._memory_layer.db_error
            
            # 檢查執行緒是否在運行
            is_running = (
                hasattr(self.memory_bridge, '_memory_layer') and 
                self.memory_bridge._memory_layer is not None and
                self.memory_bridge._memory_layer.is_alive()
            )
            
            events_sent = self.memory_bridge.events_sent
            
            self.gui.update_memory_status(
                enabled=True, 
                connected=is_db_connected and is_running, 
                events_sent=events_sent,
                db_type="PostgreSQL",
                error=db_error
            )
        else:
            self.gui.update_memory_status(enabled=False, connected=False)
    
    def _on_start(self) -> bool:
        """
        開始接收回調
        
        Returns:
            是否啟動成功
        """
        success = self.network_receiver.start()
        if success:
            self.skeleton_processor.clear()
            self.frame_counter = 0
            self.action_recognizer.start()
            # 啟動記憶層
            if self.memory_bridge:
                try:
                    self.memory_bridge.start()
                    self.debug_log("Memory Layer started")
                except Exception as e:
                    self.debug_log(f"Failed to start Memory Layer: {e}")
            # 更新記憶層狀態顯示
            self._update_memory_status()
            self.debug_log("Started receiving")
        return success
    
    def _on_stop(self):
        """停止接收回調"""
        self.network_receiver.stop()
        self.action_recognizer.stop()
        self.skeleton_processor.clear()
        # 停止記憶層
        if self.memory_bridge:
            self.memory_bridge.stop()
            self.debug_log("Memory Layer stopped")
        # 更新記憶層狀態顯示
        self._update_memory_status()
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
        # 增加幀計數器
        self.frame_counter += 1
        
        # 處理骨架資料
        skeleton_frame = self.skeleton_processor.process_frame(frame_data)
        
        # === 發送感知資料到記憶層 (每一幀) ===
        # 注意：這裡在背景執行緒執行，避免阻塞 GUI
        if self.memory_bridge:
            self._send_to_memory_layer()
            
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
    
    def _send_to_memory_layer(self):
        """發送感知資料到記憶層（每一幀呼叫）"""
        try:
            # 只處理當前幀偵測到的人（從最新的插值幀獲取）
            if not self.skeleton_processor.interpolated_buffer:
                return
            
            latest_frame = self.skeleton_processor.interpolated_buffer[-1]
            
            if not latest_frame.persons:
                # 本幀沒有偵測到任何人，不發送任何資料
                # 記憶層會根據「收不到某人的資料」來判斷該人不在場
                return
            
            # 除錯：輸出本幀偵測到的人數
            if self.frame_counter % 30 == 0:
                person_ids = [p.person_id for p in latest_frame.persons]
                self.debug_log(f"Frame {self.frame_counter}: {len(person_ids)} persons detected: {person_ids}")
            
            # 處理本幀偵測到的每個人
            for person in latest_frame.persons:
                person_id = person.person_id
                
                # 1. 獲取動作識別結果 (可能為 None)
                result = self.action_recognizer.get_current_result(person_id)
                
                # 2. 獲取運動強度
                motion = self.skeleton_processor.get_motion_magnitude(person_id)
                
                # 3. 邊界框與 ReID 向量（直接從 person 物件獲取）
                bbox = person.box  # 這是 (x, y, w, h) tuple
                reid_vector = person.reid_vector
                
                # 4. 匹配成員
                matched_member_id = None
                if reid_vector is not None and self.memory_bridge:
                    # 使用較嚴格的閾值 (0.3) 確保只有信心度夠高才匹配
                    match = self.memory_bridge.find_nearest_member(reid_vector, threshold=0.3)
                    if match:
                        matched_member_id = match['member_id']
                
                # 5. 準備動作標籤與置信度
                action_label = "偵測中"
                action_confidence = 0.0
                action_candidates = []
                action_duration = 0.0
                
                if result:
                    action_label = result.simplified_label or result.action_label
                    action_confidence = result.confidence
                    action_candidates = result.top_k_actions if result.top_k_actions else []
                    action_duration = result.duration
                
                # 6. 發送到記憶層
                self.memory_bridge.send_action_result(
                    person_id=person_id,
                    frame_no=self.frame_counter,
                    bbox=bbox,
                    action_label=action_label,
                    action_confidence=action_confidence,
                    action_candidates=action_candidates,
                    action_duration=action_duration,
                    motion_magnitude=motion,
                    reid_vector=reid_vector,
                    matched_member_id=matched_member_id,
                    environment={"room": config.room_name}
                )
                
        except Exception as e:
            self.debug_log(f"Memory bridge error: {e}")
    
    def _update_action_display(self):
        """更新動作識別結果顯示（直觀風格）"""
        try:
            # 只從最新的插值幀獲取當前偵測到的人
            if not self.skeleton_processor.interpolated_buffer:
                self.gui.update_action_result(
                    action="等待偵測...",
                    confidence=0.0,
                    skeleton_status="無人偵測到"
                )
                return
            
            latest_frame = self.skeleton_processor.interpolated_buffer[-1]
            
            if not latest_frame.persons:
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
            
            # 處理當前幀偵測到的人物
            for person in latest_frame.persons:
                person_id = person.person_id
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
                    'reid_name': '-',
                    'bbox': person.box  # 加入邊界框資訊
                }
                multi_person_info.append(person_info)
            
            # 使用第一個人的結果作為主顯示
            if multi_person_info:
                first_person = multi_person_info[0]
                main_action = first_person['action']
                main_confidence = first_person['confidence']
                main_top5 = first_person['top5']
                main_skeleton_status = first_person['skeleton_status']
                main_motion_status = first_person['motion_status']
            
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
                    
                    # 獲取最新的邊界框資訊（用於 aspect_ratio 計算）
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
            # 檢查網路連線狀態是否有變化
            if self.network_receiver.check_connection_state():
                status_info = self.network_receiver.get_connection_status()
                self.gui.update_connection_status(
                    self.network_receiver.is_connected, 
                    status_info
                )
            
            # 更新記憶層狀態（顯示已發送事件數）
            self._update_memory_status()
            
        except Exception as e:
            pass
        
        # 每 500ms 檢查一次
        self.root.after(500, self._schedule_connection_check)
    
    def _cleanup(self):
        """清理資源"""
        self.debug_log("Cleaning up...")
        self.network_receiver.stop()
        self.action_recognizer.stop()
        if self.memory_bridge:
            self.memory_bridge.stop()


def main():
    """程式入口"""
    print("=" * 50)
    print("  WE_MMA_Receiver - 骨架資料網路接收端")
    print("=" * 50)
    print()
    print(f"  監聽位址: {config.network.host}:{config.network.port}")
    print()
    
    app = WE_MMA_Receiver_App()
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[WE_MMA_Receiver] 收到中斷信號，正在關閉...")
        app._cleanup()
        try:
            app.root.destroy()
        except:
            pass
        sys.exit(0)
    except Exception as e:
        print(f"\n[WE_MMA_Receiver] 發生未預期的錯誤: {e}")
        app._cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()
