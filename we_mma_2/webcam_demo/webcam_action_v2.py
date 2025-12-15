#!/usr/bin/env python3
"""
webcam_action_v2.py - 使用電腦攝像頭測試 MMAction2 動作辨識（改進版 - 使用共享邏輯）

功能：
- 使用電腦攝像頭即時捕捉影像
- 使用 YOLO-Pose 提取骨架關鍵點
- 使用共享的 SkeletonProcessor 進行濾波、補幀
- 使用共享的 ActionRecognizer 進行動作識別（包含時序濾波和簡化邏輯）
- 保留原有的 GUI 介面與功能

使用方式：
    python -m we_mma_2.webcam_action_v2
"""

# 處理導入路徑
import os
import sys
import threading
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Queue
from tkinter import ttk
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

if __name__ == "__main__" or __package__ is None:
    # Add project root to sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from we_mma_2.action_recognizer import ActionRecognizerAsync, ActionResult
    from we_mma_2.config import config
    from we_mma_2.serial_receiver import FrameData
    from we_mma_2.skeleton_processor import SkeletonFrame, SkeletonProcessor
    from we_mma_2.visualizer import Visualizer
else:
    from ..action_recognizer import ActionRecognizerAsync, ActionResult
    from ..config import config
    from ..serial_receiver import FrameData
    from ..skeleton_processor import SkeletonFrame, SkeletonProcessor
    from ..visualizer import Visualizer


# ============================================================
# 視圖模式
# ============================================================
class ViewMode(Enum):
    ORIGINAL = "Original"          # 只顯示原始影像
    OVERLAY = "Overlay"            # 影像 + 骨架疊加
    YOLO_ONLY = "YOLO Only"        # 黑底 + 原始骨架
    INTERPOLATED = "Interpolated"  # 黑底 + 平滑骨架


# ============================================================
# 模型類型
# ============================================================
class ModelType(Enum):
    POSEC3D = "PoseC3D"
    STGCNPP = "ST-GCN++"


# ============================================================
# 配置 (保留本地 Config 結構以相容 GUI，但部分值映射到全局 config)
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@dataclass
class LocalConfig:
    # 攝像頭設定
    camera_id: int = 0
    camera_width: int = 640
    camera_height: int = 480
    
    # FPS 設定
    default_fps: float = 2.0
    min_fps: float = 0.5
    max_fps: float = 30.0
    
    # YOLO Pose 設定
    yolo_model: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n-pose.pt")
    yolo_conf: float = 0.5
    
    # MMAction2 設定 (路徑)
    mmaction_config: str = os.path.join(PROJECT_ROOT, "we_mma_2/mmaction2/configs/skeleton/posec3d/slowonly_r50_8xb16-u48-240e_ntu60-xsub-keypoint.py")
    mmaction_checkpoint: str = os.path.join(PROJECT_ROOT, "we_mma_2/mmaction2/checkpoints/slowonly_r50_8xb16-u48-240e_ntu60-xsub-keypoint_20220815-38db104b.pth")
    
    stgcnpp_config: str = os.path.join(PROJECT_ROOT, "we_mma_2/mmaction2/configs/skeleton/stgcnpp/stgcnpp_8xb16-joint-u100-80e_ntu60-xsub-keypoint-2d.py")
    stgcnpp_checkpoint: str = os.path.join(PROJECT_ROOT, "we_mma_2/mmaction2/checkpoints/stgcnpp_ntu60_joint.pth")

local_config = LocalConfig()

# 更新全局配置以匹配本地設定
if hasattr(config, 'webcam'):
    local_config.camera_id = config.webcam.camera_id
    local_config.camera_width = config.webcam.width
    local_config.camera_height = config.webcam.height
    local_config.yolo_model = config.webcam.yolo_model


