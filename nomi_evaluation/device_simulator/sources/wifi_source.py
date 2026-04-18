"""
wifi_source.py - WiFi TCP 資料來源模組

這個模組負責：
- 監聽 TCP 端口，接收 ESP32 轉發的資料
- 在背景執行緒中讀取網路資料
- 解析 JSON 格式的資料封包
- 透過回調函數將資料傳遞給主程式
"""

import base64
import json
import os
import queue
import socket
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from device_simulator.config import config
from device_simulator.sources.serial_source import FrameData


class WiFiSource:
    """WiFi TCP 資料來源（TCP Server 模式，接收 ESP32 的連接）"""
    
    def __init__(self, on_frame_received: Optional[Callable[[FrameData], None]] = None):
        """
        初始化 WiFi 接收器
        
        Args:
            on_frame_received: 當接收到完整幀資料時的回調函數
        """
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.client_addr: Optional[tuple] = None
        self.is_listening: bool = False
        self.is_connected: bool = False
        self.is_running: bool = False
        self.stop_event = threading.Event()
        
        # 資料隊列
        self.data_queue: queue.Queue = queue.Queue()
        
        # 執行緒
        self.accept_thread: Optional[threading.Thread] = None
        self.read_thread: Optional[threading.Thread] = None
        self.process_thread: Optional[threading.Thread] = None
        
        # 回調函數
        self.on_frame_received = on_frame_received
        self.on_connection_changed: Optional[Callable[[bool], None]] = None
        
        # 統計資訊
        self.frame_count: int = 0
        self.fps_start_time: float = time.time()
        self.current_fps: float = 0.0
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[WiFiSource][{time.time():.3f}] {msg}")
    
    def start(self) -> bool:
        """
        啟動 TCP 監聽
        
        Returns:
            是否啟動成功
        """
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((config.wifi.listen_host, config.wifi.listen_port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            
            self.is_listening = True
            self.is_running = True
            self.stop_event.clear()
            
            # 清空隊列
            with self.data_queue.mutex:
                self.data_queue.queue.clear()
            
            # 啟動接受連接執行緒
            self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.accept_thread.start()
            
            # 啟動處理執行緒
            self.process_thread = threading.Thread(target=self._process_data_loop, daemon=True)
            self.process_thread.start()
            
            self.debug_log(f"Listening on {config.wifi.listen_host}:{config.wifi.listen_port}")
            return True
            
        except Exception as e:
            self.debug_log(f"Start failed: {e}")
            return False
    
    def stop(self):
        """停止監聽"""
        self.is_running = False
        self.is_listening = False
        self.stop_event.set()
        
        # 關閉客戶端連接
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        # 關閉伺服器 socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        self.is_connected = False
        self.debug_log("Stopped")
    
    def _accept_loop(self):
        """接受連接執行緒"""
        self.debug_log("Accept loop started")
        
        while not self.stop_event.is_set() and self.is_running:
            try:
                client, addr = self.server_socket.accept()
                self.debug_log(f"ESP32 connected: {addr}")
                
                # 關閉舊連接
                if self.client_socket:
                    try:
                        self.client_socket.close()
                    except:
                        pass
                
                self.client_socket = client
                self.client_socket.settimeout(0.1)
                self.client_addr = addr
                self.is_connected = True
                
                if self.on_connection_changed:
                    self.on_connection_changed(True)
                
                # 啟動讀取執行緒
                if self.read_thread and self.read_thread.is_alive():
                    # 等待舊的讀取執行緒結束
                    pass
                
                self.read_thread = threading.Thread(target=self._read_socket_loop, daemon=True)
                self.read_thread.start()
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    self.debug_log(f"Accept error: {e}")
        
        self.debug_log("Accept loop ended")
    
    def _read_socket_loop(self):
        """讀取 socket 資料執行緒"""
        self.debug_log("Read thread started")
        byte_buffer = b""
        
        while not self.stop_event.is_set() and self.is_connected and self.client_socket:
            try:
                chunk = self.client_socket.recv(config.wifi.buffer_size)
                
                if not chunk:
                    # 連接關閉
                    self.debug_log("ESP32 disconnected")
                    break
                
                byte_buffer += chunk
                
                # 以換行符分割
                while b'\n' in byte_buffer:
                    line_bytes, byte_buffer = byte_buffer.split(b'\n', 1)
                    if line_bytes:
                        self.data_queue.put(line_bytes)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_connected:
                    self.debug_log(f"Read error: {e}")
                break
        
        # 連接結束處理
        self.is_connected = False
        if self.on_connection_changed:
            self.on_connection_changed(False)
        
        self.debug_log("Read thread ended")
    
    def _process_data_loop(self):
        """資料處理執行緒"""
        self.debug_log("Process thread started")
        
        while not self.stop_event.is_set() and self.is_running:
            try:
                line_bytes = self.data_queue.get(timeout=0.1)
                
                try:
                    line = line_bytes.decode('utf-8').strip()
                    
                    # 基本 JSON 完整性檢查
                    if not line.startswith('{') or not line.endswith('}'):
                        # 不完整的 JSON，跳過
                        if len(line) > 50:
                            print(f"[WiFi] Incomplete JSON (len={len(line)}): {line[:30]}...{line[-20:]}")
                        continue
                    
                    # 檢查大括號是否平衡
                    if line.count('{') != line.count('}'):
                        print(f"[WiFi] Unbalanced braces: {{ ={line.count('{')}, }} ={line.count('}')}")
                        continue
                    
                    frame_data = self._parse_line(line)
                    
                    if frame_data and self.on_frame_received:
                        self._update_fps()
                        self.on_frame_received(frame_data)
                        
                except UnicodeDecodeError as e:
                    print(f"[WiFi] Decode error: {e}")
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[WiFi] Error: {e}")
                
        self.debug_log("Process thread ended")
    
    def _parse_line(self, line: str) -> Optional[FrameData]:
        """解析一行 JSON 資料（來自 ESP32 轉發的 WE2 原始 JSON 資料）"""
        if not line.startswith('{'):
            return None
            
        try:
            data = json.loads(line)
            
            # ESP32 直接轉發 WE2 的原始 JSON 格式：
            # {"frame_info": {...}, "basic_info": {...}, "image": "...", "keypoints": [...], "reid_results": [...]}
            inner_data = data
            if data.get("name") == "INVOKE" and "data" in data:
                inner_data = data["data"]
            
            # 解析影像（如果有的話）
            image = None
            if "image" in inner_data:
                try:
                    img_b64 = inner_data["image"]
                    if img_b64:  # Check if empty
                        img_bytes = base64.b64decode(img_b64)
                        np_arr = np.frombuffer(img_bytes, np.uint8)
                        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                except Exception as e:
                    self.debug_log(f"Image decode error: {e}")
            
            # 取得 frame_info（與 serial_source 相同格式）
            frame_info = inner_data.get("frame_info", {})
            if isinstance(frame_info, dict):
                frame_info["source"] = "wifi"
            else:
                frame_info = {"source": "wifi"}
            
            # keypoints 直接使用 WE2 原始格式（list）
            keypoints = inner_data.get("keypoints", [])
            if not isinstance(keypoints, list):
                keypoints = []
            
            frame_data = FrameData(
                timestamp=time.time(),
                frame_no=frame_info.get("frame_no", inner_data.get("frame_no", self.frame_count)),
                image=image,
                keypoints=keypoints,
                reid_results=inner_data.get("reid_results", []),
                basic_info=inner_data.get("basic_info", {}),
                frame_info=frame_info,
                raw_data=inner_data
            )
            
            if keypoints:
                self.debug_log(f"Frame {frame_data.frame_no}: {len(keypoints)} people detected")
            
            return frame_data
            
        except json.JSONDecodeError as e:
            print(f"[WiFi] JSON error at {e.pos}: {e.msg}")
            return None
    
    def _update_fps(self):
        """更新 FPS 統計"""
        self.frame_count += 1
        elapsed = time.time() - self.fps_start_time
        
        if elapsed >= 1.0:
            self.current_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start_time = time.time()
    
    def get_fps(self) -> float:
        """獲取當前 FPS"""
        return self.current_fps
    
    def get_status(self) -> str:
        """獲取狀態資訊"""
        if self.is_connected:
            return f"已連接: {self.client_addr} (FPS: {self.current_fps:.1f})"
        elif self.is_listening:
            return f"監聽中: {config.wifi.listen_host}:{config.wifi.listen_port}"
        return "未啟動"
