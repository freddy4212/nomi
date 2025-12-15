"""
gui_interface.py - 圖形介面模組

這個模組負責：
- 建立 Tkinter 圖形介面
- 分頁結構：主頁（即時辨識）和錄入頁（向量錄入）
- 顯示影像和骨架
- 在下方顯示動作識別描述區域
- 處理使用者互動
- ReID 人物識別與向量錄入

介面佈局：
┌─────────────────────────────────────────────────────┐
│  [Port] [Connect] [View Mode]                       │  <- 頂部工具列
├─────────────────────────────────────────────────────┤
│  [即時辨識] [向量錄入]                               │  <- 分頁標籤
├═══════════════════════════════════════════════════════┤
│  ┌─ 即時辨識分頁 ─────────────────────────────────┐   │
│  │ ┌─────────────────┬───────────────────┐       │   │
│  │ │                 │  Device Info      │       │   │
│  │ │  影像顯示區域    │  Frame Info       │       │   │
│  │ │  (骨架疊加)      │  ReID Results     │       │   │
│  │ │                 │  ID | Who | Score │       │   │
│  │ └─────────────────┴───────────────────┘       │   │
│  │ ┌─────────────────────────────────────┐       │   │
│  │ │     動作識別描述區域                 │       │   │
│  │ └─────────────────────────────────────┘       │   │
│  └───────────────────────────────────────────────┘   │
├═══════════════════════════════════════════════════════┤
│  ┌─ 向量錄入分頁 ─────────────────────────────────┐   │
│  │  [人名輸入] [開始錄製] [停止錄製]              │   │
│  │  錄製狀態：等待開始                           │   │
│  │  已錄製樣本：0                                │   │
│  │  已註冊人物列表...                            │   │
│  └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
"""

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

try:
    from .config import config
    from .reid_database import ReIDDatabase, get_reid_database
    from .serial_receiver import FrameData
    from .skeleton_processor import SkeletonFrame
    from .visualizer import SkeletonPlayer, Visualizer
except ImportError:
    from config import config
    from reid_database import ReIDDatabase, get_reid_database
    from serial_receiver import FrameData
    from skeleton_processor import SkeletonFrame
    from visualizer import SkeletonPlayer, Visualizer


