"""
gui_interface.py - 發射端圖形介面模組

這個模組負責：
- 建立 Tkinter 圖形介面
- 三個分頁：WiFi 接收、Serial 接收、Webcam 測試
- 切換分頁時選定該頁的傳輸方式
- 顯示影像預覽
- 處理使用者互動

介面佈局：
┌─────────────────────────────────────────────────────┐
│  Server: 127.0.0.1:9527  [狀態]                     │  <- 頂部工具列
├─────────────────────────────────────────────────────┤
│  [📡 WiFi] [🔌 Serial] [📷 Webcam]                  │  <- 分頁標籤
├═══════════════════════════════════════════════════════┤
│  各分頁內容（根據選擇的來源顯示不同控制項）           │
└─────────────────────────────────────────────────────┘
"""

import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from device_simulator.config import config

# COCO 骨架連接定義
COCO_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16)
]


class SenderGUIInterface:
    """發射端圖形介面類"""
    
    def __init__(self, root: tk.Tk):
        """
        初始化 GUI
        
        Args:
            root: Tkinter 根視窗
        """
        self.root = root
        self.root.title(config.gui.window_title)
        self.root.geometry(config.gui.window_size)
        
        # 狀態變數
        self.is_sending = False
        self.current_source = "wifi"  # wifi, serial, webcam
        self.client_connected = False
        
        # 顯示相關
        self.tk_image = None
        self.canvas_w = config.gui.canvas_width
        self.canvas_h = config.gui.canvas_height
        
        # 統計
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        
        # 回調函數
        self.on_source_changed: Optional[Callable[[str], None]] = None
        self.on_wifi_start: Optional[Callable[[], bool]] = None
        self.on_wifi_stop: Optional[Callable[[], None]] = None
        self.on_serial_connect: Optional[Callable[[str], bool]] = None
        self.on_serial_disconnect: Optional[Callable[[], None]] = None
        self.on_webcam_start: Optional[Callable[[int], bool]] = None
        self.on_webcam_stop: Optional[Callable[[], None]] = None
        self.on_webcam_fps_change: Optional[Callable[[float], None]] = None
        self.on_webcam_camera_change: Optional[Callable[[int], bool]] = None
        self.on_webcam_reid_toggle: Optional[Callable[[bool], None]] = None
        self.on_webcam_floating_fps_toggle: Optional[Callable[[bool], None]] = None
        self.on_webcam_random_blocking_toggle: Optional[Callable[[bool], None]] = None
        self.on_webcam_yolo_change: Optional[Callable[[str], bool]] = None
        self.on_video_start: Optional[Callable[[str], bool]] = None
        self.on_video_stop: Optional[Callable[[], None]] = None
        self.on_video_fps_change: Optional[Callable[[float], None]] = None
        self.on_video_reid_toggle: Optional[Callable[[bool], None]] = None
        self.on_video_floating_fps_toggle: Optional[Callable[[bool], None]] = None
        self.on_video_random_blocking_toggle: Optional[Callable[[bool], None]] = None
        self.on_video_yolo_change: Optional[Callable[[str], bool]] = None
        self.get_serial_ports: Optional[Callable[[], List[str]]] = None
        self.get_camera_options: Optional[Callable[[], List[str]]] = None
        self.get_webcam_preview_frame: Optional[Callable[[], Optional[np.ndarray]]] = None
        self.get_webcam_preview_keypoints: Optional[Callable[[], List[Any]]] = None
        
        # 建立介面
        self._setup_ui()
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[SenderGUI][{time.time():.3f}] {msg}")
    
    def _setup_ui(self):
        """建立 UI 元件"""
        self._setup_top_bar()
        self._setup_notebook()
    
    def _setup_top_bar(self):
        """建立頂部工具列"""
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill=tk.X)
        
        # Receiver 連接資訊
        ttk.Label(top_frame, text="Receiver:").pack(side=tk.LEFT, padx=5)
        self.lbl_server = ttk.Label(
            top_frame, 
            text=f"{config.network.receiver_host}:{config.network.receiver_port}",
            font=("Helvetica", 12, "bold")
        )
        self.lbl_server.pack(side=tk.LEFT, padx=5)
        
        # 分隔線
        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=15)
        
        # 連接狀態
        ttk.Label(top_frame, text="狀態:").pack(side=tk.LEFT, padx=5)
        self.lbl_client_status = ttk.Label(top_frame, text="● 等待連接", foreground="gray")
        self.lbl_client_status.pack(side=tk.LEFT, padx=5)
        
        # 傳送狀態
        self.lbl_send_status = ttk.Label(top_frame, text="", foreground="gray")
        self.lbl_send_status.pack(side=tk.RIGHT, padx=10)
    
    def _setup_notebook(self):
        """建立分頁結構"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 分頁 1：WiFi 接收
        self.tab_wifi = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_wifi, text="📡 WiFi 接收")
        self._setup_wifi_tab()
        
        # 分頁 2：Serial 接收
        self.tab_serial = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_serial, text="🔌 Serial 接收")
        self._setup_serial_tab()
        
        # 分頁 3：Webcam 測試
        self.tab_webcam = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_webcam, text="📷 Webcam 測試")
        self._setup_webcam_tab()
        
        # 分頁 4：Video 影片測試
        self.tab_video = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_video, text="🎬 Video 影片")
        self._setup_video_tab()
        
        # 綁定分頁切換事件
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _setup_wifi_tab(self):
        """建立 WiFi 接收分頁"""
        main_frame = ttk.Frame(self.tab_wifi, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 說明
        info_group = ttk.LabelFrame(main_frame, text="WiFi 接收說明", padding=10)
        info_group.pack(fill=tk.X, pady=5)
        
        info_text = f"""此模式監聽來自 WiseEye2 裝置的 WiFi 資料傳輸。

