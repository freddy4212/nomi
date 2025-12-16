"""
main.py - WE_MMA_Sender 主程式入口

這個模組負責：
- 整合所有子模組（WiFi、Serial、Webcam）
- 管理程式生命週期
- 透過 localhost port 發送資料到接收端
- 協調各模組之間的資料流

使用方式：
    python -m we_mma_sender.main
    或
    python we_mma_sender/main.py
"""

import base64
import json
import os
import socket
import sys
import threading
import time
import tkinter as tk
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

# 處理直接執行和作為模組執行的情況
if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from we_mma_sender.config import config
    from we_mma_sender.gui_interface import SenderGUIInterface
    from we_mma_sender.sources.serial_source import FrameData, SerialSource
    from we_mma_sender.sources.webcam_source import WebcamSource
else:
    from .config import config
    from .gui_interface import SenderGUIInterface
    from .sources.serial_source import FrameData, SerialSource
    from .sources.webcam_source import WebcamSource


class NetworkSender:
    """網路資料發送器（TCP Server 模式）"""
    
    def __init__(self):
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.is_running: bool = False
        self.stop_event = threading.Event()
        
        # 執行緒
        self.accept_thread: Optional[threading.Thread] = None
        
        # 回調
        self.on_client_connected: Optional[callable] = None
        self.on_client_disconnected: Optional[callable] = None
        
        # 統計
        self.sent_count: int = 0
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[NetworkSender][{time.time():.3f}] {msg}")
    
    def start(self) -> bool:
        """啟動伺服器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((config.network.host, config.network.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            
            self.is_running = True
            self.stop_event.clear()
            
            # 啟動接受連接執行緒
            self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.accept_thread.start()
            
            self.debug_log(f"Server started on {config.network.host}:{config.network.port}")
            return True
            
        except Exception as e:
            self.debug_log(f"Server start failed: {e}")
            return False
    
    def stop(self):
        """停止伺服器"""
        self.is_running = False
        self.stop_event.set()
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        self.debug_log("Server stopped")
    
    def _accept_loop(self):
        """接受連接執行緒"""
        self.debug_log("Accept loop started")
        
        while not self.stop_event.is_set() and self.is_running:
            try:
                client, addr = self.server_socket.accept()
                self.debug_log(f"Client connected: {addr}")
                
                # 關閉舊連接
                if self.client_socket:
                    try:
                        self.client_socket.close()
                    except:
                        pass
                
                self.client_socket = client
                self.client_socket.settimeout(5.0)
                
                if self.on_client_connected:
                    self.on_client_connected()
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    self.debug_log(f"Accept error: {e}")
        
        self.debug_log("Accept loop ended")
    
    def send(self, data: Dict[str, Any]) -> bool:
        """發送資料"""
        if not self.client_socket:
            return False
        
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            message = (json_str + '\n').encode('utf-8')
            self.client_socket.sendall(message)
            self.sent_count += 1
            return True
            
        except Exception as e:
            self.debug_log(f"Send error: {e}")
            
            if self.on_client_disconnected:
                self.on_client_disconnected()
            
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
            
            return False
    
    def is_client_connected(self) -> bool:
        """檢查客戶端是否已連接"""
        return self.client_socket is not None


class WE_MMA_Sender_App:
    """
    WE_MMA_Sender 主應用程式類
    
    從多種來源接收資料並透過網路發送給接收端
    """
    
    def __init__(self):
        """初始化應用程式"""
        # 建立 Tkinter 根視窗
        self.root = tk.Tk()
        
        # 初始化各模組
        self.gui = SenderGUIInterface(self.root)
        self.network_sender = NetworkSender()
        
        # 資料來源
        self.serial_source: Optional[SerialSource] = None
        self.webcam_source: Optional[WebcamSource] = None
        
        # 當前來源
        self.current_source = "wifi"
        
        # 統計
        self.total_frames = 0
        self.fps_start_time = time.time()
        self.frame_count = 0
        self.current_fps = 0.0
        
        # 設定 GUI 回調
        self._setup_gui_callbacks()
        
        # 設定網路發送器回調
        self.network_sender.on_client_connected = self._on_client_connected
        self.network_sender.on_client_disconnected = self._on_client_disconnected
        
        # Webcam 預覽更新 ID
        self.webcam_preview_id = None
        
        self.debug_log("Application initialized")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[WE_MMA_Sender][{time.time():.3f}] {msg}")
    
    def _setup_gui_callbacks(self):
        """設定 GUI 回調"""
        self.gui.on_source_changed = self._on_source_changed
        
        # WiFi
        self.gui.on_wifi_start = self._on_wifi_start
        self.gui.on_wifi_stop = self._on_wifi_stop
        
        # Serial
        self.gui.on_serial_connect = self._on_serial_connect
        self.gui.on_serial_disconnect = self._on_serial_disconnect
        self.gui.get_serial_ports = SerialSource.list_ports
        
        # Webcam
        self.gui.on_webcam_start = self._on_webcam_start
        self.gui.on_webcam_stop = self._on_webcam_stop
        self.gui.on_webcam_fps_change = self._on_webcam_fps_change
        self.gui.on_webcam_camera_change = self._on_webcam_camera_change
        self.gui.on_webcam_reid_toggle = self._on_webcam_reid_toggle
        self.gui.on_webcam_yolo_change = self._on_webcam_yolo_change
    
    def _on_client_connected(self):
        """客戶端連接回調"""
        self.root.after(0, self.gui.update_client_status, True)
        self.debug_log("Client connected")
    
    def _on_client_disconnected(self):
        """客戶端斷開回調"""
        self.root.after(0, self.gui.update_client_status, False)
        self.debug_log("Client disconnected")
    
    def _on_source_changed(self, source: str):
        """來源變更回調"""
        self.debug_log(f"Source changed to: {source}")
        
        # 停止當前來源
        self.gui.stop_current_source()
        
        self.current_source = source
    
    # ===== WiFi 來源 =====
    
    def _on_wifi_start(self) -> bool:
        """WiFi 開始"""
        # WiFi 目前只是佔位符，實際功能待實作
        self.debug_log("WiFi source started (placeholder)")
        return True
    
    def _on_wifi_stop(self):
        """WiFi 停止"""
        self.debug_log("WiFi source stopped")
    
    # ===== Serial 來源 =====
    
    def _on_serial_connect(self, port: str) -> bool:
        """Serial 連接"""
        self.serial_source = SerialSource(on_frame_received=self._on_frame_received)
        success = self.serial_source.connect(port)
        
        if success:
            self.debug_log(f"Serial connected to {port}")
        
        return success
    
    def _on_serial_disconnect(self):
        """Serial 斷開"""
        if self.serial_source:
            self.serial_source.disconnect()
            self.serial_source = None
        self.debug_log("Serial disconnected")
    
    # ===== Webcam 來源 =====
    
    def _on_webcam_start(self, camera_id: int) -> bool:
        """Webcam 開始"""
        self.webcam_source = WebcamSource(on_frame_received=self._on_frame_received)
        
        # 偵測攝像頭
        cameras = self.webcam_source.detect_cameras()
        options = [f"{c['id']}: {c['resolution']}" for c in cameras]
        self.gui.set_camera_options(options)
        
        success = self.webcam_source.start(camera_id)
        
        if success:
            self.debug_log(f"Webcam started with camera {camera_id}")
            # 開始預覽更新
            self._start_webcam_preview()
        
        return success
    
    def _on_webcam_stop(self):
        """Webcam 停止"""
        # 先停止預覽更新
        self._stop_webcam_preview()
        
        # 再停止 webcam source
        if self.webcam_source:
            self.webcam_source.stop()
            # 等待一小段時間確保停止完成
            import time
            time.sleep(0.1)
            self.webcam_source = None
        
        self.debug_log("Webcam stopped")
    
    def _on_webcam_fps_change(self, fps: float):
        """Webcam FPS 變更"""
        if self.webcam_source:
            self.webcam_source.set_fps(fps)
    
    def _on_webcam_camera_change(self, camera_id: int) -> bool:
        """Webcam 攝像頭變更"""
        if self.webcam_source:
            return self.webcam_source.switch_camera(camera_id)
        return False
    
    def _on_webcam_reid_toggle(self, enabled: bool):
        """Webcam ReID 開關變更"""
        if self.webcam_source:
            self.webcam_source.set_reid_enabled(enabled)
        self.debug_log(f"ReID {'enabled' if enabled else 'disabled'}")
    
    def _on_webcam_yolo_change(self, model_name: str) -> bool:
        """Webcam YOLO 模型切換"""
        from we_mma_sender.yolo import YOLOModel
        
        model_map = {
            "yolov8n-pose": YOLOModel.YOLOV8N,
            "yolo11n-pose": YOLOModel.YOLO11N,
        }
        
        model_type = model_map.get(model_name)
        if model_type is None:
            self.debug_log(f"Unknown YOLO model: {model_name}")
            return False
        
        if self.webcam_source:
            success = self.webcam_source.switch_yolo_model(model_type)
            self.debug_log(f"YOLO model switch to {model_name}: {'success' if success else 'failed'}")
            return success
        
        return True
    
    def _start_webcam_preview(self):
        """開始 Webcam 預覽更新"""
        if self.webcam_preview_id is not None:
            return
        self._update_webcam_preview()
    
    def _stop_webcam_preview(self):
        """停止 Webcam 預覽更新"""
        if self.webcam_preview_id is not None:
            self.root.after_cancel(self.webcam_preview_id)
            self.webcam_preview_id = None
    
    def _update_webcam_preview(self):
        """更新 Webcam 預覽"""
        if self.webcam_source and self.webcam_source.is_running:
            # 固定使用採樣幀率預覽（一卡一卡的效果）
            # 但如果 preview_frame 還沒準備好，先用 latest_frame
            frame = self.webcam_source.get_preview_frame()
            keypoints = self.webcam_source.get_preview_keypoints()
            
            # 如果 preview_frame 還沒準備好，使用 latest_frame
            if frame is None:
                frame = self.webcam_source.get_latest_frame()
                keypoints = self.webcam_source.get_latest_keypoints()
            
            if frame is not None:
                self.gui.update_webcam_preview(frame, keypoints)
                self.gui.update_webcam_stats(
                    self.webcam_source.total_frame_count,
                    self.webcam_source.get_fps(),
                    len(keypoints) if keypoints else 0
                )
            
            # 繼續更新
            self.webcam_preview_id = self.root.after(33, self._update_webcam_preview)
        else:
            self.webcam_preview_id = None
    
    # ===== 資料處理 =====
    
    def _on_frame_received(self, frame_data: FrameData):
        """
        幀資料接收回調（在背景執行緒中調用）
        
        Args:
            frame_data: 接收到的幀資料
        """
        self.total_frames += 1
        self._update_fps()
        
        # 建立要發送的資料
        send_data = self._create_send_data(frame_data)
        
        # 發送到接收端
        if self.network_sender.is_client_connected():
            success = self.network_sender.send(send_data)
            if success:
                self.root.after(0, self.gui.update_send_status, 
                              f"已發送 {self.network_sender.sent_count} 幀")
        
        # 更新統計
        self.root.after(0, self._update_stats, frame_data)
    
    def _create_send_data(self, frame_data: FrameData) -> Dict[str, Any]:
        """
        建立發送資料（模擬 WiseEye2 輸出格式）
        
        Args:
            frame_data: 幀資料
            
        Returns:
            JSON 格式的資料字典
        """
        # 編碼影像
        image_b64 = ""
        if frame_data.image is not None:
            _, buffer = cv2.imencode('.jpg', frame_data.image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            image_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "type": 0,
            "name": "INVOKE",
            "code": 0,
            "data": {
                "image": image_b64,
                "keypoints": frame_data.keypoints,
                "reid_results": frame_data.reid_results,
                "basic_info": frame_data.basic_info,
                "frame_info": frame_data.frame_info
            }
        }
    
    def _update_fps(self):
        """更新 FPS 統計"""
        self.frame_count += 1
        elapsed = time.time() - self.fps_start_time
        
        if elapsed >= 1.0:
            self.current_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start_time = time.time()
    
    def _update_stats(self, frame_data: FrameData):
        """更新統計（在主執行緒中調用）"""
        if self.current_source == "serial" and self.serial_source:
            self.gui.update_serial_stats(
                self.total_frames,
                self.serial_source.get_fps(),
                frame_data.basic_info
            )
    
    def run(self):
        """啟動應用程式"""
        self.debug_log("Starting application...")
        
        # 啟動網路伺服器
        if not self.network_sender.start():
            print("⚠ 無法啟動網路伺服器")
        
        # 初始化串口列表
        ports = SerialSource.list_ports()
        self.gui.set_serial_ports(ports)
        
        # 啟動主迴圈
        self.gui.run()
        
        # 清理
        self._cleanup()
    
    def _cleanup(self):
        """清理資源"""
        self.debug_log("Cleaning up...")
        
        self._stop_webcam_preview()
        
        if self.serial_source:
            self.serial_source.disconnect()
        
        if self.webcam_source:
            self.webcam_source.stop()
        
        self.network_sender.stop()


def main():
    """程式入口"""
    print("=" * 50)
    print("  WE_MMA_Sender - 骨架資料網路發射端")
    print("=" * 50)
    print()
    print(f"  伺服器位址: {config.network.host}:{config.network.port}")
    print()
    print("  支援的資料來源:")
    print("  - 📡 WiFi: 接收 WiseEye2 的 WiFi 傳輸")
    print("  - 🔌 Serial: 接收 WiseEye2 的串口傳輸")
    print("  - 📷 Webcam: 使用電腦攝像頭模擬")
    print()
    
    app = WE_MMA_Sender_App()
    app.run()


if __name__ == "__main__":
    main()