class GUIInterface:
    """圖形介面類"""
    
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
        self.is_connected = False
        self.view_mode = tk.StringVar(value="overlay")
        self.cached_mode = "overlay"
        self.canvas_w = config.gui.canvas_width
        self.canvas_h = config.gui.canvas_height
        
        # 顯示相關
        self.tk_image = None
        self.image_item_id = None
        
        # 補幀播放器
        self.skeleton_player = SkeletonPlayer(None) # 這裡先傳入 None，稍後在 update_interpolated_frames 中更新
        self.interp_timer_id = None
        self.base_image_shape = (480, 640, 3)
        
        # FPS 統計
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        
        # ReID 資料快取
        self.current_reid_data = []
        self.last_reid_update = 0.0
        
        # ReID 資料庫
        self.reid_db = get_reid_database()
        
        # 錄製狀態
        self.is_recording = False
        self.recording_name = ""
        self.recording_vectors = []
        self.recording_start_time = 0.0
        
        # 回調函數
        self.on_connect: Optional[Callable[[str], bool]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        
        # 建立介面
        self._setup_ui()
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[GUI][{time.time():.3f}] {msg}")
    
    def _setup_ui(self):
        """建立 UI 元件"""
        self._setup_top_bar()
        self._setup_notebook()
    
    def _setup_top_bar(self):
        """建立頂部工具列"""
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill=tk.X)
        
        # 串口選擇
        ttk.Label(top_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_combo = ttk.Combobox(top_frame, width=30)
        self.port_combo.pack(side=tk.LEFT, padx=5)
        self.port_combo.set(config.serial.default_port)
        
        # 重新整理按鈕
        self.btn_refresh = ttk.Button(
            top_frame, 
            text="Refresh", 
            command=self._on_refresh_ports
        )
        self.btn_refresh.pack(side=tk.LEFT, padx=5)
        
        # 連接按鈕
        self.btn_connect = ttk.Button(
            top_frame, 
            text="Connect", 
            command=self._on_toggle_connection
        )
        self.btn_connect.pack(side=tk.LEFT, padx=5)
        
        # 分隔線
        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # 顯示模式
        ttk.Label(top_frame, text="View Mode:").pack(side=tk.LEFT, padx=5)
        self.view_mode.trace_add("write", self._on_mode_change)
        ttk.Radiobutton(
            top_frame, text="Original", 
            variable=self.view_mode, value="original"
        ).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(
            top_frame, text="Overlay", 
            variable=self.view_mode, value="overlay"
        ).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(
            top_frame, text="YOLO Only", 
            variable=self.view_mode, value="yolo_only"
        ).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(
            top_frame, text="Interpolated", 
            variable=self.view_mode, value="interpolated"
        ).pack(side=tk.LEFT, padx=8)
        
        # 狀態指示燈
        self.status_label = ttk.Label(top_frame, text="● 未連接", foreground="gray")
        self.status_label.pack(side=tk.RIGHT, padx=10)
    
    def _setup_notebook(self):
        """建立分頁結構"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 分頁 1：即時辨識
        self.tab_live = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_live, text="🎥 即時辨識")
        self._setup_live_tab()
        
        # 分頁 2：向量錄入
        self.tab_register = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_register, text="📝 向量錄入")
        self._setup_register_tab()
    
    def _setup_live_tab(self):
        """建立即時辨識分頁"""
        # 主內容區
        content_frame = ttk.Frame(self.tab_live)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左側：影像畫布
        self.canvas_frame = ttk.Frame(content_frame, borderwidth=2, relief="sunken")
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        
        # 右側：資訊面板
        right_panel = ttk.Frame(content_frame, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        right_panel.pack_propagate(False)
        
        # 裝置資訊
        device_group = ttk.LabelFrame(right_panel, text="Device Info")
        device_group.pack(fill=tk.X, pady=5)
        
        self.lbl_device_id = ttk.Label(device_group, text="ID: -")
        self.lbl_device_id.pack(anchor=tk.W, padx=5)
        
        self.lbl_model_name = ttk.Label(device_group, text="Model: -")
        self.lbl_model_name.pack(anchor=tk.W, padx=5)
        
        self.lbl_version = ttk.Label(device_group, text="Ver: -")
        self.lbl_version.pack(anchor=tk.W, padx=5)
        
        # 幀資訊
        frame_group = ttk.LabelFrame(right_panel, text="Frame Info")
        frame_group.pack(fill=tk.X, pady=5)
        
        self.lbl_fps = ttk.Label(frame_group, text="FPS: 0")
        self.lbl_fps.pack(anchor=tk.W, padx=5)
        
        self.lbl_frame_no = ttk.Label(frame_group, text="Frame: 0")
        self.lbl_frame_no.pack(anchor=tk.W, padx=5)
        
        self.lbl_algo_tick = ttk.Label(frame_group, text="Algo Tick: 0 ms")
        self.lbl_algo_tick.pack(anchor=tk.W, padx=5)
        
        # 補幀狀態
        interp_group = ttk.LabelFrame(right_panel, text="Interpolation")
        interp_group.pack(fill=tk.X, pady=5)
        
        self.lbl_raw_frames = ttk.Label(interp_group, text="Raw Frames: 0")
        self.lbl_raw_frames.pack(anchor=tk.W, padx=5)
        
        self.lbl_interp_frames = ttk.Label(interp_group, text="Interp Frames: 0")
        self.lbl_interp_frames.pack(anchor=tk.W, padx=5)
        
        self.lbl_sequence_ready = ttk.Label(interp_group, text="Sequence: Not Ready")
        self.lbl_sequence_ready.pack(anchor=tk.W, padx=5)
        
        # ReID 結果（修改為三欄：ID, Who, Score）
        reid_group = ttk.LabelFrame(right_panel, text="ReID Results")
        reid_group.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.tree = ttk.Treeview(
            reid_group, 
            columns=("ID", "Who", "Score"), 
            show="headings", 
            height=8
        )
        self.tree.heading("ID", text="ID")
        self.tree.heading("Who", text="Who")
        self.tree.heading("Score", text="Score")
        self.tree.column("ID", width=60)
        self.tree.column("Who", width=100)
        self.tree.column("Score", width=60)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        
        self.txt_vector = tk.Text(reid_group, height=4, width=30, wrap=tk.CHAR)
        self.txt_vector.pack(fill=tk.X, pady=5)
        self.txt_vector.insert(tk.END, "Select an ID to view vector...")
        
        # 動作識別描述區域
        self._setup_action_panel()
    
    def _setup_register_tab(self):
        """建立向量錄入分頁"""
        # 主框架
        main_frame = ttk.Frame(self.tab_register, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === 左側：錄入控制 ===
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # 錄入控制區
        control_group = ttk.LabelFrame(left_frame, text="錄入控制", padding=10)
        control_group.pack(fill=tk.X, pady=5)
        
        # 人名輸入
        name_frame = ttk.Frame(control_group)
        name_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(name_frame, text="人物名稱:").pack(side=tk.LEFT, padx=5)
        self.entry_name = ttk.Entry(name_frame, width=20)
        self.entry_name.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 按鈕區
        btn_frame = ttk.Frame(control_group)
        btn_frame.pack(fill=tk.X, pady=10)
        
        self.btn_start_record = ttk.Button(
            btn_frame, 
            text="🔴 開始錄製", 
            command=self._on_start_recording
        )
        self.btn_start_record.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop_record = ttk.Button(
            btn_frame, 
            text="⏹ 停止錄製", 
            command=self._on_stop_recording,
            state=tk.DISABLED
        )
        self.btn_stop_record.pack(side=tk.LEFT, padx=5)
        
        # 錄製狀態
        status_group = ttk.LabelFrame(left_frame, text="錄製狀態", padding=10)
        status_group.pack(fill=tk.X, pady=5)
        
        self.lbl_record_status = ttk.Label(
            status_group, 
            text="狀態：等待開始", 
            font=("Helvetica", 12)
        )
        self.lbl_record_status.pack(anchor=tk.W, pady=2)
        
        self.lbl_record_name = ttk.Label(status_group, text="錄製對象：-")
        self.lbl_record_name.pack(anchor=tk.W, pady=2)
        
        self.lbl_record_samples = ttk.Label(status_group, text="已錄製樣本：0")
        self.lbl_record_samples.pack(anchor=tk.W, pady=2)
        
        self.lbl_record_time = ttk.Label(status_group, text="錄製時間：0 秒")
        self.lbl_record_time.pack(anchor=tk.W, pady=2)
        
        # 進度條
        self.progress_record = ttk.Progressbar(
            status_group, 
            mode='determinate', 
            maximum=100
        )
        self.progress_record.pack(fill=tk.X, pady=5)
        
        # 說明文字
        help_group = ttk.LabelFrame(left_frame, text="使用說明", padding=10)
        help_group.pack(fill=tk.X, pady=5)
        
        help_text = """1. 確保 WiseEye2 已連接並正在傳送資料
2. 輸入要錄入的人物名稱
3. 點擊「開始錄製」
4. 讓目標人物在鏡頭前活動 5-10 秒
5. 點擊「停止錄製」儲存向量

提示：錄製期間系統會收集多個向量樣本，
並計算平均向量以提高識別準確度。"""
        
        ttk.Label(
            help_group, 
            text=help_text, 
            justify=tk.LEFT,
            wraplength=300
        ).pack(anchor=tk.W)
        
        # === 右側：已註冊人物列表 ===
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        persons_group = ttk.LabelFrame(right_frame, text="已註冊人物", padding=10)
        persons_group.pack(fill=tk.BOTH, expand=True)
        
        # 人物列表
        self.tree_persons = ttk.Treeview(
            persons_group, 
            columns=("Name", "Samples", "Updated"), 
            show="headings", 
            height=15
        )
        self.tree_persons.heading("Name", text="名稱")
        self.tree_persons.heading("Samples", text="樣本數")
        self.tree_persons.heading("Updated", text="更新時間")
        self.tree_persons.column("Name", width=100)
        self.tree_persons.column("Samples", width=60)
        self.tree_persons.column("Updated", width=120)
        self.tree_persons.pack(fill=tk.BOTH, expand=True)
        
        # 捲軸
        scrollbar = ttk.Scrollbar(persons_group, orient=tk.VERTICAL, 
                                  command=self.tree_persons.yview)
        self.tree_persons.configure(yscrollcommand=scrollbar.set)
        
        # 按鈕區
        btn_frame2 = ttk.Frame(persons_group)
        btn_frame2.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            btn_frame2, 
            text="🔄 重新整理", 
            command=self._refresh_persons_list
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame2, 
            text="🗑 刪除選中", 
            command=self._on_delete_person
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame2, 
            text="🗑 清空全部", 
            command=self._on_delete_all
        ).pack(side=tk.LEFT, padx=5)
        
        # 統計資訊
        self.lbl_person_count = ttk.Label(
            persons_group, 
            text="共 0 人已註冊"
        )
        self.lbl_person_count.pack(anchor=tk.W, pady=5)
        
        # 初始化列表
        self._refresh_persons_list()
    
    def _setup_action_panel(self):
        """建立動作識別描述區域（在底部）"""
        action_frame = ttk.LabelFrame(
            self.tab_live, 
            text="🎯 動作識別結果 (Action Recognition)",
            padding=10
        )
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 動作描述文字框
        self.txt_action = tk.Text(
            action_frame, 
            height=8, 
            wrap=tk.WORD,
            font=("Helvetica", 12),
            bg="#f0f0f0",
            fg="#333333",
            padx=10,
            pady=10
        )
        self.txt_action.pack(fill=tk.X)
        
        # 設定初始文字
        self.txt_action.insert(tk.END, "等待連接 WiseEye2 裝置...\n\n")
        self.txt_action.insert(tk.END, "連接後將自動開始骨架動作分析。\n")
        self.txt_action.insert(tk.END, "由於 WiseEye2 的傳輸速度約為 1-2 FPS，\n")
        self.txt_action.insert(tk.END, "系統將自動進行補幀處理以進行動作識別。")
        self.txt_action.config(state=tk.DISABLED)
    
    # ===== 錄入功能 =====
    
    def _on_start_recording(self):
        """開始錄製"""
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("警告", "請輸入人物名稱")
            return
        
        if not self.is_connected:
            messagebox.showwarning("警告", "請先連接 WiseEye2 裝置")
            return
        
        self.is_recording = True
        self.recording_name = name
        self.recording_vectors = []
        self.recording_start_time = time.time()
        
        # 更新 UI
        self.btn_start_record.config(state=tk.DISABLED)
        self.btn_stop_record.config(state=tk.NORMAL)
        self.entry_name.config(state=tk.DISABLED)
        
        self.lbl_record_status.config(text="狀態：錄製中...", foreground="red")
        self.lbl_record_name.config(text=f"錄製對象：{name}")
        self.lbl_record_samples.config(text="已錄製樣本：0")
        
        # 啟動更新計時器
        self._update_record_status()
        
        self.debug_log(f"Started recording for: {name}")
    
    def _on_stop_recording(self):
        """停止錄製"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # 更新 UI
        self.btn_start_record.config(state=tk.NORMAL)
        self.btn_stop_record.config(state=tk.DISABLED)
        self.entry_name.config(state=tk.NORMAL)
        
        # 處理錄製的向量
        if self.recording_vectors:
            # 計算平均向量
            avg_vector = np.mean(self.recording_vectors, axis=0)
            # 正規化
            norm = np.linalg.norm(avg_vector)
            if norm > 0:
                avg_vector = avg_vector / norm
            
            # 儲存到資料庫
            self.reid_db.add_person(self.recording_name, avg_vector)
            
            self.lbl_record_status.config(
                text=f"狀態：錄製完成 ✓", 
                foreground="green"
            )
            messagebox.showinfo(
                "錄製完成", 
                f"已成功錄入 {self.recording_name}\n"
                f"共收集 {len(self.recording_vectors)} 個樣本"
            )
            
            # 重新整理人物列表
            self._refresh_persons_list()
        else:
            self.lbl_record_status.config(
                text="狀態：錄製失敗（無資料）", 
                foreground="orange"
            )
            messagebox.showwarning("警告", "未收集到任何向量資料")
        
        # 清空錄製資料
        self.recording_name = ""
        self.recording_vectors = []
        self.progress_record['value'] = 0
        
        self.debug_log(f"Stopped recording")
    
    def _update_record_status(self):
        """更新錄製狀態"""
        if not self.is_recording:
            return
        
        elapsed = time.time() - self.recording_start_time
        sample_count = len(self.recording_vectors)
        
        self.lbl_record_samples.config(text=f"已錄製樣本：{sample_count}")
        self.lbl_record_time.config(text=f"錄製時間：{elapsed:.1f} 秒")
        
        # 更新進度條（假設目標是 30 個樣本）
        progress = min(sample_count / 30 * 100, 100)
        self.progress_record['value'] = progress
        
        # 繼續更新
        self.root.after(100, self._update_record_status)
    
    def add_recording_vector(self, vector: np.ndarray):
        """
        添加錄製向量（由主程式調用）
        
        Args:
            vector: ReID 向量
        """
        if self.is_recording and vector is not None:
            self.recording_vectors.append(vector.copy())
            self.debug_log(f"Recorded vector #{len(self.recording_vectors)}")
    
    def _refresh_persons_list(self):
        """重新整理已註冊人物列表"""
        # 清空列表
        for item in self.tree_persons.get_children():
            self.tree_persons.delete(item)
        
        # 獲取所有人物
        persons = self.reid_db.get_all_persons()
        
        for person in persons:
            # 格式化時間
            updated_str = time.strftime(
                "%Y-%m-%d %H:%M", 
                time.localtime(person.updated_at)
            )
            
            self.tree_persons.insert(
                "", "end",
                values=(person.name, person.sample_count, updated_str)
            )
        
        self.lbl_person_count.config(text=f"共 {len(persons)} 人已註冊")
    
    def _on_delete_person(self):
        """刪除選中的人物"""
        selected = self.tree_persons.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要刪除的人物")
            return
        
        item = self.tree_persons.item(selected[0])
        name = item['values'][0]
        
        if messagebox.askyesno("確認刪除", f"確定要刪除 {name} 嗎？"):
            self.reid_db.delete_person(name)
            self._refresh_persons_list()
    
    def _on_delete_all(self):
        """刪除所有人物"""
        if messagebox.askyesno("確認刪除", "確定要刪除所有已註冊的人物嗎？\n此操作無法復原！"):
            self.reid_db.delete_all()
            self._refresh_persons_list()
    
    # ===== 事件處理 =====
    
    def _on_canvas_resize(self, event):
        """畫布尺寸變更"""
        self.canvas_w = event.width
        self.canvas_h = event.height
    
    def _on_refresh_ports(self):
        """重新整理串口列表"""
        from .serial_receiver import SerialReceiver
        ports = SerialReceiver.list_ports()
        self.port_combo['values'] = ports
        if ports and not self.port_combo.get():
            self.port_combo.current(0)
    
    def _on_toggle_connection(self):
        """切換連接狀態"""
        if not self.is_connected:
            port = self.port_combo.get()
            if self.on_connect and self.on_connect(port):
                self.is_connected = True
                self.btn_connect.config(text="Disconnect")
                self.status_label.config(text="● 已連接", foreground="green")
                self.update_action_text("已連接到 WiseEye2，正在接收資料...\n等待骨架資料進行動作分析。")
        else:
            if self.on_disconnect:
                self.on_disconnect()
            self.is_connected = False
            self.btn_connect.config(text="Connect")
            self.status_label.config(text="● 未連接", foreground="gray")
            self.update_action_text("已斷開連接。")
            
            # 停止錄製
            if self.is_recording:
                self._on_stop_recording()
    
    def _on_tree_select(self, event):
        """ReID 樹狀選擇事件"""
        selected = self.tree.selection()
        if selected:
            idx = int(selected[0])
            if idx < len(self.current_reid_data):
                vector = self.current_reid_data[idx]
                self.txt_vector.delete("1.0", tk.END)
                self.txt_vector.insert(tk.END, str(vector))
    
    # ===== 公開方法 =====
    
    def set_ports(self, ports: list):
        """設定可用串口列表"""
        self.port_combo['values'] = ports
    
    def update_frame(
        self, 
        frame_data: FrameData,
        skeleton_frame: Optional[SkeletonFrame] = None
    ):
        """
        更新影像顯示
        
        Args:
            frame_data: 幀資料
            skeleton_frame: 骨架幀資料（可選）
        """
        if frame_data.image is None:
            return
        
        try:
            # 更新 FPS
            self._update_fps()
            
            # 處理影像
            mode = self.cached_mode
            
            # 記錄影像尺寸
            self.base_image_shape = frame_data.image.shape
            
            # 如果是補幀模式，由專用計時器處理顯示，這裡只更新資訊
            if mode == "interpolated":
                self._update_info(frame_data, skeleton_frame)
                return
            elif mode == "yolo_only":
                draw_img = np.zeros_like(frame_data.image)
                if skeleton_frame:
                    for person in skeleton_frame.persons:
                        Visualizer.draw_skeleton(
                            draw_img, 
                            person.get_keypoints(use_smoothed=False),
                            person_id=person.person_id,
                            box=person.box,
                            show_confidence=False
                        )
                elif frame_data.keypoints:
                    self._draw_keypoints_legacy(draw_img, frame_data.keypoints)
            else:
                draw_img = frame_data.image.copy()
                if mode != "original" and skeleton_frame:
                    for person in skeleton_frame.persons:
                        Visualizer.draw_skeleton(
                            draw_img, 
                            person.get_keypoints(use_smoothed=False),
                            person_id=person.person_id,
                            box=person.box,
                            show_confidence=False
                        )
                elif mode != "original" and frame_data.keypoints:
                    self._draw_keypoints_legacy(draw_img, frame_data.keypoints)
            
            # 縮放影像
            draw_img = self._resize_image(draw_img)
            
            # 轉換為 RGB
            img_rgb = cv2.cvtColor(draw_img, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(img_rgb)
            
            # 顯示
            self._display_image(pil_image)
            
            # 更新資訊
            self._update_info(frame_data, skeleton_frame)
            
        except Exception as e:
            self.debug_log(f"Frame update error: {e}")
    
    def _draw_keypoints_legacy(self, img: np.ndarray, keypoints: list):
        """使用原始資料繪製骨架（相容性方法）"""
        skeleton = [
            (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
            (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)
        ]
        
        for idx, person in enumerate(keypoints):
            if not person or len(person) < 1:
                continue
            
            box = person[0]
            if len(box) >= 6:
                x, y, w, h, score, target = box[:6]
                x, y, w, h = int(x), int(y), int(w), int(h)
                
                cv2.rectangle(img, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(
                    img, f"ID: {idx} ({int(score)}%)", 
                    (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2
                )
                
                kpts = person[1:]
                parsed_kpts = []
                
                for kp in kpts:
                    if len(kp) == 1 and isinstance(kp[0], list):
                        kp = kp[0]
                    
                    if len(kp) >= 4:
                        kp_x, kp_y, kp_s, kp_t = kp[:4]
                        parsed_kpts.append((int(kp_x), int(kp_y), kp_s))
                        
                        if kp_s > 0:
                            cv2.circle(img, (int(kp_x), int(kp_y)), 3, (0, 255, 255), -1)
                    else:
                        parsed_kpts.append((0, 0, 0))
                
                for p1, p2 in skeleton:
                    if p1 < len(parsed_kpts) and p2 < len(parsed_kpts):
                        kp1, kp2 = parsed_kpts[p1], parsed_kpts[p2]
                        if kp1[2] > 0 and kp2[2] > 0:
                            cv2.line(img, (kp1[0], kp1[1]), (kp2[0], kp2[1]), (0, 255, 0), 2)
    
    def _resize_image(self, img: np.ndarray) -> np.ndarray:
        """縮放影像以適應畫布"""
        if self.canvas_w <= 1 or self.canvas_h <= 1:
            return img
        
        h, w = img.shape[:2]
        scale = min(self.canvas_w / w, self.canvas_h / h)
        nw, nh = int(w * scale), int(h * scale)
        
        if nw > 0 and nh > 0:
            return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        return img
    
    def _display_image(self, pil_image: Image.Image):
        """顯示影像到畫布"""
        self.tk_image = ImageTk.PhotoImage(pil_image)
        
        if self.image_item_id is None:
            self.canvas.delete("all")
            self.image_item_id = self.canvas.create_image(
                self.canvas.winfo_width() // 2,
                self.canvas.winfo_height() // 2,
                image=self.tk_image,
                anchor=tk.CENTER
            )
        else:
            self.canvas.itemconfig(self.image_item_id, image=self.tk_image)
    
    def _update_fps(self):
        """更新 FPS 統計"""
        self.frame_count += 1
        elapsed = time.time() - self.fps_start_time
        
        if elapsed >= 1.0:
            self.current_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start_time = time.time()
            self.lbl_fps.config(text=f"FPS: {self.current_fps:.1f}")
    
    def _update_info(self, data: FrameData, skeleton_frame: Optional[SkeletonFrame] = None):
        """更新資訊面板"""
        # 幀資訊
        self.lbl_frame_no.config(text=f"Frame: {data.frame_no}")
        algo_tick = data.frame_info.get("algo_tick", 0)
        self.lbl_algo_tick.config(text=f"Algo Tick: {algo_tick} ms")
        
        # 裝置資訊
        if data.basic_info:
            self.lbl_device_id.config(text=f"ID: {data.basic_info.get('device_id', '-')}")
            self.lbl_model_name.config(text=f"Model: {data.basic_info.get('name', '-')}")
            self.lbl_version.config(text=f"Ver: {data.basic_info.get('ver', '-')}")
        
        # ReID 結果（節流更新）
        if time.time() - self.last_reid_update >= 0.5:
            self._update_reid_table(data.reid_results, skeleton_frame)
            self.last_reid_update = time.time()
    
    def _update_reid_table(self, reid_results: list, skeleton_frame: Optional[SkeletonFrame] = None):
        """更新 ReID 表格（含人物識別）"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.current_reid_data = reid_results
        
        # 獲取有效的人物 ID 集合
        valid_ids = set()
        if skeleton_frame:
            for p in skeleton_frame.persons:
                valid_ids.add(p.person_id)
        
        limit = min(len(reid_results), 20)
        for i in range(limit):
            # 如果有骨架幀資訊，則過濾掉無效的人物（例如關鍵點過少）
            if skeleton_frame is not None and i not in valid_ids:
                continue
            
            vector = reid_results[i] if i < len(reid_results) else None
            
            # 識別人物
            who = ""
            score = ""
            if vector is not None and isinstance(vector, (list, np.ndarray)):
                try:
                    vec_np = np.array(vector, dtype=np.float32)
                    name, sim_score = self.reid_db.identify(vec_np)
                    if name:
                        who = name
                        score = f"{sim_score:.2f}"
                except Exception:
                    pass
            
            self.tree.insert(
                "", "end", 
                iid=str(i), 
                values=(f"Person {i}", who, score)
            )
            
            # 如果正在錄製，添加向量
            if self.is_recording and vector is not None:
                try:
                    vec_np = np.array(vector, dtype=np.float32)
                    self.add_recording_vector(vec_np)
                except Exception:
                    pass
    
    def update_interpolation_status(self, status: Dict[str, Any]):
        """
        更新補幀狀態顯示
        
        Args:
            status: 狀態字典
        """
        self.lbl_raw_frames.config(text=f"Raw Frames: {status.get('raw_frames', 0)}")
        self.lbl_interp_frames.config(text=f"Interp Frames: {status.get('interpolated_frames', 0)}")
        
        if status.get('sequence_ready', False):
            self.lbl_sequence_ready.config(text="Sequence: ✓ Ready", foreground="green")
        else:
            self.lbl_sequence_ready.config(text="Sequence: Buffering...", foreground="orange")
    
    def update_interpolated_frames(self, skeleton_frames: list):
        """
        更新補幀骨架列表（用於 Interpolated 模式流暢播放）
        
        Args:
            skeleton_frames: 補幀後的骨架幀列表
        """
        if skeleton_frames:
            self.skeleton_player.set_buffer(list(skeleton_frames))
            if self.interp_timer_id is None and self.cached_mode == "interpolated":
                self._start_interpolated_playback()
    
    def _start_interpolated_playback(self):
        """開始播放補幀動畫"""
        if self.interp_timer_id is not None:
            return
        self.skeleton_player.reset()
        self._play_next_interpolated_frame()
    
    def _stop_interpolated_playback(self):
        """停止播放補幀動畫"""
        if self.interp_timer_id is not None:
            self.root.after_cancel(self.interp_timer_id)
            self.interp_timer_id = None
    
    def _play_next_interpolated_frame(self):
        """播放下一個補幀"""
        if self.cached_mode != "interpolated":
            self.interp_timer_id = None
            return
        
        frame = self.skeleton_player.get_next_frame()
        
        if not frame:
            self.interp_timer_id = self.root.after(67, self._play_next_interpolated_frame)
            return
        
        try:
            h, w = self.base_image_shape[:2]
            draw_img = np.zeros((h, w, 3), dtype=np.uint8)
            
            for person in frame.persons:
                Visualizer.draw_skeleton(
                    draw_img, 
                    person.get_keypoints(use_smoothed=True),
                    person_id=person.person_id,
                    box=person.box,
                    show_confidence=False
                )
            
            draw_img = self._resize_image(draw_img)
            
            img_rgb = cv2.cvtColor(draw_img, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(img_rgb)
            
            self._display_image(pil_image)
            
        except Exception as e:
            if config.debug:
                print(f"[GUI] Interpolated playback error: {e}")
        
        self.interp_timer_id = self.root.after(33, self._play_next_interpolated_frame)
    
    def _on_mode_change(self, *args):
        """顯示模式變更"""
        self.cached_mode = self.view_mode.get()
        
        if self.cached_mode == "interpolated":
            self._start_interpolated_playback()
        else:
            self._stop_interpolated_playback()
    
    def update_action_text(self, text: str):
        """
        更新動作識別描述文字
        
        Args:
            text: 描述文字
        """
        self.txt_action.config(state=tk.NORMAL)
        self.txt_action.delete("1.0", tk.END)
        self.txt_action.insert(tk.END, text)
        self.txt_action.config(state=tk.DISABLED)
    
    def schedule(self, callback: Callable, delay_ms: int = 0):
        """
        排程在主執行緒執行
        
        Args:
            callback: 回調函數
            delay_ms: 延遲毫秒數
        """
        self.root.after(delay_ms, callback)
    
    def run(self):
        """啟動主迴圈"""
        self.root.mainloop()