監聽位址: {config.wifi.listen_host}:{config.wifi.listen_port}

使用方式：
1. 確保 WiseEye2 裝置與電腦在同一網路
2. 設定 WiseEye2 將資料傳送到此電腦的 IP 位址
3. 點擊「開始監聽」接收資料
4. 資料將自動轉發給接收端"""
        
        ttk.Label(info_group, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
        
        # 控制區
        control_group = ttk.LabelFrame(main_frame, text="控制", padding=10)
        control_group.pack(fill=tk.X, pady=5)
        
        self.btn_wifi_start = ttk.Button(
            control_group,
            text="▶ 開始監聽",
            command=self._on_wifi_toggle
        )
        self.btn_wifi_start.pack(side=tk.LEFT, padx=5)
        
        self.lbl_wifi_status = ttk.Label(control_group, text="狀態：已停止")
        self.lbl_wifi_status.pack(side=tk.LEFT, padx=20)
        
        # 統計區
        stats_group = ttk.LabelFrame(main_frame, text="統計", padding=10)
        stats_group.pack(fill=tk.X, pady=5)
        
        self.lbl_wifi_frames = ttk.Label(stats_group, text="接收幀數：0")
        self.lbl_wifi_frames.pack(anchor=tk.W)
        
        self.lbl_wifi_fps = ttk.Label(stats_group, text="接收 FPS：0")
        self.lbl_wifi_fps.pack(anchor=tk.W)
    
    def _setup_serial_tab(self):
        """建立 Serial 接收分頁"""
        main_frame = ttk.Frame(self.tab_serial, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 串口設定
        port_group = ttk.LabelFrame(main_frame, text="串口設定", padding=10)
        port_group.pack(fill=tk.X, pady=5)
        
        port_row = ttk.Frame(port_group)
        port_row.pack(fill=tk.X)
        
        ttk.Label(port_row, text="Port:").pack(side=tk.LEFT, padx=5)
        self.serial_port_combo = ttk.Combobox(port_row, width=30)
        self.serial_port_combo.pack(side=tk.LEFT, padx=5)
        self.serial_port_combo.set(config.serial.default_port)
        
        ttk.Button(
            port_row, 
            text="🔄 重新整理",
            command=self._on_refresh_serial_ports
        ).pack(side=tk.LEFT, padx=5)
        
        # 連接控制
        control_group = ttk.LabelFrame(main_frame, text="控制", padding=10)
        control_group.pack(fill=tk.X, pady=5)
        
        self.btn_serial_connect = ttk.Button(
            control_group,
            text="▶ 連接",
            command=self._on_serial_toggle
        )
        self.btn_serial_connect.pack(side=tk.LEFT, padx=5)
        
        self.lbl_serial_status = ttk.Label(control_group, text="狀態：未連接")
        self.lbl_serial_status.pack(side=tk.LEFT, padx=20)
        
        # 統計區
        stats_group = ttk.LabelFrame(main_frame, text="統計", padding=10)
        stats_group.pack(fill=tk.X, pady=5)
        
        self.lbl_serial_frames = ttk.Label(stats_group, text="接收幀數：0")
        self.lbl_serial_frames.pack(anchor=tk.W)
        
        self.lbl_serial_fps = ttk.Label(stats_group, text="接收 FPS：0")
        self.lbl_serial_fps.pack(anchor=tk.W)
        
        # 裝置資訊
        device_group = ttk.LabelFrame(main_frame, text="裝置資訊", padding=10)
        device_group.pack(fill=tk.X, pady=5)
        
        self.lbl_device_id = ttk.Label(device_group, text="ID: -")
        self.lbl_device_id.pack(anchor=tk.W)
        
        self.lbl_device_model = ttk.Label(device_group, text="Model: -")
        self.lbl_device_model.pack(anchor=tk.W)
        
        self.lbl_device_ver = ttk.Label(device_group, text="Ver: -")
        self.lbl_device_ver.pack(anchor=tk.W)
    
    def _setup_webcam_tab(self):
        """建立 Webcam 測試分頁"""
        main_frame = ttk.Frame(self.tab_webcam, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左側：影像預覽
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        canvas_frame = ttk.LabelFrame(left_frame, text="影像預覽", padding=5)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.webcam_canvas = tk.Canvas(
            canvas_frame, 
            bg="black", 
            width=config.gui.canvas_width,
            height=config.gui.canvas_height
        )
        self.webcam_canvas.pack(fill=tk.BOTH, expand=True)
        self.webcam_canvas.bind("<Configure>", self._on_webcam_canvas_resize)
        
        # 右側：控制面板
        right_frame = ttk.Frame(main_frame, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        right_frame.pack_propagate(False)
        
        # 攝像頭選擇
        camera_group = ttk.LabelFrame(right_frame, text="攝像頭選擇", padding=10)
        camera_group.pack(fill=tk.X, pady=5)
        
        self.camera_combo = ttk.Combobox(camera_group, state="readonly")
        self.camera_combo.pack(fill=tk.X)
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_selected)
        
        ttk.Button(
            camera_group,
            text="🔄 重新偵測",
            command=self._on_refresh_cameras
        ).pack(fill=tk.X, pady=5)
        
        # YOLO 模型選擇
        yolo_group = ttk.LabelFrame(right_frame, text="YOLO 模型", padding=10)
        yolo_group.pack(fill=tk.X, pady=5)
        
        self.yolo_model_var = tk.StringVar(value="yolov8n-pose")
        
        # 水平排列的 Radio Buttons
        radio_frame = ttk.Frame(yolo_group)
        radio_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(
            radio_frame,
            text="YOLOv8n-Pose",
            variable=self.yolo_model_var,
            value="yolov8n-pose",
            command=self._on_yolo_model_selected
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Radiobutton(
            radio_frame,
            text="YOLO11n-Pose",
            variable=self.yolo_model_var,
            value="yolo11n-pose",
            command=self._on_yolo_model_selected
        ).pack(side=tk.LEFT, padx=10)
        
        self.lbl_yolo_status = ttk.Label(
            yolo_group,
            text="",
            font=("Helvetica", 9)
        )
        self.lbl_yolo_status.pack(anchor=tk.W, pady=2)
        
        # FPS 控制
        fps_group = ttk.LabelFrame(right_frame, text="採樣率設定", padding=10)
        fps_group.pack(fill=tk.X, pady=5)
        
        self.fps_label_var = tk.StringVar(value=f"採樣: {config.webcam.default_fps:.0f} FPS")
        ttk.Label(fps_group, textvariable=self.fps_label_var).pack()
        
        self.fps_var = tk.DoubleVar(value=config.webcam.default_fps)
        self.fps_slider = ttk.Scale(
            fps_group, 
            from_=config.webcam.min_fps, 
            to=config.webcam.max_fps,
            variable=self.fps_var, 
            orient=tk.HORIZONTAL,
            command=self._on_fps_change
        )
        self.fps_slider.pack(fill=tk.X, pady=5)
        
        # FPS 快速按鈕
        presets_frame = ttk.Frame(fps_group)
        presets_frame.pack(fill=tk.X, pady=5)
        for fps_val in [1, 2, 15, 30]:
            btn = ttk.Button(
                presets_frame, 
                text=f"{fps_val}",
                width=4,
                command=lambda f=fps_val: self._set_fps(f)
            )
            btn.pack(side=tk.LEFT, padx=3, expand=True)
        
        # 浮動採樣率
        self.floating_fps_var = tk.BooleanVar(value=config.webcam.floating_fps)
        self.chk_floating_fps = ttk.Checkbutton(
            fps_group,
            text="模擬浮動採樣率 (WiseEye2 特性)",
            variable=self.floating_fps_var,
            command=self._on_floating_fps_toggle
        )
        self.chk_floating_fps.pack(anchor=tk.W, pady=2)
        
        self.random_blocking_var = tk.BooleanVar(value=config.webcam.random_blocking)
        self.chk_random_blocking = ttk.Checkbutton(
            fps_group,
            text="模擬隨機阻塞 (網路/處理延遲)",
            variable=self.random_blocking_var,
            command=self._on_random_blocking_toggle
        )
        self.chk_random_blocking.pack(anchor=tk.W, pady=2)
        
        # ReID 控制
        reid_group = ttk.LabelFrame(right_frame, text="ReID 設定", padding=10)
        reid_group.pack(fill=tk.X, pady=5)
        
        self.reid_enabled_var = tk.BooleanVar(value=True)
        self.chk_reid = ttk.Checkbutton(
            reid_group,
            text="啟用 ReID 特徵提取",
            variable=self.reid_enabled_var,
            command=self._on_reid_toggle
        )
        self.chk_reid.pack(anchor=tk.W)
        
        self.lbl_reid_status = ttk.Label(
            reid_group,
            text="ReID: 模擬模式 (512-dim)",
            font=("Helvetica", 9)
        )
        self.lbl_reid_status.pack(anchor=tk.W, pady=2)
        
        # 控制按鈕
        control_group = ttk.LabelFrame(right_frame, text="控制", padding=10)
        control_group.pack(fill=tk.X, pady=5)
        
        self.btn_webcam_start = ttk.Button(
            control_group,
            text="▶ 開始擷取",
            command=self._on_webcam_toggle
        )
        self.btn_webcam_start.pack(fill=tk.X)
        
        self.lbl_webcam_status = ttk.Label(
            control_group, 
            text="狀態：已停止",
            font=("Helvetica", 10)
        )
        self.lbl_webcam_status.pack(pady=5)
        
        # 統計資訊
        stats_group = ttk.LabelFrame(right_frame, text="統計", padding=10)
        stats_group.pack(fill=tk.X, pady=5)
        
        self.lbl_webcam_frames = ttk.Label(stats_group, text="擷取幀數：0")
        self.lbl_webcam_frames.pack(anchor=tk.W)
        
        self.lbl_webcam_fps = ttk.Label(stats_group, text="實際 FPS：0")
        self.lbl_webcam_fps.pack(anchor=tk.W)
        
        self.lbl_webcam_persons = ttk.Label(stats_group, text="偵測人數：0")
        self.lbl_webcam_persons.pack(anchor=tk.W)

    def _setup_video_tab(self):
        """建立 Video 測試分頁"""
        main_frame = ttk.Frame(self.tab_video, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左側：影像預覽
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        canvas_frame = ttk.LabelFrame(left_frame, text="影像預覽", padding=5)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.video_canvas = tk.Canvas(
            canvas_frame, 
            bg="black", 
            width=config.gui.canvas_width,
            height=config.gui.canvas_height
        )
        self.video_canvas.pack(fill=tk.BOTH, expand=True)
        self.video_canvas.bind("<Configure>", self._on_video_canvas_resize)
        
        # 右側：控制面板
        right_frame = ttk.Frame(main_frame, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        right_frame.pack_propagate(False)
        
        # 影片選擇
        video_group = ttk.LabelFrame(right_frame, text="影片選擇", padding=10)
        video_group.pack(fill=tk.X, pady=5)
        
        self.video_path_var = tk.StringVar(value="")
        self.lbl_video_path = ttk.Label(video_group, text="未選擇影片", wraplength=250)
        self.lbl_video_path.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            video_group,
            text="📁 選擇影片檔案",
            command=self._on_select_video_file
        ).pack(fill=tk.X, pady=5)
        
        # YOLO 模型選擇
        yolo_group = ttk.LabelFrame(right_frame, text="YOLO 模型", padding=10)
        yolo_group.pack(fill=tk.X, pady=5)
        
        self.video_yolo_model_var = tk.StringVar(value="yolov8n-pose")
        
        radio_frame = ttk.Frame(yolo_group)
        radio_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(
            radio_frame, text="YOLOv8n-Pose", variable=self.video_yolo_model_var,
            value="yolov8n-pose", command=self._on_video_yolo_model_selected
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Radiobutton(
            radio_frame, text="YOLO11n-Pose", variable=self.video_yolo_model_var,
            value="yolo11n-pose", command=self._on_video_yolo_model_selected
        ).pack(side=tk.LEFT, padx=10)
        
        # FPS 控制
        fps_group = ttk.LabelFrame(right_frame, text="採樣率設定", padding=10)
        fps_group.pack(fill=tk.X, pady=5)
        
        self.video_fps_label_var = tk.StringVar(value=f"採樣: {config.webcam.default_fps:.0f} FPS")
        ttk.Label(fps_group, textvariable=self.video_fps_label_var).pack()
        
        self.video_fps_var = tk.DoubleVar(value=config.webcam.default_fps)
        self.video_fps_slider = ttk.Scale(
            fps_group, from_=config.webcam.min_fps, to=config.webcam.max_fps,
            variable=self.video_fps_var, orient=tk.HORIZONTAL, command=self._on_video_fps_change
        )
        self.video_fps_slider.pack(fill=tk.X, pady=5)

        # 浮動採樣率與隨機阻塞
        self.video_floating_fps_var = tk.BooleanVar(value=config.webcam.floating_fps)
        ttk.Checkbutton(
            fps_group, text="模擬浮動採樣率 (WiseEye2 特性)", variable=self.video_floating_fps_var,
            command=self._on_video_floating_fps_toggle
        ).pack(anchor=tk.W, pady=2)
        
        self.video_random_blocking_var = tk.BooleanVar(value=config.webcam.random_blocking)
        ttk.Checkbutton(
            fps_group, text="模擬隨機阻塞 (網路/處理延遲)", variable=self.video_random_blocking_var,
            command=self._on_video_random_blocking_toggle
        ).pack(anchor=tk.W, pady=2)
        
        # ReID 控制
        reid_group = ttk.LabelFrame(right_frame, text="ReID 設定", padding=10)
        reid_group.pack(fill=tk.X, pady=5)
        
        self.video_reid_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            reid_group, text="啟用 ReID 特徵提取", variable=self.video_reid_enabled_var,
            command=self._on_video_reid_toggle
        ).pack(anchor=tk.W)
        
        # 控制按鈕
        control_group = ttk.LabelFrame(right_frame, text="控制", padding=10)
        control_group.pack(fill=tk.X, pady=5)
        
        self.btn_video_start = ttk.Button(
            control_group, text="▶ 開始播放", command=self._on_video_toggle
        )
        self.btn_video_start.pack(fill=tk.X)
        
        self.lbl_video_status = ttk.Label(control_group, text="狀態：已停止")
        self.lbl_video_status.pack(pady=5)
        
        # 統計資訊
        stats_group = ttk.LabelFrame(right_frame, text="統計", padding=10)
        stats_group.pack(fill=tk.X, pady=5)
        
        self.lbl_video_frames = ttk.Label(stats_group, text="處理幀數：0")
        self.lbl_video_frames.pack(anchor=tk.W)
        self.lbl_video_fps = ttk.Label(stats_group, text="實際 FPS：0.0")
        self.lbl_video_fps.pack(anchor=tk.W)
    
    # ===== 事件處理 =====
    
    def _on_tab_changed(self, event):
        """分頁切換事件"""
        selected = self.notebook.index(self.notebook.select())
        source_map = {0: "wifi", 1: "serial", 2: "webcam", 3: "video"}
        new_source = source_map.get(selected, "wifi")
        
        if new_source != self.current_source:
            self.debug_log(f"Source changed: {self.current_source} -> {new_source}")
            self.current_source = new_source
            
            if self.on_source_changed:
                self.on_source_changed(new_source)
    
    def _on_wifi_toggle(self):
        """WiFi 開始/停止"""
        if not self.is_sending:
            if self.on_wifi_start and self.on_wifi_start():
                self.is_sending = True
                self.btn_wifi_start.config(text="⏹ 停止監聽")
                self.lbl_wifi_status.config(text="狀態：等待 ESP32 連接...", foreground="orange")
        else:
            if self.on_wifi_stop:
                self.on_wifi_stop()
            self.is_sending = False
            self.btn_wifi_start.config(text="▶ 開始監聯")
            self.lbl_wifi_status.config(text="狀態：已停止", foreground="gray")
    
    def _on_refresh_serial_ports(self):
        """重新整理串口列表"""
        if self.get_serial_ports:
            ports = self.get_serial_ports()
            self.serial_port_combo['values'] = ports
            if ports and not self.serial_port_combo.get():
                self.serial_port_combo.current(0)
    
    def _on_serial_toggle(self):
        """Serial 連接/斷開"""
        if not self.is_sending:
            port = self.serial_port_combo.get()
            if self.on_serial_connect and self.on_serial_connect(port):
                self.is_sending = True
                self.btn_serial_connect.config(text="⏹ 斷開")
                self.lbl_serial_status.config(text="狀態：已連接", foreground="green")
        else:
            if self.on_serial_disconnect:
                self.on_serial_disconnect()
            self.is_sending = False
            self.btn_serial_connect.config(text="▶ 連接")
            self.lbl_serial_status.config(text="狀態：未連接", foreground="gray")
    
    def _on_refresh_cameras(self):
        """重新偵測攝像頭"""
        if self.get_camera_options:
            options = self.get_camera_options()
            self.camera_combo['values'] = options
            if options:
                self.camera_combo.current(0)
    
    def _on_camera_selected(self, event):
        """攝像頭選擇變更"""
        selected = self.camera_combo.get()
        try:
            camera_id = int(selected.split(':')[0])
            if self.on_webcam_camera_change:
                self.on_webcam_camera_change(camera_id)
        except (ValueError, IndexError):
            pass
    
    def _on_fps_change(self, val):
        """FPS 滑桿變更"""
        fps = float(val)
        self.fps_label_var.set(f"採樣: {fps:.0f} FPS")
        if self.on_webcam_fps_change:
            self.on_webcam_fps_change(fps)
    
    def _set_fps(self, fps: float):
        """設定 FPS"""
        self.fps_var.set(fps)
        self.fps_label_var.set(f"採樣: {fps:.0f} FPS")
        if self.on_webcam_fps_change:
            self.on_webcam_fps_change(fps)
    
    def _on_reid_toggle(self):
        """ReID 開關切換"""
        enabled = self.reid_enabled_var.get()
        self.debug_log(f"ReID toggle: {enabled}")
        if self.on_webcam_reid_toggle:
            self.on_webcam_reid_toggle(enabled)
        status = "已啟用 (256-dim)" if enabled else "已停用"
        self.lbl_reid_status.config(text=f"ReID: {status}")
    
    def _on_floating_fps_toggle(self):
        """浮動採樣率開關切換"""
        enabled = self.floating_fps_var.get()
        self.debug_log(f"Floating FPS toggle: {enabled}")
        if self.on_webcam_floating_fps_toggle:
            self.on_webcam_floating_fps_toggle(enabled)
            
    def _on_random_blocking_toggle(self):
        """隨機阻塞開關切換"""
        enabled = self.random_blocking_var.get()
        self.debug_log(f"Random blocking toggle: {enabled}")
        if self.on_webcam_random_blocking_toggle:
            self.on_webcam_random_blocking_toggle(enabled)
    
    def _on_yolo_model_selected(self, event=None):
        """YOLO 模型選擇變更"""
        model_name = self.yolo_model_var.get()
        self.debug_log(f"YOLO model selected: {model_name}")
        if self.on_webcam_yolo_change:
            success = self.on_webcam_yolo_change(model_name)
            if success:
                self.lbl_yolo_status.config(text=f"✓ 已切換到 {model_name}")
            else:
                self.lbl_yolo_status.config(text=f"✗ 切換失敗")

    # Video 相關處理
    def _on_select_video_file(self):
        """選擇影片檔案"""
        file_path = filedialog.askopenfilename(
            title="選擇影片檔案",
            filetypes=[("影片檔案", "*.mp4 *.avi *.mov *.mkv"), ("所有檔案", "*.*")]
        )
        if file_path:
            self.video_path_var.set(file_path)
            self.lbl_video_path.config(text=os.path.basename(file_path))
            self.debug_log(f"Selected video: {file_path}")

    def _on_video_toggle(self):
        """Video 開始/停止"""
        if not self.is_sending:
            video_path = self.video_path_var.get()
            if not video_path:
                messagebox.showwarning("警告", "請先選擇影片檔案")
                return
            
            if self.on_video_start and self.on_video_start(video_path):
                self.is_sending = True
                self.btn_video_start.config(text="⏹ 停止播放")
                self.lbl_video_status.config(text="狀態：播放中...", foreground="green")
                self._update_video_preview()
        else:
            if self.on_video_stop:
                self.on_video_stop()
            self.is_sending = False
            self.btn_video_start.config(text="▶ 開始播放")
            self.lbl_video_status.config(text="狀態：已停止", foreground="gray")

    def _on_video_fps_change(self, val):
        """Video FPS 滑桿變更"""
        fps = float(val)
        self.video_fps_label_var.set(f"採樣: {fps:.0f} FPS")
        if self.on_video_fps_change:
            self.on_video_fps_change(fps)

    def _on_video_reid_toggle(self):
        """Video ReID 開關切換"""
        enabled = self.video_reid_enabled_var.get()
        if self.on_video_reid_toggle:
            self.on_video_reid_toggle(enabled)

    def _on_video_floating_fps_toggle(self):
        """Video 浮動採樣率開關切換"""
        enabled = self.video_floating_fps_var.get()
        if self.on_video_floating_fps_toggle:
            self.on_video_floating_fps_toggle(enabled)

    def _on_video_random_blocking_toggle(self):
        """Video 隨機阻塞開關切換"""
        enabled = self.video_random_blocking_var.get()
        if self.on_video_random_blocking_toggle:
            self.on_video_random_blocking_toggle(enabled)

    def _on_video_yolo_model_selected(self):
        """Video YOLO 模型選擇變更"""
        model_name = self.video_yolo_model_var.get()
        if self.on_video_yolo_change:
            self.on_video_yolo_change(model_name)

    def _on_video_canvas_resize(self, event):
        """Video 畫布尺寸變更"""
        self.canvas_w = event.width
        self.canvas_h = event.height

    def _update_video_preview(self):
        """更新 Video 預覽"""
        pass  # 將由主程式實作
    
    def get_preview_mode(self) -> str:
        """獲取預覽模式 - 固定返回 sampled（採樣幀率預覽）"""
        return "sampled"
    
    def _on_webcam_toggle(self):
        """Webcam 開始/停止"""
        if not self.is_sending:
            selected = self.camera_combo.get()
            camera_id = 0
            try:
                camera_id = int(selected.split(':')[0])
            except (ValueError, IndexError):
                pass
            
            if self.on_webcam_start and self.on_webcam_start(camera_id):
                self.is_sending = True
                self.btn_webcam_start.config(text="⏹ 停止擷取")
                self.lbl_webcam_status.config(text="狀態：擷取中...", foreground="green")
                self._update_webcam_preview()
        else:
            if self.on_webcam_stop:
                self.on_webcam_stop()
            self.is_sending = False
            self.btn_webcam_start.config(text="▶ 開始擷取")
            self.lbl_webcam_status.config(text="狀態：已停止", foreground="gray")
    
    def _on_webcam_canvas_resize(self, event):
        """Webcam 畫布尺寸變更"""
        self.canvas_w = event.width
        self.canvas_h = event.height
    
    # ===== 公開方法 =====
    
    def update_client_status(self, connected: bool):
        """更新 Receiver 連接狀態"""
        self.client_connected = connected
        if connected:
            self.lbl_client_status.config(text="● 已連接 Receiver", foreground="green")
        else:
            self.lbl_client_status.config(text="● 等待連接", foreground="gray")
    
    def update_send_status(self, text: str):
        """更新傳送狀態"""
        self.lbl_send_status.config(text=text)
    
    def update_wifi_stats(self, frames: int, fps: float):
        """更新 WiFi 統計"""
        self.lbl_wifi_frames.config(text=f"接收幀數：{frames}")
        self.lbl_wifi_fps.config(text=f"接收 FPS：{fps:.1f}")
    
    def update_wifi_connection_status(self, connected: bool):
        """更新 WiFi ESP32 連接狀態"""
        if connected:
            self.lbl_wifi_status.config(text="狀態：ESP32 已連接", foreground="green")
        else:
            self.lbl_wifi_status.config(text="狀態：等待 ESP32 連接...", foreground="orange")
    
    def update_serial_stats(self, frames: int, fps: float, device_info: Dict = None):
        """更新 Serial 統計"""
        self.lbl_serial_frames.config(text=f"接收幀數：{frames}")
        self.lbl_serial_fps.config(text=f"接收 FPS：{fps:.1f}")
        
        if device_info:
            self.lbl_device_id.config(text=f"ID: {device_info.get('device_id', '-')}")
            self.lbl_device_model.config(text=f"Model: {device_info.get('name', '-')}")
            self.lbl_device_ver.config(text=f"Ver: {device_info.get('ver', '-')}")
    
    def update_webcam_stats(self, frames: int, fps: float, persons: int):
        """更新 Webcam 統計"""
        self.lbl_webcam_frames.config(text=f"擷取幀數：{frames}")
        self.lbl_webcam_fps.config(text=f"實際 FPS：{fps:.1f}")
        self.lbl_webcam_persons.config(text=f"偵測人數：{persons}")
    
    def update_webcam_preview(self, frame: np.ndarray, keypoints: List[Any] = None):
        """更新 Webcam 預覽畫面"""
        if frame is None:
            return
        
        try:
            # 繪製骨架
            display = frame.copy()
            if keypoints:
                self._draw_keypoints(display, keypoints)
            
            # 縮放
            display = self._resize_image(display)
            
            # 轉換顯示
            img_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(img_rgb)
            self.tk_image = ImageTk.PhotoImage(pil_image)
            
            self.webcam_canvas.delete("all")
            self.webcam_canvas.create_image(
                self.canvas_w // 2,
                self.canvas_h // 2,
                image=self.tk_image,
                anchor=tk.CENTER
            )
        except Exception as e:
            self.debug_log(f"Preview update error: {e}")

    def update_video_preview(self, frame: np.ndarray, keypoints: List[Any] = None):
        """更新 Video 預覽畫面"""
        if frame is None:
            return
        
        try:
            # 繪製骨架
            display = frame.copy()
            if keypoints:
                self._draw_keypoints(display, keypoints)
            
            # 縮放
            display = self._resize_image(display)
            
            # 轉換顯示
            img_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(img_rgb)
            self.tk_video_image = ImageTk.PhotoImage(pil_image)
            
            self.video_canvas.delete("all")
            self.video_canvas.create_image(
                self.canvas_w // 2,
                self.canvas_h // 2,
                image=self.tk_video_image,
                anchor=tk.CENTER
            )
        except Exception as e:
            self.debug_log(f"Video preview update error: {e}")
    
    def _draw_keypoints(self, img: np.ndarray, keypoints: List[Any]):
        """繪製骨架關鍵點"""
        for person_idx, person in enumerate(keypoints):
            if not person or len(person) < 1:
                continue
            
            # 邊界框
            box = person[0]
            if len(box) >= 6:
                x, y, w, h, score, _ = box[:6]
                cv2.rectangle(img, (int(x), int(y)), (int(x+w), int(y+h)), (0, 255, 0), 2)
                cv2.putText(
                    img, f"ID:{person_idx}", 
                    (int(x), int(y)-5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
                )
            
            # 關鍵點
            kpts = person[1:]
            parsed_kpts = []
            for kp in kpts:
                if len(kp) >= 3:
                    parsed_kpts.append((int(kp[0]), int(kp[1]), kp[2]))
                else:
                    parsed_kpts.append((0, 0, 0))
            
            # 繪製連線
            for p1, p2 in COCO_SKELETON:
                if p1 < len(parsed_kpts) and p2 < len(parsed_kpts):
                    kp1, kp2 = parsed_kpts[p1], parsed_kpts[p2]
                    if kp1[2] > 0.3 and kp2[2] > 0.3:
                        cv2.line(img, (kp1[0], kp1[1]), (kp2[0], kp2[1]), (255, 255, 0), 2)
            
            # 繪製點
            for kp in parsed_kpts:
                if kp[2] > 0.3:
                    cv2.circle(img, (kp[0], kp[1]), 3, (0, 255, 255), -1)
    
    def _resize_image(self, img: np.ndarray) -> np.ndarray:
        """縮放影像"""
        if self.canvas_w <= 1 or self.canvas_h <= 1:
            return img
        
        h, w = img.shape[:2]
        scale = min(self.canvas_w / w, self.canvas_h / h)
        nw, nh = int(w * scale), int(h * scale)
        
        if nw > 0 and nh > 0:
            return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        return img
    
    def _update_webcam_preview(self):
        """定期更新 Webcam 預覽（由外部調用）"""
        pass  # 將由主程式實作
    
    def set_camera_options(self, options: List[str]):
        """設定攝像頭選項"""
        self.camera_combo['values'] = options
        if options:
            self.camera_combo.current(0)
    
    def set_serial_ports(self, ports: List[str]):
        """設定串口列表"""
        self.serial_port_combo['values'] = ports
    
    def stop_current_source(self):
        """停止當前資料來源"""
        if not self.is_sending:
            return
        
        if self.current_source == "wifi":
            self._on_wifi_toggle()
        elif self.current_source == "serial":
            self._on_serial_toggle()
        elif self.current_source == "webcam":
            self._on_webcam_toggle()
        elif self.current_source == "video":
            self._on_video_toggle()
    
    def schedule(self, callback, delay_ms: int = 0):
        """排程在主執行緒執行"""
        self.root.after(delay_ms, callback)
    
    def run(self):
        """啟動主迴圈"""
        self.root.mainloop()
