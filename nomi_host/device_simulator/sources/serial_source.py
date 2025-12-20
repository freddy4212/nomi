"""
serial_source.py - Serial 串口資料來源模組

這個模組負責：
- 連接 WiseEye2 裝置的串口
- 在背景執行緒中讀取串口資料
- 解析 JSON 格式的資料封包
- 透過回調函數將資料傳遞給主程式
"""

import base64
import json
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np
import serial
import serial.tools.list_ports

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from device_simulator.config import config


@dataclass
class FrameData:
    """單一幀的資料結構"""
    timestamp: float
    frame_no: int
    image: Optional[np.ndarray]
    keypoints: List[Any]
    reid_results: List[Any]
    basic_info: Dict[str, Any]
    frame_info: Dict[str, Any]
    raw_data: Dict[str, Any]


class SerialSource:
    """Serial 串口資料來源"""
    
    def __init__(self, on_frame_received: Optional[Callable[[FrameData], None]] = None):
        """
        初始化串口接收器
        
        Args:
            on_frame_received: 當接收到完整幀資料時的回調函數
        """
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected: bool = False
        self.is_running: bool = False
        self.stop_event = threading.Event()
        
        # 資料隊列
        self.data_queue: queue.Queue = queue.Queue()
        
        # 執行緒
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
            print(f"[SerialSource][{time.time():.3f}] {msg}")
    
    @staticmethod
    def list_ports() -> List[str]:
        """列出所有可用的串口"""
        return [port.device for port in serial.tools.list_ports.comports()]
    
    def connect(self, port: str) -> bool:
        """
        連接到指定串口
        
        Args:
            port: 串口名稱
            
        Returns:
            是否連接成功
        """
        try:
            self.serial_port = serial.Serial(
                port,
                config.serial.baudrate,
                timeout=config.serial.timeout
            )
            self.is_connected = True
            self.is_running = True
            self.stop_event.clear()
            
            # 清空隊列
            with self.data_queue.mutex:
                self.data_queue.queue.clear()
            
            # 啟動讀取執行緒
            self.read_thread = threading.Thread(target=self._read_serial_loop, daemon=True)
            self.read_thread.start()
            
            # 啟動處理執行緒
            self.process_thread = threading.Thread(target=self._process_data_loop, daemon=True)
            self.process_thread.start()
            
            self.debug_log(f"Connected to {port}")
            
            if self.on_connection_changed:
                self.on_connection_changed(True)
            
            return True
            
        except Exception as e:
            self.debug_log(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """斷開串口連接"""
        self.is_connected = False
        self.is_running = False
        self.stop_event.set()
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        
        if self.on_connection_changed:
            self.on_connection_changed(False)
            
        self.debug_log("Disconnected")
    
    def _read_serial_loop(self):
        """串口讀取執行緒"""
        self.debug_log("Read thread started")
        byte_buffer = b""
        
        while not self.stop_event.is_set() and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    chunk = self.serial_port.read(self.serial_port.in_waiting)
                    byte_buffer += chunk
                    
                    if b'\n' in byte_buffer:
                        lines = byte_buffer.split(b'\n')
                        byte_buffer = lines.pop()
                        
                        for line_bytes in lines:
                            if line_bytes:
                                self.data_queue.put(line_bytes)
                else:
                    time.sleep(0.001)
                    
            except Exception as e:
                self.debug_log(f"Read error: {e}")
                break
                
        self.debug_log("Read thread ended")
    
    def _process_data_loop(self):
        """資料處理執行緒"""
        self.debug_log("Process thread started")
        
        while not self.stop_event.is_set() and self.is_running:
            try:
                line_bytes = self.data_queue.get(timeout=0.1)
                
                try:
                    line = line_bytes.decode('utf-8').strip()
                    frame_data = self._parse_line(line)
                    
                    if frame_data and self.on_frame_received:
                        self._update_fps()
                        self.on_frame_received(frame_data)
                        
                except UnicodeDecodeError:
                    pass
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.debug_log(f"Process error: {e}")
                
        self.debug_log("Process thread ended")
    
    def _parse_line(self, line: str) -> Optional[FrameData]:
        """解析一行 JSON 資料"""
        if not line.startswith('{'):
            return None
            
        try:
            data = json.loads(line)
            
            inner_data = data
            if data.get("name") == "INVOKE" and "data" in data:
                inner_data = data["data"]
            
            # 解析影像
            image = None
            if "image" in inner_data:
                try:
                    img_b64 = inner_data["image"]
                    img_bytes = base64.b64decode(img_b64)
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                except Exception as e:
                    self.debug_log(f"Image decode error: {e}")
            
            frame_info = inner_data.get("frame_info", {})
            frame_info["source"] = "serial"
            
            frame_data = FrameData(
                timestamp=time.time(),
                frame_no=frame_info.get("frame_no", inner_data.get("frame_no", 0)),
                image=image,
                keypoints=inner_data.get("keypoints", []),
                reid_results=inner_data.get("reid_results", []),
                basic_info=inner_data.get("basic_info", {}),
                frame_info=frame_info,
                raw_data=inner_data
            )
            
            if frame_data.keypoints:
                self.debug_log(f"Frame {frame_data.frame_no}: {len(frame_data.keypoints)} people detected")
            
            return frame_data
            
        except json.JSONDecodeError as e:
            self.debug_log(f"JSON parse error: {e}")
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
            return f"已連接 (FPS: {self.current_fps:.1f})"
        return "未連接"
