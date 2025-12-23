"""
main.py - NOMI Device Simulator 主程式入口

這個模組負責：
- 整合所有子模組（WiFi、Serial、Webcam）
- 管理程式生命週期
- 透過 localhost port 發送資料到接收端
- 協調各模組之間的資料流

使用方式：
    python -m device_simulator.main
    或
    python device_simulator/main.py
"""

import base64
import json
import os
import queue
import socket
import sys
import threading
import time
import tkinter as tk
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

# 抑制 OpenCV 警告
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

# 處理直接執行和作為模組執行的情況
if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from device_simulator.config import config
    from device_simulator.gui_interface import SenderGUIInterface
    from device_simulator.sources.serial_source import FrameData, SerialSource
    from device_simulator.sources.video_source import VideoSource
    from device_simulator.sources.webcam_source import WebcamSource
    from device_simulator.sources.wifi_source import WiFiSource
else:
    from .config import config
    from .gui_interface import SenderGUIInterface
    from .sources.serial_source import FrameData, SerialSource
    from .sources.video_source import VideoSource
    from .sources.webcam_source import WebcamSource
    from .sources.wifi_source import WiFiSource


class NetworkSender:
    """網路資料發送器（TCP Client 模式，主動連接到 receiver）"""
    
    def __init__(self):
        self.socket: Optional[socket.socket] = None
        self.is_running: bool = False
        self.is_connected: bool = False
        self.stop_event = threading.Event()
        
        # 執行緒
        self.connect_thread: Optional[threading.Thread] = None
        
        # 回調
        self.on_connection_changed: Optional[callable] = None
        
        # 統計
        self.sent_count: int = 0
        
        # 連接參數
        self.receiver_host = config.network.receiver_host
        self.receiver_port = config.network.receiver_port
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[NetworkSender][{time.time():.3f}] {msg}")
    
    def start(self) -> bool:
        """啟動連接執行緒"""
        if self.is_running:
            return True
        
        self.is_running = True
        self.stop_event.clear()
        
        # 啟動連接執行緒
        self.connect_thread = threading.Thread(target=self._connect_loop, daemon=True)
        self.connect_thread.start()
        
        self.debug_log(f"NetworkSender started, will connect to {self.receiver_host}:{self.receiver_port}")
        return True
    
    def stop(self):
        """停止連接"""
        self.is_running = False
        self.stop_event.set()
        self._disconnect()
        self.debug_log("NetworkSender stopped")
    
    def _connect(self) -> bool:
        """嘗試連接到 receiver"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.receiver_host, self.receiver_port))
            
            # 設定 TCP_NODELAY 減少延遲
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            self.socket.settimeout(2.0)  # 發送超時縮短到 2 秒
            self.is_connected = True
            self.debug_log(f"Connected to receiver at {self.receiver_host}:{self.receiver_port}")
            
            if self.on_connection_changed:
                self.on_connection_changed(True)
            
            return True
        except Exception as e:
            self.debug_log(f"Connection to receiver failed: {e}")
            self._disconnect()
            return False
    
    def _disconnect(self):
        """斷開連接"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        was_connected = self.is_connected
        self.is_connected = False
        
        if was_connected and self.on_connection_changed:
            self.on_connection_changed(False)
    
    def _connect_loop(self):
        """持續嘗試連接的執行緒"""
        self.debug_log("Connect loop started")
        
        while not self.stop_event.is_set() and self.is_running:
            if not self.is_connected:
                if not self._connect():
                    # 等待後重試
                    time.sleep(config.network.reconnect_interval)
            else:
                # 已連接，等待一下再檢查
                time.sleep(0.5)
        
        self._disconnect()
        self.debug_log("Connect loop ended")
    
    def send(self, data: Dict[str, Any]) -> bool:
        """發送資料到 receiver"""
        if not self.is_connected or not self.socket:
            return False
        
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            message = (json_str + '\n').encode('utf-8')
            self.socket.sendall(message)
            self.sent_count += 1
            return True
            
        except Exception as e:
            self.debug_log(f"Send error: {e}")
            self._disconnect()
            return False
    
    def is_receiver_connected(self) -> bool:
        """檢查是否已連接到 receiver"""
        return self.is_connected
    
    def get_connection_info(self) -> str:
        """獲取連接資訊"""
        if self.is_connected:
            return f"→ {self.receiver_host}:{self.receiver_port}"
        return f"等待連接 {self.receiver_host}:{self.receiver_port}..."


