"""
webcam_source.py - Webcam 攝像頭資料來源模組

這個模組負責：
- 使用電腦攝像頭捕捉影像
- 使用 YOLO-Pose 提取骨架關鍵點（支援 v8n/v11n 切換）
- 使用 ReID 提取人員特徵向量
- 模擬 WiseEye2 輸出的 JSON 格式（tflm_yolov8n_pose_reid）
- 可調整採樣率（模擬低 FPS 環境）
- 預覽畫面與採樣同步（一卡一卡的效果）

功能：
- 切換鏡頭
- YOLO 辨識（v8n / v11n）
- ReID 特徵提取
- 可變採樣率
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

from we_mma_sender.config import config
from we_mma_sender.reid import ReIDExtractor
from we_mma_sender.yolo import PoseExtractor, YOLOModel


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


class WebcamSource:
    """Webcam 攝像頭資料來源（模擬 WiseEye2 tflm_yolov8n_pose_reid）"""
    
    def __init__(self, on_frame_received: Optional[Callable[[FrameData], None]] = None):
        """
        初始化 Webcam 來源
        
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
        
        # 攝像頭設定
        self.current_camera_id = config.webcam.camera_id
        self.available_cameras: List[Dict] = []
        
        # FPS 控制
        self.target_fps = config.webcam.default_fps
        self.last_capture_time = 0.0
        
        # 執行緒
        self.capture_thread: Optional[threading.Thread] = None
        
        # 回調函數
        self.on_frame_received = on_frame_received
        self.on_camera_changed: Optional[Callable[[int], None]] = None
        
        # 統計資訊
        self.frame_count: int = 0
        self.total_frame_count: int = 0
        self.fps_start_time: float = time.time()
        self.current_fps: float = 0.0
        
        # 預覽幀資料（只在採樣時更新，產生一卡一卡的效果）
        self.preview_frame: Optional[np.ndarray] = None
        self.preview_keypoints: List[Any] = []
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_keypoints: List[Any] = []
        self.latest_reid_results: List[Any] = []
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[WebcamSource][{time.time():.3f}] {msg}")
    
    def detect_cameras(self) -> List[Dict]:
        """偵測可用的攝像頭"""
        cameras = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cameras.append({'id': i, 'resolution': f"{w}x{h}"})
                cap.release()
        self.available_cameras = cameras
        return cameras
    
    def start(self, camera_id: Optional[int] = None) -> bool:
        """啟動 Webcam 來源"""
        if self.is_running:
            return True
        
        if camera_id is not None:
            self.current_camera_id = camera_id
        
        # 偵測攝像頭
        if not self.available_cameras:
            self.detect_cameras()
        
        # 開啟攝像頭
        self.cap = cv2.VideoCapture(self.current_camera_id)
        if not self.cap.isOpened():
            self.debug_log(f"無法開啟攝像頭 {self.current_camera_id}")
            return False
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.webcam.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.webcam.height)
        
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
        
        self.debug_log(f"攝像頭 {self.current_camera_id} 已啟動")
        return True
    
    def stop(self):
        """停止 Webcam 來源"""
        self.is_running = False
        self.stop_event.set()
        
        # 等待執行緒結束
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
        
        self.debug_log("Webcam 已停止")
    
    def switch_camera(self, camera_id: int) -> bool:
        """切換攝像頭"""
        if camera_id == self.current_camera_id and self.is_running:
            return True
        
        self.debug_log(f"正在切換到攝像頭 {camera_id}...")
        
        was_running = self.is_running
        
        if was_running:
            self.stop()
            time.sleep(0.5)  # 增加等待時間
        
        self.current_camera_id = camera_id
        
        if was_running:
            return self.start(camera_id)
        
        return True
    
    def switch_yolo_model(self, model_type: YOLOModel) -> bool:
        """
        切換 YOLO 模型版本
        
        Args:
            model_type: YOLOModel.YOLOV8N 或 YOLOModel.YOLO11N
        """
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
    
    def get_fps(self) -> float:
        """獲取當前實際 FPS"""
        return self.current_fps
    
    def set_reid_enabled(self, enabled: bool):
        """設定是否啟用 ReID"""
        self.reid_enabled = enabled
        if enabled and self.reid_extractor is None:
            self.reid_extractor = ReIDExtractor()
        self.debug_log(f"ReID {'已啟用' if enabled else '已停用'}")
    
    def _capture_loop(self):
        """捕捉執行緒主迴圈"""
        self.debug_log("Capture loop started")
        
        while not self.stop_event.is_set() and self.is_running:
            current_time = time.time()
            time_interval = 1.0 / self.target_fps
            
            # 安全讀取
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.01)
                continue
            
            try:
                ret, frame = self.cap.read()
            except Exception as e:
                self.debug_log(f"讀取幀錯誤: {e}")
                time.sleep(0.01)
                continue
            
            if not ret or frame is None:
                time.sleep(0.01)
                continue
            
            # 水平翻轉（鏡像效果）
            frame = cv2.flip(frame, 1)
            self.latest_frame = frame.copy()
            
            # 檢查是否到達採樣時間
            should_capture = (current_time - self.last_capture_time) >= time_interval
            
            if should_capture:
                capture_start = time.time()
                self.last_capture_time = current_time
                
                # 提取骨架
                yolo_start = time.time()
                keypoints_raw, boxes_raw = [], []
                if self.pose_extractor and self.pose_extractor.ready:
                    keypoints_raw, boxes_raw = self.pose_extractor.extract(frame)
                yolo_time = (time.time() - yolo_start) * 1000
                
                # 格式化關鍵點（WiseEye2 格式）
                keypoints_formatted = self._format_keypoints(keypoints_raw, boxes_raw)
                self.latest_keypoints = keypoints_formatted
                
                # 提取 ReID 特徵
                reid_start = time.time()
                reid_results = []
                if self.reid_enabled and self.reid_extractor and len(boxes_raw) > 0:
                    reid_results = self._extract_reid_features(frame, boxes_raw)
                reid_time = (time.time() - reid_start) * 1000
                self.latest_reid_results = reid_results
                
                # 更新預覽幀（只在採樣時更新，產生一卡一卡的效果）
                self.preview_frame = frame.copy()
                self.preview_keypoints = keypoints_formatted
                
                # 建立 FrameData
                frame_data = self._create_frame_data(frame, keypoints_formatted, reid_results)
                
                # 計算處理時間
                total_time = (time.time() - capture_start) * 1000
                max_fps = 1000.0 / total_time if total_time > 0 else 999
                
                # 每 30 幀輸出一次效能資訊
                if self.total_frame_count % 30 == 0:
                    self.debug_log(f"處理時間: YOLO={yolo_time:.1f}ms, ReID={reid_time:.1f}ms, 總計={total_time:.1f}ms, 最大可達 FPS={max_fps:.1f}")
                
                # 更新統計
                self._update_fps()
                self.total_frame_count += 1
                
                # 調用回調
                if self.on_frame_received:
                    self.on_frame_received(frame_data)
            
            time.sleep(0.005)
        
        self.debug_log("Capture loop ended")
    
    def _format_keypoints(self, keypoints_list: List, boxes_list: List) -> List[List[Any]]:
        """
        格式化關鍵點為 WiseEye2 格式
        
        格式: [ [box_data, kpt1, kpt2...], ... ]
        """
        formatted_persons = []
        
        for kpts, box in zip(keypoints_list, boxes_list):
            x1, y1, x2, y2, conf = box[:5]
            w, h = x2 - x1, y2 - y1
            
            # box_data: [x, y, w, h, confidence, target]
            box_data = [float(x1), float(y1), float(w), float(h), float(conf * 100), 0]
            
            # 關鍵點列表
            kpt_list = []
            for k in kpts:
                kpt_list.append([float(k[0]), float(k[1]), float(k[2]), 0])
            
            person_data = [box_data] + kpt_list
            formatted_persons.append(person_data)
        
        return formatted_persons
    
    def _extract_reid_features(self, frame: np.ndarray, boxes_list: List) -> List[List[float]]:
        """
        為每個偵測到的人員提取 ReID 特徵
        
        格式與 tflm_yolov8n_pose_reid 相同:
        [[向量1], [向量2], ...] - 每個向量是 256 個浮點數的列表
        向量的索引與 keypoints 的索引對應
        """
        reid_results = []
        
        for idx, box in enumerate(boxes_list):
            x1, y1, x2, y2 = [int(v) for v in box[:4]]
            
            # 裁剪人員區域
            person_crop = self.reid_extractor.crop_person(frame, x1, y1, x2, y2)
            
            if person_crop is not None:
                feature = self.reid_extractor.extract_features(person_crop)
                
                if feature is not None:
                    # 直接將向量作為列表加入（與 tflm_yolov8n_pose_reid 格式相同）
                    reid_results.append(feature.tolist())
                else:
                    # 如果提取失敗，加入空向量以保持索引對應
                    reid_results.append([])
            else:
                # 如果裁剪失敗，加入空向量
                reid_results.append([])
        
        return reid_results
    
    def _create_frame_data(self, frame: np.ndarray, keypoints: List[Any], 
                          reid_results: List[List[float]]) -> FrameData:
        """建立 FrameData（模擬 WiseEye2 tflm_yolov8n_pose_reid 輸出格式）"""
        # 編碼影像為 base64
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        basic_info = {
            "device_id": "WEBCAM_SIM",
            "name": f"Webcam Simulator ({self.current_yolo_model.value})",
            "ver": "1.0.0"
        }
        
        frame_info = {
            "frame_no": self.total_frame_count,
            "algo_tick": int((time.time() - self.last_capture_time) * 1000),
            "source": "webcam",
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
        """獲取預覽用的幀（與採樣率同步，一卡一卡的效果）"""
        return self.preview_frame
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """獲取最新的攝像頭幀（實時）"""
        return self.latest_frame
    
    def get_preview_keypoints(self) -> List[Any]:
        """獲取預覽用的骨架關鍵點"""
        return self.preview_keypoints
    
    def get_latest_keypoints(self) -> List[Any]:
        """獲取最新的骨架關鍵點"""
        return self.latest_keypoints
    
    def get_latest_reid_results(self) -> List[Any]:
        """獲取最新的 ReID 結果"""
        return self.latest_reid_results
    
    def get_status(self) -> str:
        """獲取狀態資訊"""
        if self.is_running:
            reid_status = "ReID:ON" if self.reid_enabled else "ReID:OFF"
            return f"Camera {self.current_camera_id} ({self.current_yolo_model.value}) FPS:{self.current_fps:.1f}/{self.target_fps:.1f} {reid_status}"
        return "已停止"
    
    def get_camera_options(self) -> List[str]:
        """獲取攝像頭選項列表"""
        if not self.available_cameras:
            self.detect_cameras()
        return [f"{c['id']}: {c['resolution']}" for c in self.available_cameras]
    
    def get_yolo_model_options(self) -> List[str]:
        """獲取 YOLO 模型選項"""
        return [m.value for m in YOLOModel]