# ============================================================
# 姿態提取器 (保留 YOLO 封裝)
# ============================================================
class PoseExtractor:
    def __init__(self):
        self.model = None
        self.ready = False
        self._init_model()
    
    def _init_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(local_config.yolo_model)
            self.ready = True
            print(f"✓ 已載入 YOLO-Pose: {local_config.yolo_model}")
        except Exception as e:
            print(f"⚠ YOLO-Pose 載入失敗: {e}")
    
    def extract(self, frame: np.ndarray) -> List[List[Any]]:
        """
        執行 YOLO 並返回 FrameData 格式的關鍵點列表
        格式: [ [box_data, kpt1, kpt2...], ... ]
        """
        if not self.ready:
            return []
        try:
            results = self.model(frame, verbose=False, conf=local_config.yolo_conf)
            formatted_persons = []
            
            for r in results:
                if r.boxes is None or r.keypoints is None:
                    continue
                    
                boxes = r.boxes.data.cpu().numpy()
                kpts = r.keypoints.data.cpu().numpy()
                
                for i in range(len(boxes)):
                    x1, y1, x2, y2, conf, cls = boxes[i]
                    w, h = x2 - x1, y2 - y1
                    box_data = [x1, y1, w, h, conf, 0]
                    
                    person_kpts = kpts[i]
                    kpt_list = []
                    for k in person_kpts:
                        # [x, y, conf, target]
                        kpt_list.append([k[0], k[1], k[2], 0])
                    
                    person_data = [box_data] + kpt_list
                    formatted_persons.append(person_data)
            
            return formatted_persons
        except Exception as e:
            print(f"YOLO Error: {e}")
            return []


