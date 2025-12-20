"""
network_receiver.py - 網路資料接收模組

這個模組負責：
- 建立與發射端的 TCP 連接
- 在背景執行緒中讀取網路資料
- 解析 JSON 格式的資料封包
- 透過回調函數將資料傳遞給其他模組
"""

import base64
import json
import queue
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

try:
    from ...config import config
except ImportError:
    from observation_layer.config import config


@dataclass
class FrameData:
    """單一幀的資料結構（與 we_mma_2 相容）"""
    timestamp: float  # 接收時間戳
    frame_no: int     # 幀編號
    image: Optional[np.ndarray]  # 原始影像 (BGR)
    keypoints: List[Any]  # 骨架關鍵點資料
    reid_results: List[Any]  # ReID 結果
    basic_info: Dict[str, Any]  # 裝置基本資訊
    frame_info: Dict[str, Any]  # 幀資訊（algo_tick 等）
    raw_data: Dict[str, Any]  # 原始 JSON 資料


class NetworkReceiver:
    """網路資料接收器（支援 Server 和 Client 模式，含自動重連）"""
    
    def __init__(self, on_frame_received: Optional[Callable[[FrameData], None]] = None):
        """
        初始化網路接收器
        
        Args:
            on_frame_received: 當接收到完整幀資料時的回調函數
        """
        self.socket: Optional[socket.socket] = None
        self.server_socket: Optional[socket.socket] = None  # Server 模式用
        self.client_socket: Optional[socket.socket] = None  # 當前連接的客戶端
        self.is_connected: bool = False
        self.is_running: bool = False
        self.stop_event = threading.Event()
        
        # 資料隊列（用於解耦讀取和處理）
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
        
        # 連接參數
        self.mode = config.network.mode  # "server" 或 "client"
        self.host = config.network.host
        self.port = config.network.port
        
        # 客戶端資訊（Server 模式）
        self.client_addr: Optional[tuple] = None
        
        # 重連控制
        self.reconnect_count: int = 0
        self.last_connection_time: float = 0
        self.last_data_time: float = 0
        
        # 連線狀態變更時間（用於即時更新 GUI）
        self._connection_state_changed: bool = False
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[NetworkReceiver][{time.time():.3f}] {msg}")
    
    def start(self) -> bool:
        """
        啟動網路接收器
        
        Returns:
            是否啟動成功
        """
        if self.is_running:
            return True
        
        self.is_running = True
        self.stop_event.clear()
        
        # 根據模式啟動不同的連接執行緒
        if self.mode == "server":
            self.read_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.debug_log(f"Starting in SERVER mode on {self.host}:{self.port}")
        else:
            self.read_thread = threading.Thread(target=self._connection_loop, daemon=True)
            self.debug_log(f"Starting in CLIENT mode, connecting to {self.host}:{self.port}")
        
        self.read_thread.start()
        
        # 啟動處理執行緒
        self.process_thread = threading.Thread(target=self._process_data_loop, daemon=True)
        self.process_thread.start()
        
        self.debug_log("Network receiver started")
        return True
    
    def stop(self):
        """停止網路接收器"""
        self.is_running = False
        self.stop_event.set()
        self._disconnect()
        
        # 關閉 Server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        self.debug_log("Network receiver stopped")
    
    def _connect(self) -> bool:
        """嘗試連接到發射端"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(0.1)  # 設定非阻塞式讀取超時
            self.is_connected = True
            self.debug_log(f"Connected to {self.host}:{self.port}")
            
            if self.on_connection_changed:
                self.on_connection_changed(True)
            
            return True
        except Exception as e:
            self.debug_log(f"Connection failed: {e}")
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
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        was_connected = self.is_connected
        self.is_connected = False
        self.client_addr = None
        
        if was_connected:
            self.reconnect_count += 1
            self._connection_state_changed = True
            self.debug_log(f"Disconnected. Reconnect attempt #{self.reconnect_count}")
            if self.on_connection_changed:
                try:
                    self.on_connection_changed(False)
                except:
                    pass
    
    def check_connection_state(self) -> bool:
        """
        檢查連線狀態是否有變化（供 GUI 輪詢使用）
        
        Returns:
            如果狀態有變化返回 True
        """
        changed = self._connection_state_changed
        self._connection_state_changed = False
        return changed
    
    def get_connection_status(self) -> dict:
        """
        獲取詳細的連線狀態（供 GUI 顯示）
        
        Returns:
            狀態字典
        """
        now = time.time()
        data_age = now - self.last_data_time if self.last_data_time > 0 else -1
        
        return {
            "connected": self.is_connected,
            "mode": self.mode,
            "host": self.host,
            "port": self.port,
            "client_addr": self.client_addr,
            "reconnect_count": self.reconnect_count,
            "data_age": data_age,  # 距離上次收到資料的秒數
            "fps": self.current_fps
        }
    
    def _server_loop(self):
        """Server 模式：監聽並接受連接（含自動重連處理）"""
        self.debug_log("Server loop started")
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            self.debug_log(f"Server listening on {self.host}:{self.port}")
        except Exception as e:
            self.debug_log(f"Server bind failed: {e}")
            return
        
        byte_buffer = b""
        
        while not self.stop_event.is_set() and self.is_running:
            # 如果沒有連接，等待新連接
            if not self.is_connected:
                try:
                    client_sock, addr = self.server_socket.accept()
                    client_sock.settimeout(0.1)
                    # 設定 TCP_NODELAY 減少延遲
                    client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    self.client_socket = client_sock
                    self.client_addr = addr
                    self.is_connected = True
                    self._connection_state_changed = True
                    self.last_connection_time = time.time()
                    byte_buffer = b""
                    self.debug_log(f"Client connected from {addr}")
                    
                    if self.on_connection_changed:
                        try:
                            self.on_connection_changed(True)
                        except:
                            pass
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    self.debug_log(f"Accept error: {e}")
                    time.sleep(0.5)
                    continue
            
            # 讀取已連接客戶端的資料
            try:
                chunk = self.client_socket.recv(config.network.buffer_size)
                if not chunk:
                    self.debug_log(f"Client {self.client_addr} disconnected")
                    self._disconnect()
                    continue
                
                byte_buffer += chunk
                
                while b'\n' in byte_buffer:
                    line, byte_buffer = byte_buffer.split(b'\n', 1)
                    if line:
                        self.data_queue.put(line)
                        
            except socket.timeout:
                continue
            except Exception as e:
                self.debug_log(f"Read error from client: {e}")
                self._disconnect()
        
        self.debug_log("Server loop ended")
    
    def _connection_loop(self):
        """連接管理執行緒（包含讀取功能）"""
        self.debug_log("Connection loop started")
        byte_buffer = b""
        
        while not self.stop_event.is_set() and self.is_running:
            # 如果未連接，嘗試連接
            if not self.is_connected:
                if self._connect():
                    byte_buffer = b""
                else:
                    # 等待後重試
                    time.sleep(config.network.reconnect_interval)
                    continue
            
            # 讀取資料
            try:
                chunk = self.socket.recv(config.network.buffer_size)
                if not chunk:
                    # 連接已關閉
                    self.debug_log("Connection closed by sender")
                    self._disconnect()
                    continue
                
                byte_buffer += chunk
                
                # 按行分割
                while b'\n' in byte_buffer:
                    line, byte_buffer = byte_buffer.split(b'\n', 1)
                    if line:
                        self.data_queue.put(line)
                        
            except socket.timeout:
                continue
            except Exception as e:
                self.debug_log(f"Read error: {e}")
                self._disconnect()
        
        self._disconnect()
        self.debug_log("Connection loop ended")
    
    def _process_data_loop(self):
        """資料處理執行緒（負責解析和回調）"""
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
                        
                except UnicodeDecodeError as e:
                    print(f"[RX] Decode error: {e}")
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[RX] Error: {e}")
                
        self.debug_log("Process thread ended")
    
    def _parse_line(self, line: str) -> Optional[FrameData]:
        """
        解析一行 JSON 資料
        
        Args:
            line: JSON 字串
            
        Returns:
            FrameData 或 None
        """
        if not line.startswith('{'):
            return None
            
        try:
            data = json.loads(line)
            
            # 支援新舊格式
            inner_data = data
            if data.get("name") == "INVOKE" and "data" in data:
                inner_data = data["data"]
            
            # 解析影像（如果有）
            image = None
            if "image" in inner_data:
                try:
                    img_b64 = inner_data["image"]
                    img_bytes = base64.b64decode(img_b64)
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                except Exception as e:
                    self.debug_log(f"Image decode error: {e}")
            
            # 建構 FrameData
            frame_info = inner_data.get("frame_info", {})
            
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
            
            # 永遠輸出幀編號到終端
            people_count = len(frame_data.keypoints) if frame_data.keypoints else 0
            print(f"[RX] Frame #{frame_data.frame_no} - {people_count} people")
            
            return frame_data
            
        except json.JSONDecodeError as e:
            print(f"[RX] JSON error at {e.pos}: {e.msg}")
            return None
    
    def _update_fps(self):
        """更新 FPS 統計"""
        self.frame_count += 1
        self.last_data_time = time.time()  # 記錄最後收到資料的時間
        elapsed = time.time() - self.fps_start_time
        
        if elapsed >= 1.0:
            self.current_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start_time = time.time()
    
    def get_fps(self) -> float:
        """獲取當前 FPS"""
        return self.current_fps
    
    def get_connection_info(self) -> str:
        """獲取連接資訊"""
        if self.mode == "server":
            if self.is_connected and self.client_addr:
                return f"Server:{self.port} ← {self.client_addr[0]}:{self.client_addr[1]}"
            return f"Server:{self.port} (等待連接...)"
        else:
            if self.is_connected:
                return f"Client → {self.host}:{self.port}"
            return "未連接"