class NOMIDeviceSimulatorApp:
    """
    NOMI Device Simulator 主應用程式類
    
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
        self.video_source: Optional[VideoSource] = None
        self.wifi_source: Optional[WiFiSource] = None
        
        # 當前來源
        self.current_source = "wifi"
        
        # 停止事件
        self.app_stop_event = threading.Event()
        
        # 模擬設定
        self.floating_fps_enabled = config.webcam.floating_fps
        self.random_blocking_enabled = config.webcam.random_blocking
        
        # 統計
        self.total_frames = 0
        self.fps_start_time = time.time()
        self.frame_count = 0
        self.current_fps = 0.0
        
        # 網路發送佇列與執行緒
        self.send_queue = queue.Queue(maxsize=30)
        self.network_thread = threading.Thread(target=self._network_sender_loop, daemon=True)
        self.network_thread.start()
        
        # 設定 GUI 回調
        self._setup_gui_callbacks()
        
        # 設定網路發送器回調
        self.network_sender.on_connection_changed = self._on_receiver_connection_changed
        
        # Webcam 預覽更新 ID
        self.webcam_preview_id = None
        
        self.debug_log("Application initialized")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[NOMI Device Simulator][{time.time():.3f}] {msg}")
    
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
        self.gui.on_webcam_floating_fps_toggle = self._on_webcam_floating_fps_toggle
        self.gui.on_webcam_random_blocking_toggle = self._on_webcam_random_blocking_toggle
        self.gui.on_webcam_yolo_change = self._on_webcam_yolo_change
        self.gui.get_camera_options = self._get_camera_options
        
        # Video
        self.gui.on_video_start = self._on_video_start
        self.gui.on_video_stop = self._on_video_stop
        self.gui.on_video_fps_change = self._on_video_fps_change
        self.gui.on_video_reid_toggle = self._on_video_reid_toggle
        self.gui.on_video_floating_fps_toggle = self._on_video_floating_fps_toggle
        self.gui.on_video_random_blocking_toggle = self._on_video_random_blocking_toggle
        self.gui.on_video_yolo_change = self._on_video_yolo_change
        self.gui._update_video_preview = self._update_video_preview
    
    def _on_receiver_connection_changed(self, connected: bool):
        """Receiver 連接狀態變更回調"""
        self.root.after(0, self.gui.update_client_status, connected)
        if connected:
            self.debug_log("Connected to receiver")
        else:
            self.debug_log("Disconnected from receiver")
    
    def _on_source_changed(self, source: str):
        """來源變更回調"""
        self.debug_log(f"Source changed to: {source}")
        
        # 停止當前來源
        self.gui.stop_current_source()
        
        self.current_source = source
    
    # ===== WiFi 來源 =====
    
    def _on_wifi_start(self) -> bool:
        """WiFi 開始監聽"""
        self.wifi_source = WiFiSource(on_frame_received=self._on_frame_received)
        self.wifi_source.on_connection_changed = self._on_wifi_connection_changed
        success = self.wifi_source.start()
        
        if success:
            self.debug_log(f"WiFi listening on {config.wifi.listen_host}:{config.wifi.listen_port}")
        
        return success
    
    def _on_wifi_stop(self):
        """WiFi 停止監聯"""
        if self.wifi_source:
            self.wifi_source.stop()
            self.wifi_source = None
        self.debug_log("WiFi source stopped")
    
    def _on_wifi_connection_changed(self, connected: bool):
        """WiFi 連接狀態變更回調"""
        self.root.after(0, self.gui.update_wifi_connection_status, connected)
    
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
        if not self.webcam_source:
            self.webcam_source = WebcamSource(on_frame_received=self._on_frame_received)
        
        # 偵測攝像頭並更新 GUI 選項
        options = self._get_camera_options()
        self.gui.set_camera_options(options)
        
        success = self.webcam_source.start(camera_id)
        
        if success:
            self.debug_log(f"Webcam started with camera {camera_id}")
            # 開始預覽更新
            self._start_webcam_preview()
        
        return success

    def _get_camera_options(self) -> List[str]:
        """獲取攝像頭選項列表"""
        if not self.webcam_source:
            self.webcam_source = WebcamSource(on_frame_received=self._on_frame_received)
        
        cameras = self.webcam_source.detect_cameras()
        return [f"{c['id']}: {c['resolution']} ({c.get('backend', 'Unknown')})" for c in cameras]
    
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
            
    def _on_webcam_floating_fps_toggle(self, enabled: bool):
        """Webcam 浮動採樣率開關變更"""
        self.floating_fps_enabled = enabled
        if self.webcam_source:
            self.webcam_source.set_floating_fps(enabled)
        self.debug_log(f"Floating FPS {'enabled' if enabled else 'disabled'} (Network level)")
            
    def _on_webcam_random_blocking_toggle(self, enabled: bool):
        """Webcam 隨機阻塞開關變更"""
        self.random_blocking_enabled = enabled
        if self.webcam_source:
            self.webcam_source.set_random_blocking(enabled)
        self.debug_log(f"Random blocking {'enabled' if enabled else 'disabled'} (Network level)")
    
    def _on_webcam_yolo_change(self, model_name: str) -> bool:
        """Webcam YOLO 模型切換"""
        from device_simulator.yolo import YOLOModel
        
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

    # ===== Video 來源 =====
    
    def _on_video_start(self, video_path: str) -> bool:
        """Video 開始"""
        if not self.video_source:
            self.video_source = VideoSource(on_frame_received=self._on_frame_received)
        
        success = self.video_source.start(video_path)
        
        if success:
            self.debug_log(f"Video started: {video_path}")
            self._start_video_preview()
        
        return success
    
    def _on_video_stop(self):
        """Video 停止"""
        self._stop_video_preview()
        if self.video_source:
            self.video_source.stop()
        self.debug_log("Video source stopped")
    
    def _on_video_fps_change(self, fps: float):
        """Video FPS 變更"""
        if self.video_source:
            self.video_source.set_fps(fps)
    
    def _on_video_reid_toggle(self, enabled: bool):
        """Video ReID 開關變更"""
        if self.video_source:
            self.video_source.set_reid_enabled(enabled)

    def _on_video_floating_fps_toggle(self, enabled: bool):
        """Video 浮動採樣率開關變更"""
        self.floating_fps_enabled = enabled
        if self.video_source:
            self.video_source.set_floating_fps(enabled)
        self.debug_log(f"Video Floating FPS {'enabled' if enabled else 'disabled'}")

    def _on_video_random_blocking_toggle(self, enabled: bool):
        """Video 隨機阻塞開關變更"""
        self.random_blocking_enabled = enabled
        if self.video_source:
            self.video_source.set_random_blocking(enabled)
        self.debug_log(f"Video Random blocking {'enabled' if enabled else 'disabled'}")
            
    def _on_video_yolo_change(self, model_name: str) -> bool:
        """Video YOLO 模型切換"""
        from device_simulator.yolo import YOLOModel
        model_map = {"yolov8n-pose": YOLOModel.YOLOV8N, "yolo11n-pose": YOLOModel.YOLO11N}
        model_type = model_map.get(model_name)
        if model_type and self.video_source:
            return self.video_source.switch_yolo_model(model_type)
        return True

    def _start_video_preview(self):
        """開始 Video 預覽更新"""
        self._update_video_preview()
    
    def _stop_video_preview(self):
        """停止 Video 預覽更新"""
        pass # 由 _update_video_preview 檢查狀態停止

    def _update_video_preview(self):
        """更新 Video 預覽"""
        if self.video_source and self.video_source.is_running:
            frame = self.video_source.get_preview_frame()
            keypoints = self.video_source.get_preview_keypoints()
            
            if frame is not None:
                self.gui.update_video_preview(frame, keypoints)
                
            # 更新統計
            self.gui.lbl_video_frames.config(text=f"處理幀數：{self.video_source.total_frame_count}")
            self.gui.lbl_video_fps.config(text=f"實際 FPS：{self.video_source.current_fps:.1f}")
            
            self.root.after(33, self._update_video_preview)
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
        
        # 放入發送佇列（如果佇列滿了就丟棄最舊的，確保即時性）
        try:
            if self.send_queue.full():
                self.send_queue.get_nowait()
            self.send_queue.put_nowait(frame_data)
        except queue.Full:
            pass
        
        # 更新統計 (只傳遞必要資訊，避免在主執行緒處理大物件)
        stats_info = {
            'basic_info': frame_data.basic_info
        }
        self.root.after(0, self._update_stats, stats_info)
    
    def _network_sender_loop(self):
        """網路發送執行緒主迴圈 - 負責模擬網路不穩與浮動幀率"""
        self.debug_log("Network sender loop started")
        
        jitter_factor = 1.0
        last_jitter_update = 0
        
        while not self.app_stop_event.is_set():
            try:
                # 從佇列獲取原始幀資料
                frame_data = self.send_queue.get(timeout=0.5)
                
                # 在此執行緒進行影像編碼，減輕採樣執行緒負擔並增加穩定性
                send_data = self._create_send_data(frame_data)
                
                current_time = time.time()
                
                # 1. 模擬隨機阻塞 (1% 機率發生 0.5~1.5 秒的停頓)
                if self.random_blocking_enabled and np.random.random() < 0.01:
                    block_duration = np.random.uniform(0.5, 1.5)
                    self.debug_log(f"⚠️ [Network] 模擬隨機阻塞 {block_duration:.2f} 秒...")
                    time.sleep(block_duration)
                
                # 2. 模擬浮動採樣率 (控制發送間隔)
                if self.floating_fps_enabled:
                    # 每秒更新一次隨機抖動因子 (0.85 ~ 2.25)
                    if current_time - last_jitter_update > 1.0:
                        jitter_factor = np.random.uniform(0.85, 2.25)
                        last_jitter_update = current_time
                    
                    # 根據目標 FPS 計算應有的間隔
                    target_fps = config.webcam.default_fps
                    if self.webcam_source:
                        target_fps = self.webcam_source.target_fps
                    
                    effective_fps = target_fps * jitter_factor
                    # 模擬發送延遲
                    time.sleep(1.0 / max(0.1, effective_fps))
                
                # 發送到接收端
                if self.network_sender.is_receiver_connected():
                    success = self.network_sender.send(send_data)
                    if success:
                        self.root.after(0, self.gui.update_send_status, 
                                      f"已發送 {self.network_sender.sent_count} 幀")
                
                self.send_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.debug_log(f"Network sender error: {e}")
                time.sleep(0.1)
        
        self.debug_log("Network sender loop ended")
    
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
    
    def _update_stats(self, stats_info: Dict):
        """更新統計（在主執行緒中調用）"""
        if self.current_source == "serial" and self.serial_source:
            self.gui.update_serial_stats(
                self.total_frames,
                self.serial_source.get_fps(),
                stats_info.get('basic_info')
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
        
        self.app_stop_event.set()
        self._stop_webcam_preview()
        
        if self.serial_source:
            self.serial_source.disconnect()
        
        if self.webcam_source:
            self.webcam_source.stop()
        
        self.network_sender.stop()


def main():
    """程式入口"""
    print("=" * 50)
    print("  NOMI Device Simulator - 骨架資料網路發射端")
    print("=" * 50)
    print()
    print(f"  Receiver 位址: {config.network.receiver_host}:{config.network.receiver_port}")
    print(f"  WiFi 監聽埠: {config.wifi.listen_port}")
    print()
    print("  支援的資料來源:")
    print("  - 📡 WiFi: 接收 ESP32/WiseEye2 的 WiFi 傳輸 (port {})".format(config.wifi.listen_port))
    print("  - 🔌 Serial: 接收 WiseEye2 的串口傳輸")
    print("  - 📷 Webcam: 使用電腦攝像頭模擬")
    print()
    
    app = NOMIDeviceSimulatorApp()
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[NOMI Device Simulator] 收到中斷信號，正在關閉...")
        app._cleanup()
        try:
            app.root.destroy()
        except:
            pass
        sys.exit(0)
    except Exception as e:
        print(f"\n[NOMI Device Simulator] 發生未預期的錯誤: {e}")
        app._cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()
