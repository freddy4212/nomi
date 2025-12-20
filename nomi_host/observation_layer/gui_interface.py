"""
gui_interface.py - 接收端圖形介面模組

這個模組負責：
- 建立 Tkinter 圖形介面
- 分頁結構：主頁（即時辨識）和錄入頁（向量錄入）
- 顯示影像和骨架
- 處理使用者互動
- 加入開始/停止按鈕控制

介面佈局與 we_mma_2 相同，但移除串口相關功能
"""

import os
import sys
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

# 確保可以導入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observation_layer.config import config
from observation_layer.modules.network.receiver import FrameData
from observation_layer.modules.skeleton.processor import SkeletonFrame
from observation_layer.modules.visualization import SkeletonPlayer, Visualizer


class ReceiverGUIInterface:
    """接收端圖形介面類"""
    
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
        self.is_running = False
        self.is_connected = False
        self.view_mode = tk.StringVar(value="overlay")
        self.cached_mode = "overlay"
        self.canvas_w = config.gui.canvas_width
        self.canvas_h = config.gui.canvas_height
        
        # 顯示相關
        self.tk_image = None
        self.image_item_id = None
        
        # 補幀播放器
        self.skeleton_player = SkeletonPlayer(None)
        self.interp_timer_id = None
        self.base_image_shape = (480, 640, 3)
        
        # FPS 統計
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        
        # ReID 資料快取
        self.current_reid_data = []
        self.last_reid_update = 0.0
        
        # ReID 資料庫 (已棄用 SQLite，改用 memory_bridge)
        self.memory_bridge = None
        
        # 錄製狀態
        self.is_recording = False
        self.recording_name = ""
        self.recording_vectors = []
        self.recording_start_time = 0.0
        
        # 回調函數
        self.on_start: Optional[Callable[[], bool]] = None
        self.on_stop: Optional[Callable[[], None]] = None
        
        # 建立介面
        self._setup_ui()
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[ReceiverGUI][{time.time():.3f}] {msg}")
    
    def _setup_ui(self):
        """建立 UI 元件"""
        self._setup_top_bar()
        self._setup_notebook()
    
    def _setup_top_bar(self):
        """建立頂部工具列"""
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill=tk.X)
        
        # 網路連接資訊
        ttk.Label(top_frame, text="Server:").pack(side=tk.LEFT, padx=5)
        self.lbl_server = ttk.Label(
            top_frame, 
            text=f"{config.network.host}:{config.network.port}",
            foreground="gray"
        )
        self.lbl_server.pack(side=tk.LEFT, padx=5)
        
        # 開始/停止按鈕
        self.btn_start = ttk.Button(
            top_frame, 
            text="▶ 開始接收", 
            command=self._on_toggle_running
        )
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
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
        
        # 記憶層狀態指示燈（在右側）
        self.memory_status_label = ttk.Label(
            top_frame, 
            text="🗄 記憶層: --", 
            foreground="gray"
        )
        self.memory_status_label.pack(side=tk.RIGHT, padx=5)
        
        # 分隔線
        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        # 網路連線狀態指示燈
        self.status_label = ttk.Label(top_frame, text="● 已停止", foreground="gray")
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
        
        # 綁定分頁切換事件：切換到向量錄入時自動刷新已註冊人物列表
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _setup_live_tab(self):
        """建立即時辨識分頁"""
        # 使用 PanedWindow 分隔上方（影像+右側面板）和下方（動作識別結果）
        main_pane = ttk.PanedWindow(self.tab_live, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # === 上方區域：影像 + 右側面板 ===
        top_frame = ttk.Frame(main_pane)
        main_pane.add(top_frame, weight=3)
        
        # 左側：影像畫布
        self.canvas_frame = ttk.Frame(top_frame, borderwidth=2, relief="sunken")
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        
        # 右側：資訊面板
        right_panel = ttk.Frame(top_frame, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        right_panel.pack_propagate(False)
        
        # 裝置資訊
        device_group = ttk.LabelFrame(right_panel, text="Device Info", padding=10)
        device_group.pack(fill=tk.X, pady=5)
        
        self.lbl_device_id = ttk.Label(device_group, text="ID: -")
        self.lbl_device_id.pack(anchor=tk.W, padx=5)
        
        self.lbl_model_name = ttk.Label(device_group, text="Model: -")
        self.lbl_model_name.pack(anchor=tk.W, padx=5)
        
        self.lbl_version = ttk.Label(device_group, text="Ver: -")
        self.lbl_version.pack(anchor=tk.W, padx=5)
        
        # 幀資訊
        frame_group = ttk.LabelFrame(right_panel, text="Frame Info", padding=10)
        frame_group.pack(fill=tk.X, pady=5)
        
        self.lbl_fps = ttk.Label(frame_group, text="FPS: 0")
        self.lbl_fps.pack(anchor=tk.W, padx=5)
        
        self.lbl_frame_no = ttk.Label(frame_group, text="Frame: 0")
        self.lbl_frame_no.pack(anchor=tk.W, padx=5)
        
        self.lbl_algo_tick = ttk.Label(frame_group, text="Algo Tick: 0 ms")
        self.lbl_algo_tick.pack(anchor=tk.W, padx=5)
        
        # 保留相容性變數（隱藏）
        self.lbl_conn_status = ttk.Label(frame_group)
        self.lbl_sender_info = ttk.Label(frame_group)
        
        # 補幀狀態
        interp_group = ttk.LabelFrame(right_panel, text="Interpolation", padding=10)
        interp_group.pack(fill=tk.X, pady=5)
        
        self.lbl_raw_frames = ttk.Label(interp_group, text="Raw Frames: 0")
        self.lbl_raw_frames.pack(anchor=tk.W, padx=5)
        
        self.lbl_interp_frames = ttk.Label(interp_group, text="Interp Frames: 0")
        self.lbl_interp_frames.pack(anchor=tk.W, padx=5)
        
        self.lbl_sequence_ready = ttk.Label(interp_group, text="Sequence: Not Ready")
        self.lbl_sequence_ready.pack(anchor=tk.W, padx=5)
        
        # 保留動作識別相關的變數（相容性，但不顯示）
        self.action_var = tk.StringVar(value="等待中...")
        self.confidence_var = tk.StringVar(value="信心度: 0%")
        self.skeleton_status_var = tk.StringVar(value="骨架: 等待偵測...")
        self.motion_status_var = tk.StringVar(value="動態: -")
        self.top5_var = tk.StringVar(value="等待識別...")
        
        # 建立一個隱藏的多人識別文字區域（相容性）
        self.txt_multi_person = tk.Text(right_panel, height=1)
        
        # ReID 結果
        reid_group = ttk.LabelFrame(right_panel, text="ReID Results", padding=5)
        reid_group.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.tree = ttk.Treeview(
            reid_group, 
            columns=("ID", "Who", "Score"), 
            show="headings", 
            height=6
        )
        self.tree.heading("ID", text="ID")
        self.tree.heading("Who", text="Who")
        self.tree.heading("Score", text="Score")
        self.tree.column("ID", width=50)
        self.tree.column("Who", width=120)
        self.tree.column("Score", width=70)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        
        self.txt_vector = tk.Text(reid_group, height=3, width=30, wrap=tk.CHAR)
        self.txt_vector.pack(fill=tk.X, pady=2)
        self.txt_vector.insert(tk.END, "Select an ID to view vector...")
        
        # === 下方區域：動作識別結果（可拖曳調整大小）===
        bottom_frame = ttk.LabelFrame(
            main_pane, 
            text="🎯 動作識別結果 (Action Recognition)",
            padding=5
        )
        main_pane.add(bottom_frame, weight=1)
        
        # 動作描述文字框
        text_frame = ttk.Frame(bottom_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.txt_action = tk.Text(
            text_frame, 
            wrap=tk.WORD,
            font=("Helvetica", 11),
            bg="#f5f5f5",
            fg="#333333",
            padx=8,
            pady=8
        )
        self.txt_action.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滾動條
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.txt_action.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_action.config(yscrollcommand=scrollbar.set)
        
        # 設定初始文字
        self.txt_action.insert(tk.END, "等待開始接收...\n")
        self.txt_action.insert(tk.END, "點擊「開始接收」按鈕後，將顯示即時分析日誌。\n")
        self.txt_action.insert(tk.END, "\n提示：拖曳上方橫桿可調整此區域大小。")
        self.txt_action.config(state=tk.DISABLED)
    
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
        
        help_text = """1. 確保已開始接收並有資料傳入
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
    
    # ===== 錄入功能 =====
    
    def _on_start_recording(self):
        """開始錄製"""
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("警告", "請輸入人物名稱")
            return
        
        if not self.is_running:
            messagebox.showwarning("警告", "請先點擊「開始接收」")
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
            avg_vector = np.mean(self.recording_vectors, axis=0)
            norm = np.linalg.norm(avg_vector)
            if norm > 0:
                avg_vector = avg_vector / norm
            
            if self.memory_bridge:
                self.memory_bridge.register_member(self.recording_name, avg_vector)
            
            self.lbl_record_status.config(
                text=f"狀態：錄製完成 ✓", 
                foreground="green"
            )
            messagebox.showinfo(
                "錄製完成", 
                f"已成功錄入 {self.recording_name}\n"
                f"共收集 {len(self.recording_vectors)} 個樣本"
            )
            
            self._refresh_persons_list()
        else:
            self.lbl_record_status.config(
                text="狀態：錄製失敗（無資料）", 
                foreground="orange"
            )
            messagebox.showwarning("警告", "未收集到任何向量資料")
        
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
        
        progress = min(sample_count / 30 * 100, 100)
        self.progress_record['value'] = progress
        
        self.root.after(100, self._update_record_status)
    
    def add_recording_vector(self, vector: np.ndarray):
        """添加錄製向量"""
        if self.is_recording and vector is not None:
            self.recording_vectors.append(vector.copy())
            self.debug_log(f"Recorded vector #{len(self.recording_vectors)}")
    
    def _refresh_persons_list(self):
        """重新整理已註冊人物列表"""
        for item in self.tree_persons.get_children():
            self.tree_persons.delete(item)
        
        if not self.memory_bridge:
            return
            
        members = self.memory_bridge.get_all_members()
        
        for member in members:
            updated_at = member.get('updated_at')
            if isinstance(updated_at, datetime):
                updated_str = updated_at.strftime("%Y-%m-%d %H:%M")
            else:
                updated_str = "-"
            
            self.tree_persons.insert(
                "", "end",
                values=(member['name'], member.get('sample_count', 1), updated_str)
            )
        
        self.lbl_person_count.config(text=f"共 {len(members)} 人已註冊")
    
    def _on_delete_person(self):
        """刪除選中的人物"""
        selected = self.tree_persons.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要刪除的人物")
            return
        
        item = self.tree_persons.item(selected[0])
        name = item['values'][0]
        
        if messagebox.askyesno("確認刪除", f"確定要刪除 {name} 嗎？"):
            if self.memory_bridge:
                self.memory_bridge.delete_member(name)
            self._refresh_persons_list()
    
    def _on_delete_all(self):
        """刪除所有人物"""
        if messagebox.askyesno("確認刪除", "確定要刪除所有已註冊的人物嗎？\n此操作無法復原！"):
            if self.memory_bridge:
                self.memory_bridge.delete_all_members()
            self._refresh_persons_list()
    
    # ===== 事件處理 =====
    
    def _on_tab_changed(self, event):
        """分頁切換事件：切換到向量錄入分頁時自動刷新已註冊人物列表"""
        selected_tab = self.notebook.index(self.notebook.select())
        # 分頁索引 1 = 向量錄入分頁
        if selected_tab == 1:
            self._refresh_persons_list()
    
    def _on_canvas_resize(self, event):
        """畫布尺寸變更"""
        self.canvas_w = event.width
        self.canvas_h = event.height
    
    def _on_toggle_running(self):
        """切換運行狀態"""
        if not self.is_running:
            if self.on_start and self.on_start():
                self.is_running = True
                self.btn_start.config(text="⏹ 停止接收")
                self.status_label.config(text="● 接收中...", foreground="orange")
                self.update_action_text("正在連接發射端...\n等待資料...")
        else:
            if self.on_stop:
                self.on_stop()
            self.is_running = False
            self.is_connected = False
            self.btn_start.config(text="▶ 開始接收")
            self.status_label.config(text="● 已停止", foreground="gray")
            self.lbl_conn_status.config(text="Status: 未連接")
            self.update_action_text("已停止接收。")
            
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
    
    def update_connection_status(self, connected: bool, status_info: dict = None):
        """更新連接狀態（含詳細資訊）"""
        self.is_connected = connected
        
        if connected:
            self.status_label.config(text="● 已連接", foreground="green")
            if status_info:
                client = status_info.get("client_addr")
                if client:
                    self.lbl_conn_status.config(
                        text=f"Status: ✓ {client[0]}:{client[1]}", 
                        foreground="green"
                    )
                else:
                    self.lbl_conn_status.config(text="Status: ✓ 已連接", foreground="green")
            else:
                self.lbl_conn_status.config(text="Status: ✓ 已連接", foreground="green")
        else:
            reconnect_count = status_info.get("reconnect_count", 0) if status_info else 0
            if reconnect_count > 0:
                self.status_label.config(text=f"● 重連中 ({reconnect_count})", foreground="orange")
                self.lbl_conn_status.config(
                    text=f"Status: 等待連線... (重連 {reconnect_count} 次)", 
                    foreground="orange"
                )
            else:
                self.status_label.config(text="● 等待連線", foreground="orange")
                self.lbl_conn_status.config(text="Status: 等待連線...", foreground="orange")
    
    def update_memory_status(self, enabled: bool, connected: bool, events_sent: int = 0, db_type: str = "PostgreSQL", error: str = None):
        """
        更新記憶層連線狀態
        
        Args:
            enabled: 記憶層模組是否可用
            connected: 資料庫是否已連線
            events_sent: 已發送的事件數
            db_type: 資料庫類型
            error: 連線錯誤訊息
        """
        if not enabled:
            self.memory_status_label.config(
                text="🗄 記憶層: 未安裝", 
                foreground="gray"
            )
        elif connected:
            self.memory_status_label.config(
                text=f"🗄 {db_type} ✓ ({events_sent})", 
                foreground="green"
            )
        elif error:
            # 連線失敗
            short_error = error[:20] + "..." if len(error) > 20 else error
            self.memory_status_label.config(
                text=f"🗄 {db_type}: ✗ 未連線", 
                foreground="red"
            )
        else:
            self.memory_status_label.config(
                text=f"🗄 {db_type}: 待機", 
                foreground="orange"
            )
    
    # ===== 公開方法 =====
    
    def update_frame(
        self, 
        frame_data: FrameData,
        skeleton_frame: Optional[SkeletonFrame] = None
    ):
        """更新影像顯示"""
        if frame_data.image is None:
            return
        
        try:
            self._update_fps()
            mode = self.cached_mode
            self.base_image_shape = frame_data.image.shape
            
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
            
            draw_img = self._resize_image(draw_img)
            img_rgb = cv2.cvtColor(draw_img, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(img_rgb)
            self._display_image(pil_image)
            self._update_info(frame_data, skeleton_frame)
            
        except Exception as e:
            self.debug_log(f"Frame update error: {e}")
    
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
        self.lbl_frame_no.config(text=f"Frame: {data.frame_no}")
        algo_tick = data.frame_info.get("algo_tick", 0)
        self.lbl_algo_tick.config(text=f"Algo Tick: {algo_tick} ms")
        
        if data.basic_info:
            self.lbl_device_id.config(text=f"ID: {data.basic_info.get('device_id', '-')}")
            self.lbl_model_name.config(text=f"Model: {data.basic_info.get('name', '-')}")
            self.lbl_version.config(text=f"Ver: {data.basic_info.get('ver', '-')}")
        
        # 更新發送源資訊
        source = data.frame_info.get("source", "-")
        self.lbl_sender_info.config(text=f"Source: {source}")
        
        if time.time() - self.last_reid_update >= 0.5:
            self._update_reid_table(data.reid_results, skeleton_frame)
            self.last_reid_update = time.time()
    
    def _update_reid_table(self, reid_results: list, skeleton_frame: Optional[SkeletonFrame] = None):
        """更新 ReID 表格"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.current_reid_data = reid_results
        
        # 如果有骨架幀，直接使用每個人物的 reid_vector
        if skeleton_frame and skeleton_frame.persons:
            for person in skeleton_frame.persons:
                person_id = person.person_id
                vector = person.reid_vector
                
                who = ""
                score = ""
                if vector is not None and isinstance(vector, (list, np.ndarray)):
                    try:
                        vec_np = np.array(vector, dtype=np.float32)
                        if self.memory_bridge:
                            # 使用記憶層進行識別 (餘弦距離閾值 0.4 對應相似度 0.6)
                            result = self.memory_bridge.find_nearest_member(vec_np, threshold=0.4)
                            if result:
                                who = result['name']
                                sim_score = 1.0 - result['distance']
                                score = f"{sim_score:.2f}"
                    except Exception:
                        pass
                
                self.tree.insert(
                    "", "end", 
                    iid=str(person_id), 
                    values=(f"Person {person_id}", who, score)
                )
                
                if self.is_recording and vector is not None:
                    try:
                        vec_np = np.array(vector, dtype=np.float32)
                        self.add_recording_vector(vec_np)
                    except Exception:
                        pass
        else:
            # 後備方案：沒有骨架幀時使用索引遍歷 reid_results
            limit = min(len(reid_results), 20)
            for i in range(limit):
                vector = reid_results[i] if i < len(reid_results) else None
                
                who = ""
                score = ""
                if vector is not None and isinstance(vector, (list, np.ndarray)):
                    try:
                        vec_np = np.array(vector, dtype=np.float32)
                        if self.memory_bridge:
                            result = self.memory_bridge.find_nearest_member(vec_np, threshold=0.4)
                            if result:
                                who = result['name']
                                sim_score = 1.0 - result['distance']
                                score = f"{sim_score:.2f}"
                    except Exception:
                        pass
                
                self.tree.insert(
                    "", "end", 
                    iid=str(i), 
                    values=(f"Person {i}", who, score)
                )
                
                if self.is_recording and vector is not None:
                    try:
                        vec_np = np.array(vector, dtype=np.float32)
                        self.add_recording_vector(vec_np)
                    except Exception:
                        pass
    
    def update_interpolation_status(self, status: Dict[str, Any]):
        """更新補幀狀態顯示"""
        self.lbl_raw_frames.config(text=f"Raw Frames: {status.get('raw_frames', 0)}")
        
        # 顯示播放緩衝區狀態（更有意義）
        player_status = self.skeleton_player.get_buffer_status()
        remaining = player_status.get("remaining", 0)
        buffer_size = player_status.get("buffer_size", 0)
        self.lbl_interp_frames.config(text=f"Buffer: {remaining}/{buffer_size}")
        
        if status.get('sequence_ready', False):
            self.lbl_sequence_ready.config(text="Sequence: ✓ Ready", foreground="green")
        else:
            self.lbl_sequence_ready.config(text="Sequence: Buffering...", foreground="orange")
    
    def update_interpolated_frames(self, skeleton_frames: list):
        """更新補幀骨架列表（追加模式）"""
        if skeleton_frames:
            # 使用追加模式，而非覆蓋
            self.skeleton_player.set_buffer(skeleton_frames)
            if self.interp_timer_id is None and self.cached_mode == "interpolated":
                self._start_interpolated_playback()
    
    def _start_interpolated_playback(self):
        """開始播放補幀動畫"""
        if self.interp_timer_id is not None:
            return
        # 不重置播放器，繼續從當前位置播放
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
            # 沒有幀可播放，等待新幀
            self.interp_timer_id = self.root.after(33, self._play_next_interpolated_frame)
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
                print(f"[ReceiverGUI] Interpolated playback error: {e}")
        
        # 根據緩衝區狀態動態調整播放間隔
        buffer_status = self.skeleton_player.get_buffer_status()
        remaining = buffer_status.get("remaining", 0)
        
        if remaining <= 2:
            # 緩衝區快空了，減慢播放速度等待新幀
            interval = 50  # ~20 FPS
        elif remaining <= 5:
            interval = 40  # ~25 FPS
        elif remaining > 30:
            # 緩衝區太滿，加快消耗
            interval = 25  # ~40 FPS
        else:
            interval = 33  # ~30 FPS
        
        self.interp_timer_id = self.root.after(interval, self._play_next_interpolated_frame)
    
    def _on_mode_change(self, *args):
        """顯示模式變更"""
        self.cached_mode = self.view_mode.get()
        
        if self.cached_mode == "interpolated":
            self._start_interpolated_playback()
        else:
            self._stop_interpolated_playback()
    
    def update_action_text(self, text: str):
        """更新動作識別描述文字"""
        self.txt_action.config(state=tk.NORMAL)
        self.txt_action.delete("1.0", tk.END)
        self.txt_action.insert(tk.END, text)
        self.txt_action.config(state=tk.DISABLED)
    
    def update_action_result(
        self, 
        action: str = "等待中...",
        confidence: float = 0.0,
        top5: List[tuple] = None,
        skeleton_status: str = "等待偵測...",
        motion_status: str = "-",
        multi_person_info: List[Dict] = None
    ):
        """
        更新動作識別結果顯示（仿 webcam_action_test 風格）
        
        Args:
            action: 當前識別的動作名稱
            confidence: 識別信心度 (0~1)
            top5: Top 5 預測結果 [(label, score), ...]
            skeleton_status: 骨架可見性狀態文字
            motion_status: 動作強度狀態文字
            multi_person_info: 多人識別結果 [{'id': 0, 'action': '...', 'confidence': 0.8, 'top5': [...]}, ...]
        """
        # 更新主要動作顯示
        self.action_var.set(action)
        self.confidence_var.set(f"信心度: {confidence:.1%}")
        self.skeleton_status_var.set(f"骨架: {skeleton_status}")
        self.motion_status_var.set(f"動態: {motion_status}")
        
        # 更新 Top 5
        if top5:
            top5_text = "\n".join([f"{i+1}. {label}: {score:.1%}" 
                                   for i, (label, score) in enumerate(top5[:5])])
            self.top5_var.set(top5_text)
        else:
            self.top5_var.set("等待識別...")
        
        # 更新多人識別結果
        self._update_multi_person_display(multi_person_info)
    
    def _update_multi_person_display(self, multi_person_info: List[Dict] = None):
        """更新多人識別結果顯示"""
        self.txt_multi_person.config(state=tk.NORMAL)
        self.txt_multi_person.delete("1.0", tk.END)
        
        if not multi_person_info:
            self.txt_multi_person.insert(tk.END, "單人模式或無偵測到人\n")
            self.txt_multi_person.config(state=tk.DISABLED)
            return
        
        for person_info in multi_person_info:
            person_id = person_info.get('id', 0)
            action = person_info.get('action', '未知')
            confidence = person_info.get('confidence', 0.0)
            reid_name = person_info.get('reid_name', '-')
            
            # 格式化顯示
            line = f"👤 Person #{person_id}"
            if reid_name and reid_name != '-':
                line += f" ({reid_name})"
            line += f"\n   動作: {action} ({confidence:.1%})\n"
            
            # 顯示該人的 Top 3
            top3 = person_info.get('top5', [])[:3]
            if top3:
                for i, (label, score) in enumerate(top3):
                    line += f"   {i+1}. {label}: {score:.1%}\n"
            
            line += "\n"
            self.txt_multi_person.insert(tk.END, line)
        
        self.txt_multi_person.config(state=tk.DISABLED)

    def schedule(self, callback, delay_ms: int = 0):
        """排程在主執行緒執行"""
        self.root.after(delay_ms, callback)
    
    def run(self):
        """啟動主迴圈"""
        self.root.mainloop()
