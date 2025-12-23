"""
video_source.py - Video 影片檔案資料來源模組

這個模組負責：
- 讀取電腦上的影片檔案作為影像來源
- 支援影片循環播放
- 使用 YOLO-Pose 提取骨架關鍵點
- 使用 ReID 提取人員特徵向量
- 模擬 WiseEye2 輸出的 JSON 格式
- 可調整採樣率（模擬低 FPS 環境）
- 支援傳輸不穩模擬（浮動 FPS、隨機阻塞）
"""

import base64
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from device_simulator.config import config
from device_simulator.reid import ReIDExtractor
from device_simulator.sources.webcam_source import FrameData
from device_simulator.yolo import PoseExtractor, YOLOModel


class VideoSource:
    """Video 影片檔案資料來源（模擬 WiseEye2 tflm_yolov8n_pose_reid）"""
    
    def __init__(self, on_frame_received: Optional[Callable[[FrameData], None]] = None):
        """
        初始化 Video 來源
        
        Args:
            on_frame_received: 當提取到骨架資料時的回調函數
        """
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running: bool = False
        self.stop_event = threading.Event()
        
        # YOLO 骨架提取器
        self.pose_extractor: Optional[PoseExtractor] = None
        self.current_yolo_model = YOLOModel.YOLOV8N
        
        # ReID 特徵提取器
        self.reid_extractor: Optional[ReIDExtractor] = None
        self.reid_enabled: bool = True
        
        # 影片設定
        self.video_path: str = ""
        self.loop: bool = True
        
        # FPS 控制
        self.target_fps = config.webcam.default_fps
        self.last_capture_time = 0.0
        self.floating_fps_enabled = config.webcam.floating_fps
        self.random_blocking_enabled = config.webcam.random_blocking
        
        # 執行緒
        self.capture_thread: Optional[threading.Thread] = None
        self.data_lock = threading.Lock()
        
        # 回調函數
        self.on_frame_received = on_frame_received
        
        # 統計資訊
        self.frame_count: int = 0
        self.total_frame_count: int = 0
        self.fps_start_time = time.time()
        self.current_fps: float = 0.0
        
        # 預覽幀資料
        self.preview_frame: Optional[np.ndarray] = None
        self.preview_keypoints: List[Any] = []
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_keypoints: List[Any] = []
        self.latest_reid_results: List[Any] = []
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[VideoSource][{time.time():.3f}] {msg}")
    
    def start(self, video_path: str) -> bool:
        """啟動 Video 來源"""
        if self.is_running:
            self.stop()
            
        if not video_path or not os.path.exists(video_path):
            self.debug_log(f"影片路徑無效: {video_path}")
            return False
            
        self.video_path = video_path
        
        # 開啟影片
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            self.debug_log(f"無法開啟影片: {self.video_path}")
            return False
        
        # 初始化 YOLO
        if self.pose_extractor is None:
            self.pose_extractor = PoseExtractor(
                model_type=self.current_yolo_model,
                conf_threshold=config.webcam.yolo_conf
            )
        
        # 初始化 ReID
        if self.reid_extractor is None and self.reid_enabled:
            self.reid_extractor = ReIDExtractor()
        
        self.is_running = True
        self.stop_event.clear()
        
        # 啟動捕捉執行緒
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        
        self.debug_log(f"影片 {os.path.basename(self.video_path)} 已啟動")
        return True
    
    def stop(self):
        """停止 Video 來源"""
        self.is_running = False
        self.stop_event.set()
        
        # 等待執行緒結束
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
        
        self.debug_log("Video 已停止")
    
    def switch_yolo_model(self, model_type: YOLOModel) -> bool:
        """切換 YOLO 模型版本"""
        if model_type == self.current_yolo_model:
            return True
        
        self.current_yolo_model = model_type
        
        if self.pose_extractor:
            success = self.pose_extractor.switch_model(model_type)
            self.debug_log(f"YOLO 模型切換到 {model_type.value}: {'成功' if success else '失敗'}")
            return success
        
        return True
    
    def set_fps(self, fps: float):
        """設定目標採樣率"""
        self.target_fps = max(config.webcam.min_fps, min(fps, config.webcam.max_fps))
        self.debug_log(f"採樣率設定為 {self.target_fps:.1f} FPS")
    
    def set_floating_fps(self, enabled: bool):
        """設定是否啟用浮動採樣率"""
        self.floating_fps_enabled = enabled
    
    def set_random_blocking(self, enabled: bool):
        """設定是否啟用隨機阻塞"""
        self.random_blocking_enabled = enabled
    
    def set_reid_enabled(self, enabled: bool):
        """設定是否啟用 ReID"""
        self.reid_enabled = enabled
        if enabled and self.reid_extractor is None:
            self.reid_extractor = ReIDExtractor()
    
    def get_preview_data(self) -> Tuple[Optional[np.ndarray], List[Any]]:
        """安全地獲取預覽資料"""
        with self.data_lock:
            if self.preview_frame is None:
                return None, []
            return self.preview_frame.copy(), self.preview_keypoints
            
    def _capture_loop(self):
        """捕捉執行緒主迴圈"""
        self.debug_log("Video capture loop started")
        
        processing_times = []
        
        while not self.stop_event.is_set() and self.is_running:
            current_time = time.time()
            time_interval = 1.0 / self.target_fps
            
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.01)
                continue
            
            try:
                ret, frame = self.cap.read()
                if not ret:
                    if self.loop:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.cap.read()
                    else:
                        break
            except Exception as e:
                self.debug_log(f"讀取影片幀錯誤: {e}")
                time.sleep(0.01)
                continue
            
            if not ret or frame is None:
                time.sleep(0.01)
                continue
            
            with self.data_lock:
                self.latest_frame = frame.copy()
            
            # 檢查是否到達採樣時間
            should_capture = (current_time - self.last_capture_time) >= time_interval
            
            if should_capture:
                capture_start = time.time()
                self.last_capture_time = current_time
                
                # 提取骨架
                yolo_start = time.time()
                keypoints_raw, boxes_raw, track_ids = [], [], []
                if self.pose_extractor and self.pose_extractor.ready:
                    keypoints_raw, boxes_raw, track_ids = self.pose_extractor.extract(frame)
                yolo_time = (time.time() - yolo_start) * 1000
                
                # 格式化關鍵點
                keypoints_formatted = self._format_keypoints(keypoints_raw, boxes_raw, track_ids)
                with self.data_lock:
                    self.latest_keypoints = keypoints_formatted
                
                # 提取 ReID 特徵
                reid_results = []
                if self.reid_enabled and self.reid_extractor and len(boxes_raw) > 0:
                    reid_results = self._extract_reid_features(frame, boxes_raw)
                with self.data_lock:
                    self.latest_reid_results = reid_results
                
                # 更新預覽幀
                with self.data_lock:
                    self.preview_frame = frame.copy()
                    self.preview_keypoints = keypoints_formatted
                
                # 建立 FrameData
                frame_data = self._create_frame_data(frame, keypoints_formatted, reid_results)
                
                # 更新統計
                self._update_fps()
                self.total_frame_count += 1
                
                # 調用回調
                if self.on_frame_received:
                    self.on_frame_received(frame_data)
            
            time.sleep(0.005)
        
        self.debug_log("Video capture loop ended")

    def _format_keypoints(self, keypoints_list: List, boxes_list: List, 
                          track_ids: Optional[List[int]] = None) -> List[List[Any]]:
        """格式化關鍵點為 WiseEye2 格式"""
        formatted_persons = []
        if track_ids is None:
            track_ids = list(range(len(keypoints_list)))
        
        for idx, (kpts, box) in enumerate(zip(keypoints_list, boxes_list)):
            track_id = track_ids[idx] if idx < len(track_ids) else idx
            x1, y1, x2, y2, conf = box[:5]
            w, h = x2 - x1, y2 - y1
            box_data = [float(x1), float(y1), float(w), float(h), float(conf * 100), int(track_id)]
            kpt_list = []
            for k in kpts:
                kpt_list.append([float(k[0]), float(k[1]), float(k[2]), int(track_id)])
            person_data = [box_data] + kpt_list
            formatted_persons.append(person_data)
        return formatted_persons

    def _extract_reid_features(self, frame: np.ndarray, boxes_list: List) -> List[List[float]]:
        """提取 ReID 特徵"""
        reid_results = []
        for idx, box in enumerate(boxes_list):
            x1, y1, x2, y2 = [int(v) for v in box[:4]]
            person_crop = self.reid_extractor.crop_person(frame, x1, y1, x2, y2)
            if person_crop is not None:
                feature = self.reid_extractor.extract_features(person_crop)
                if feature is not None:
                    reid_results.append(feature.tolist())
                else:
                    reid_results.append([])
            else:
                reid_results.append([])
        return reid_results

    def _create_frame_data(self, frame: np.ndarray, keypoints: List[Any], 
                          reid_results: List[List[float]]) -> FrameData:
        """建立 FrameData"""
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        basic_info = {
            "device_id": "VIDEO_SIM",
            "name": f"Video Simulator ({self.current_yolo_model.value})",
            "ver": "1.0.0"
        }
        
        frame_info = {
            "frame_no": self.total_frame_count,
            "algo_tick": int((time.time() - self.last_capture_time) * 1000),
            "source": "video",
            "sample_fps": self.target_fps,
            "yolo_model": self.current_yolo_model.value,
            "reid_enabled": self.reid_enabled
        }
        
        raw_data = {
            "type": 0,
            "name": "INVOKE",
            "code": 0,
            "data": {
                "image": img_b64,
                "keypoints": keypoints,
                "reid_results": reid_results,
                "basic_info": basic_info,
                "frame_info": frame_info
            }
        }
        
        return FrameData(
            timestamp=time.time(),
            frame_no=self.total_frame_count,
            image=frame,
            keypoints=keypoints,
            reid_results=reid_results,
            basic_info=basic_info,
            frame_info=frame_info,
            raw_data=raw_data
        )

    def _update_fps(self):
        """更新 FPS 統計"""
        self.frame_count += 1
        elapsed = time.time() - self.fps_start_time
        if elapsed >= 1.0:
            self.current_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start_time = time.time()

    def get_preview_frame(self) -> Optional[np.ndarray]:
        with self.data_lock:
            return self.preview_frame.copy() if self.preview_frame is not None else None

    def get_preview_keypoints(self) -> List[Any]:
        with self.data_lock:
            return self.preview_keypoints

    def get_status(self) -> str:
        if self.is_running:
            return f"Video: {os.path.basename(self.video_path)} FPS:{self.current_fps:.1f}/{self.target_fps:.1f}"
        return "已停止"