# ============================================================
# 主應用程式
# ============================================================
class WebcamActionApp:
    def __init__(self):
        self.running = False
        self.current_fps = local_config.default_fps
        self.last_capture_time = 0
        self.view_mode = ViewMode.OVERLAY
        self.model_type = ModelType.POSEC3D
        
        print("=" * 50)
        print("  Webcam Action Recognition Test v2 (Unified Logic)")
        print("  使用 YOLO-Pose + MMAction2 (PoseC3D / ST-GCN++)")
        print("=" * 50)
        print("\n正在初始化...")
        
        # 初始化共享模組
        self.pose_extractor = PoseExtractor()
        self.skeleton_processor = SkeletonProcessor()
        self.action_recognizer = ActionRecognizerAsync()
        
        # 狀態變數
        self.current_action = "等待中..."
        self.current_confidence = 0.0
        self.stable_action = "等待中..."
        self.stable_confidence = 0.0
        self.top5_predictions = []
        self.skeleton_quality = (False, 0.0, 0)
        self.motion_magnitude = 0.0
        
        # 攝像頭
        self.cap = None
        self.current_camera_id = local_config.camera_id
        self.available_cameras = []
        
        # 顯示相關
        self.display_frame = None
        self.display_output = None  # 用於儲存渲染後的畫面 (符合採樣率)
        self.current_skeleton_frame = None
        self.frame_count = 0
        
        # 補幀播放相關
        self.interpolated_buffer = []
        self.interp_play_index = 0
        
        # GUI 變數
        self.root = None
        self.canvas = None
        self.photo = None
    
    def detect_cameras(self, max_cameras: int = 10) -> List[dict]:
        """偵測可用的攝像頭"""
        cameras = []
        current_cap = self.cap
        if current_cap is not None:
            current_cap.release()
            self.cap = None
            time.sleep(0.2)
        
        for i in range(max_cameras):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        cameras.append({
                            'id': i,
                            'name': f"Camera {i}",
                            'resolution': f"{w}x{h}"
                        })
                    cap.release()
                    time.sleep(0.1)
            except Exception:
                pass
        
        if current_cap is not None:
            self.start_camera(getattr(self, 'current_camera_id', 0))
        
        return cameras
    
    def start_camera(self, camera_id: int = None) -> bool:
        if camera_id is None:
            camera_id = local_config.camera_id
        
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            print(f"⚠ 無法開啟攝像頭 {camera_id}")
            return False
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, local_config.camera_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, local_config.camera_height)
        self.current_camera_id = camera_id
        
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"✓ 攝像頭 {camera_id} 已開啟: {actual_w}x{actual_h}")
        return True
    
    def switch_camera(self, camera_id: int):
        if camera_id == getattr(self, 'current_camera_id', 0):
            return
        
        print(f"正在切換到攝像頭 {camera_id}...")
        self.skeleton_processor.clear()
        self.current_action = "等待中..."
        self.stable_action = "等待中..."
        
        if self.start_camera(camera_id):
            if hasattr(self, 'camera_var'):
                self.camera_var.set(camera_id)
            print(f"✓ 已切換到攝像頭 {camera_id}")
        else:
            print(f"⚠ 切換攝像頭 {camera_id} 失敗")

    def set_model_type(self, model_type: ModelType):
        """切換識別模型"""
        if model_type == self.model_type:
            return
        
        print(f"\n切換模型: {self.model_type.value} -> {model_type.value}")
        self.model_type = model_type
        
        # 更新全局配置
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if model_type == ModelType.STGCNPP:
            config.action.config_file = os.path.join(base_dir, "../", local_config.stgcnpp_config)
            config.action.checkpoint_file = os.path.join(base_dir, "../", local_config.stgcnpp_checkpoint)
        else:
            config.action.config_file = os.path.join(base_dir, "../", local_config.mmaction_config)
            config.action.checkpoint_file = os.path.join(base_dir, "../", local_config.mmaction_checkpoint)
            
        # 重啟識別器
        self.action_recognizer.stop()
        self.action_recognizer = ActionRecognizerAsync()
        self.action_recognizer.start()
        
        self.skeleton_processor.clear()
        
        # 更新 GUI
        self.model_type_var.set(model_type.value)
        print(f"✓ 已切換到 {model_type.value}")

    def update_video(self):
        if not self.running:
            return
        
        current_time = time.time()
        time_interval = 1.0 / self.current_fps
        should_capture = (current_time - self.last_capture_time) >= time_interval
        
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)
            self.display_frame = frame.copy()
            
            # 只有在模擬 FPS 時間到時才進行處理
            if should_capture:
                # 1. 提取骨架
                keypoints_data = self.pose_extractor.extract(frame)
                
                # 2. 封裝 FrameData
                frame_data = FrameData(
                    timestamp=current_time,
                    frame_no=self.frame_count,
                    image=frame,
                    keypoints=keypoints_data,
                    reid_results=[],
                    basic_info={},
                    frame_info={"source": "webcam"},
                    raw_data={}
                )
                self.frame_count += 1
                
                # 3. 骨架處理 (補幀、平滑)
                self.current_skeleton_frame = self.skeleton_processor.process_frame(frame_data)
                
                # 更新補幀緩衝區
                self.interpolated_buffer = self.skeleton_processor.get_interpolated_frames()
                
                # 4. 動作識別
                self._try_action_recognition()
                
                self.last_capture_time = current_time
                
                # 更新靜態顯示輸出 (符合採樣率)
                self.display_output = self._render_static_view(self.display_frame)
        
        # 更新顯示
        output = self._get_current_display()
        output_rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(output_rgb)
        self.photo = ImageTk.PhotoImage(image=img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        self.update_labels()
        self.root.after(33, self.update_video)

    def _try_action_recognition(self):
        """嘗試提交動作識別請求"""
        sequences = self.skeleton_processor.get_all_skeleton_sequences()
        if sequences:
            sequences_info = {}
            for person_id, sequence in sequences.items():
                motion = self.skeleton_processor.get_motion_magnitude(person_id)
                visibility = self.skeleton_processor.analyze_visibility(person_id)
                sequences_info[person_id] = {
                    'sequence': sequence,
                    'motion': motion,
                    'visibility': visibility
                }
                
                # 更新本地狀態用於顯示
                if person_id == 0: # 假設只顯示第一個人
                    self.motion_magnitude = motion
                    self.skeleton_quality = (visibility['is_valid'], visibility['avg_conf'], visibility['visible_count'])
            
            self.action_recognizer.submit(sequences_info)

    def update_labels(self):
        """從識別器獲取結果並更新 GUI"""
        result = self.action_recognizer.get_current_result(0) # 獲取 ID 0 的結果
        
        if result:
            # 根據模式選擇顯示的標籤
            # 檢查簡化模式開關 (self.simplified_var)
            use_simplified = False
            if hasattr(self, 'simplified_var'):
                use_simplified = self.simplified_var.get()
            
            if use_simplified and config.simplified.labels and hasattr(result, 'simplified_label') and result.simplified_label:
                self.stable_action = result.simplified_label
            else:
                self.stable_action = result.action_label
                
            self.stable_confidence = result.confidence
            self.top5_predictions = result.top_k_actions
            
            # 更新 GUI 變數
            self.action_var.set(f"✓ {self.stable_action}")
            self.confidence_var.set(f"信心度: {self.stable_confidence:.1%}")
            
            top5_text = "\n".join([f"{i+1}. {label}: {score:.1%}" 
                                   for i, (label, score) in enumerate(self.top5_predictions[:5])])
            self.top5_var.set(top5_text)
        
        # 更新品質顯示
        is_valid, avg_conf, visible_count = self.skeleton_quality
        quality_status = "✓" if is_valid else "✗"
        motion_status = "動態" if self.motion_magnitude >= config.motion.threshold_low else "靜態"
        self.quality_var.set(f"骨架: {quality_status} ({visible_count}/17)  動作: {motion_status} ({self.motion_magnitude:.1f}px)")

    def _render_static_view(self, frame: np.ndarray) -> np.ndarray:
        """渲染靜態視圖 (Original, Overlay, YOLO Only)"""
        h, w = local_config.camera_height, local_config.camera_width
        output = np.zeros((h, w, 3), dtype=np.uint8)
        
        if self.view_mode == ViewMode.ORIGINAL:
            if frame is not None:
                output = frame.copy()
                
        elif self.view_mode == ViewMode.OVERLAY:
            if frame is not None:
                output = frame.copy()
            if self.current_skeleton_frame:
                for person in self.current_skeleton_frame.persons:
                    Visualizer.draw_skeleton(
                        output, 
                        person.get_keypoints(use_smoothed=False),
                        person_id=person.person_id,
                        box=person.box,
                        show_confidence=False
                    )
                
        elif self.view_mode == ViewMode.YOLO_ONLY:
            if self.current_skeleton_frame:
                for person in self.current_skeleton_frame.persons:
                    Visualizer.draw_skeleton(
                        output, 
                        person.get_keypoints(use_smoothed=False),
                        person_id=person.person_id,
                        box=person.box,
                        show_confidence=False
                    )
        
        # 繪製資訊疊加層
        output = self._draw_info_overlay(output)
        return output

    def _get_current_display(self) -> np.ndarray:
        """取得當前顯示畫面"""
        h, w = local_config.camera_height, local_config.camera_width
        
        if self.view_mode == ViewMode.INTERPOLATED:
            # Interpolated 視圖：顯示補幀結果（流暢播放）
            output = np.zeros((h, w, 3), dtype=np.uint8)
            
            target_frame = None
            if self.interpolated_buffer:
                # 防止循環播放：如果播放索引超過緩衝區長度，則停留在最後一幀
                if self.interp_play_index >= len(self.interpolated_buffer):
                    self.interp_play_index = len(self.interpolated_buffer) - 1
                
                target_frame = self.interpolated_buffer[self.interp_play_index]
                # 更新索引以便下一幀播放下一張 (30 FPS)
                self.interp_play_index += 1
            elif self.current_skeleton_frame:
                target_frame = self.current_skeleton_frame
            
            if target_frame:
                for person in target_frame.persons:
                    Visualizer.draw_skeleton(
                        output, 
                        person.get_keypoints(use_smoothed=True),
                        person_id=person.person_id,
                        box=person.box,
                        show_confidence=False
                    )
            
            # 繪製資訊疊加層
            output = self._draw_info_overlay(output)
            return output
            
        else:
            # 其他視圖：顯示最近一次採樣的結果（一卡一卡的效果）
            if self.display_output is not None:
                return self.display_output
            return np.zeros((h, w, 3), dtype=np.uint8)

    def _draw_info_overlay(self, img: np.ndarray) -> np.ndarray:
        """繪製資訊疊加層"""
        buffer_status = self.skeleton_processor.get_buffer_status()
        
        # 建構 info dict
        info = {
            'mode': self.view_mode.value,
            'sample_fps': self.current_fps,
            'output_fps': 30,
            'buffer': buffer_status['raw_frames'],
            'buffer_max': config.interpolation.sequence_length,
            'action': self.stable_action,
            'interp_t': 0.0
        }
        
        return Visualizer.draw_info_overlay(img, info)

    # === GUI 回調函數 ===
    def on_fps_change(self, val):
        self.current_fps = float(val)
        self.fps_label_var.set(f"採樣: {int(float(val))} FPS")
    
    def set_fps(self, fps_val):
        self.current_fps = fps_val
        self.fps_var.set(fps_val)
        self.fps_label_var.set(f"採樣: {int(fps_val)} FPS")
    
    def set_view_mode(self, mode: ViewMode):
        self.view_mode = mode
        self.view_mode_var.set(mode.value)
        
    def toggle_simplified_mode(self):
        """切換簡化/完整辨識模式"""
        # 更新全局配置
        # 注意：ActionRecognizerAsync 會自動讀取新的 config，但可能需要清除緩存
        # 這裡我們主要更新 GUI 顯示
        use_simplified = self.simplified_var.get()
        
        # 這裡我們需要一種方式通知 ActionRecognizer 使用簡化模式
        # 目前 ActionRecognizer 依賴 config.simplified 是否存在
        # 我們可以動態修改 config.simplified 的行為，或者 ActionRecognizer 應該檢查這個標誌
        
        # 暫時方案：我們假設 config.simplified 始終存在，但我們可以通過修改 mapping 來禁用它
        # 或者更簡單，我們在 update_labels 裡決定顯示哪個標籤
        
        if use_simplified:
            self.mode_info_var.set("✓ 簡化: 坐著/站立/走動/跳躍/蹲下/打鬥/跌倒")
            print("已切換到簡化模式（7類）")
        else:
            self.mode_info_var.set("○ 完整: 60種NTU動作")
            print("已切換到完整模式（60類）")
            
        # 清除狀態
        self.stable_action = "等待中..."

    def refresh_cameras(self):
        print("正在重新偵測攝像頭...")
        self.available_cameras = self.detect_cameras()
        
        if hasattr(self, 'camera_buttons_frame'):
            for widget in self.camera_buttons_frame.winfo_children():
                widget.destroy()
            
            for cam in self.available_cameras:
                btn = ttk.Radiobutton(
                    self.camera_buttons_frame, 
                    text=f"{cam['id']}: {cam['resolution']}",
                    value=cam['id'],
                    variable=self.camera_var,
                    command=lambda c=cam['id']: self.switch_camera(c)
                )
                btn.pack(side=tk.LEFT, padx=5)
        
        if hasattr(self, 'camera_info_var'):
            if len(self.available_cameras) > 0:
                cam_list = ", ".join([f"{c['id']}" for c in self.available_cameras])
                self.camera_info_var.set(f"可用: [{cam_list}]，目前: {self.current_camera_id}")
            else:
                self.camera_info_var.set("未偵測到攝像頭")

    def reset_buffer(self):
        self.skeleton_processor.clear()
        self.current_action = "等待中..."
        self.stable_action = "等待中..."
        print("緩衝區已重置")

    def on_closing(self):
        self.running = False
        self.action_recognizer.stop()
        if self.cap:
            self.cap.release()
        self.root.destroy()
        print("程式已結束")

    def run(self):
        print("偵測可用攝像頭...")
        self.available_cameras = self.detect_cameras()
        
        if not self.start_camera():
            return
        
        self.root = tk.Tk()
        self.root.title("Webcam Action Recognition v2 - YOLO-Pose + MMAction2 (Unified)")
        self.root.geometry("1050x650")
        
        style = ttk.Style()
        try:
            style.theme_use('aqua')
        except:
            pass
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左側：影像
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(left_frame, width=local_config.camera_width, 
                               height=local_config.camera_height, bg='black',
                               highlightthickness=0)
        self.canvas.pack(pady=10)
        
        # 右側：控制面板
        right_frame = ttk.Frame(main_frame, width=350)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        
        # === 模型選擇 ===
        model_frame = ttk.LabelFrame(right_frame, text="識別模型", padding="10")
        model_frame.pack(fill=tk.X, pady=5)
        
        self.model_type_var = tk.StringVar(value=self.model_type.value)
        model_frame.columnconfigure(0, weight=1)
        model_frame.columnconfigure(1, weight=1)
        
        for i, mtype in enumerate(ModelType):
            btn = ttk.Radiobutton(
                model_frame, text=mtype.value, value=mtype.value,
                variable=self.model_type_var,
                command=lambda m=mtype: self.set_model_type(m)
            )
            btn.grid(row=0, column=i, sticky=tk.W, padx=10, pady=2)
            
        # === 視圖模式 ===
        view_frame = ttk.LabelFrame(right_frame, text="視圖模式", padding="10")
        view_frame.pack(fill=tk.X, pady=5)
        
        self.view_mode_var = tk.StringVar(value=ViewMode.OVERLAY.value)
        view_frame.columnconfigure(0, weight=1)
        view_frame.columnconfigure(1, weight=1)
        
        for i, mode in enumerate(ViewMode):
            row = i // 2
            col = i % 2
            btn = ttk.Radiobutton(
                view_frame, text=mode.value, value=mode.value,
                variable=self.view_mode_var,
                command=lambda m=mode: self.set_view_mode(m)
            )
            btn.grid(row=row, column=col, sticky=tk.W, padx=10, pady=2)
            
        # === FPS 控制 ===
        fps_frame = ttk.LabelFrame(right_frame, text="採樣幀率 (補幀至 30 FPS)", padding="10")
        fps_frame.pack(fill=tk.X, pady=5)
        
        self.fps_label_var = tk.StringVar(value=f"採樣: {local_config.default_fps:.0f} FPS")
        ttk.Label(fps_frame, textvariable=self.fps_label_var).pack()
        
        self.fps_var = tk.DoubleVar(value=local_config.default_fps)
        fps_slider = ttk.Scale(
            fps_frame, from_=local_config.min_fps, to=local_config.max_fps,
            variable=self.fps_var, orient=tk.HORIZONTAL, length=280,
            command=self.on_fps_change
        )
        fps_slider.pack(fill=tk.X, pady=5)
        
        presets_frame = ttk.Frame(fps_frame)
        presets_frame.pack(pady=5)
        for fps_val in [2, 3, 15, 30]:
            btn = ttk.Button(presets_frame, text=f"{fps_val}", width=4,
                           command=lambda f=fps_val: self.set_fps(f))
            btn.pack(side=tk.LEFT, padx=1)
            
        # === 簡化模式開關 ===
        mode_frame = ttk.LabelFrame(right_frame, text="辨識模式", padding="10")
        mode_frame.pack(fill=tk.X, pady=5)
        
        self.simplified_var = tk.BooleanVar(value=True) # 預設開啟
        simplified_check = ttk.Checkbutton(
            mode_frame, 
            text="簡化模式（7類）",
            variable=self.simplified_var,
            command=self.toggle_simplified_mode
        )
        simplified_check.pack(anchor=tk.W)
        
        self.mode_info_var = tk.StringVar(value="✓ 簡化: 坐著/站立/走動/跳躍/蹲下/打鬥/跌倒")
        ttk.Label(mode_frame, textvariable=self.mode_info_var, 
                 font=('SF Pro Display', 9)).pack(anchor=tk.W, pady=2)
                 
        # === 識別結果 ===
        result_frame = ttk.LabelFrame(right_frame, text="識別結果", padding="10")
        result_frame.pack(fill=tk.X, pady=5)
        
        self.action_var = tk.StringVar(value="等待中...")
        action_label = ttk.Label(result_frame, textvariable=self.action_var, 
                                font=('SF Pro Display', 16, 'bold'))
        action_label.pack(pady=5)
        
        self.confidence_var = tk.StringVar(value="信心度: 0%")
        ttk.Label(result_frame, textvariable=self.confidence_var).pack()
        
        self.quality_var = tk.StringVar(value="骨架品質: -")
        ttk.Label(result_frame, textvariable=self.quality_var, 
                 font=('SF Pro Display', 9)).pack(pady=2)
        
        ttk.Separator(result_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        ttk.Label(result_frame, text="Top 5:", font=('SF Pro Display', 10, 'bold')).pack(anchor=tk.W)
        
        self.top5_var = tk.StringVar(value="等待識別...")
        ttk.Label(result_frame, textvariable=self.top5_var, justify=tk.LEFT).pack(anchor=tk.W, pady=5)
        
        # === 相機選擇 ===
        camera_frame = ttk.LabelFrame(right_frame, text="攝像頭", padding="10")
        camera_frame.pack(fill=tk.X, pady=5)
        
        self.camera_buttons_frame = ttk.Frame(camera_frame)
        self.camera_buttons_frame.pack(fill=tk.X)
        self.camera_var = tk.IntVar(value=self.current_camera_id)
        
        for cam in self.available_cameras:
            btn = ttk.Radiobutton(
                self.camera_buttons_frame, 
                text=f"{cam['id']}: {cam['resolution']}",
                value=cam['id'],
                variable=self.camera_var,
                command=lambda c=cam['id']: self.switch_camera(c)
            )
            btn.pack(side=tk.LEFT, padx=5)
            
        self.camera_info_var = tk.StringVar()
        if len(self.available_cameras) > 0:
            cam_list = ", ".join([f"{c['id']}" for c in self.available_cameras])
            self.camera_info_var.set(f"可用: [{cam_list}]，目前: {self.current_camera_id}")
        else:
            self.camera_info_var.set("未偵測到攝像頭")
        ttk.Label(camera_frame, textvariable=self.camera_info_var).pack(pady=2)
        
        # === 控制按鈕 ===
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="重新偵測", command=self.refresh_cameras).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(control_frame, text="重置緩衝區", command=self.reset_buffer).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(control_frame, text="退出", command=self.on_closing).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 啟動識別器
        self.action_recognizer.start()
        self.running = True
        
        self.update_video()
        self.root.mainloop()

def main():
    app = WebcamActionApp()
    app.run()

if __name__ == "__main__":
    main()
