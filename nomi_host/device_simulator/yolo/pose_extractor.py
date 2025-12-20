"""
pose_extractor.py - YOLO-Pose 骨架提取器

使用 Ultralytics YOLO-Pose 模型提取人體骨架關鍵點
支援 YOLOv8n-pose 和 YOLO11n-pose 模型切換
輸出格式與 WiseEye2 tflm_yolov8n_pose_reid 相容
"""

import os
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


class YOLOModel(Enum):
    """YOLO 模型版本"""
    YOLOV8N = "yolov8n-pose"
    YOLO11N = "yolo11n-pose"


class PoseExtractor:
    """YOLO-Pose 骨架提取器"""
    
    # 模型檔案對應
    MODEL_FILES = {
        YOLOModel.YOLOV8N: "yolov8n-pose.pt",
        YOLOModel.YOLO11N: "yolo11n-pose.pt",
    }
    
    def __init__(self, model_type: YOLOModel = YOLOModel.YOLOV8N, 
                 model_path: Optional[str] = None,
                 conf_threshold: float = 0.5,
                 enable_tracking: bool = True):
        """
        初始化 YOLO-Pose 提取器
        
        Args:
            model_type: 模型類型 (YOLOv8n 或 YOLO11n)
            model_path: 自訂模型路徑（可選）
            conf_threshold: 置信度閾值
            enable_tracking: 是否啟用追蹤功能來分配穩定的人物 ID
        """
        self.model = None
        self.ready = False
        self.conf_threshold = conf_threshold
        self.model_type = model_type
        self.enable_tracking = enable_tracking
        
        # ID 映射：將 YOLO 追蹤 ID 映射為從 0 開始的連續 ID
        self._track_to_local_id: Dict[int, int] = {}
        self._next_local_id = 0
        
        # 決定模型路徑
        if model_path is None:
            model_path = self._find_model_path(model_type)
        
        self.model_path = model_path
        self._init_model()
    
    def _find_model_path(self, model_type: YOLOModel) -> str:
        """尋找模型檔案路徑"""
        filename = self.MODEL_FILES.get(model_type, "yolov8n-pose.pt")
        
        # 搜尋路徑列表
        search_paths = [
            # 1. 同目錄下
            os.path.join(os.path.dirname(__file__), filename),
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                return path
        
        # 如果都找不到，返回檔名讓 ultralytics 自動下載
        return filename
    
    def _init_model(self):
        """初始化 YOLO 模型"""
        try:
            from ultralytics import YOLO
            
            self.model = YOLO(self.model_path)
            self.ready = True
            print(f"✓ 已載入 YOLO-Pose ({self.model_type.value}): {self.model_path}")
            
        except Exception as e:
            print(f"⚠ YOLO-Pose 載入失敗: {e}")
            import traceback
            traceback.print_exc()
    
    def switch_model(self, model_type: YOLOModel) -> bool:
        """
        切換 YOLO 模型版本
        
        Args:
            model_type: 新的模型類型
            
        Returns:
            是否切換成功
        """
        if model_type == self.model_type and self.ready:
            return True
        
        self.model_type = model_type
        self.model_path = self._find_model_path(model_type)
        self.ready = False
        self.model = None
        
        self._init_model()
        return self.ready
    
    def extract(self, frame: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray], List[int]]:
        """
        執行 YOLO 並返回關鍵點、邊界框和追蹤 ID
        
        Args:
            frame: BGR 影像
            
        Returns:
            (keypoints_list, boxes_list, local_ids)
            - keypoints_list: List[np.ndarray] 每個人的 17 個關鍵點 [[x,y,conf], ...]
            - boxes_list: List[np.ndarray] 每個人的邊界框 [x1, y1, x2, y2, conf]
            - local_ids: List[int] 每個人的本地 ID (從 0 開始)
        """
        if not self.ready or self.model is None:
            return [], [], []
            
        try:
            # 使用 tracking 模式來獲取穩定的 ID
            if self.enable_tracking:
                results = self.model.track(
                    frame, 
                    verbose=False, 
                    conf=self.conf_threshold,
                    persist=True,  # 保持追蹤狀態
                    tracker="bytetrack.yaml"  # 使用 ByteTrack 追蹤器
                )
            else:
                results = self.model(frame, verbose=False, conf=self.conf_threshold)
            
            keypoints_list = []
            boxes_list = []
            raw_track_ids = []  # YOLO 原始追蹤 ID
            
            for r in results:
                if r.boxes is None or r.keypoints is None:
                    continue
                    
                boxes = r.boxes.data.cpu().numpy()
                kpts = r.keypoints.data.cpu().numpy()
                
                # 取得追蹤 ID（如果有的話）
                if self.enable_tracking and r.boxes.id is not None:
                    ids = r.boxes.id.cpu().numpy().astype(int)
                else:
                    ids = list(range(len(boxes)))  # 沒有追蹤時使用索引
                
                for i in range(len(boxes)):
                    # 邊界框: [x1, y1, x2, y2, conf, cls]
                    box = boxes[i]
                    x1, y1, x2, y2, conf = box[:5]
                    boxes_list.append(np.array([x1, y1, x2, y2, conf]))
                    
                    # 關鍵點: [[x, y, conf], ...]
                    person_kpts = kpts[i]
                    keypoints_list.append(person_kpts)
                    
                    # 追蹤 ID
                    track_id = int(ids[i]) if i < len(ids) else i
                    raw_track_ids.append(track_id)
            
            # 如果沒有偵測到任何人，重置 ID 映射
            if len(raw_track_ids) == 0:
                self._track_to_local_id.clear()
                self._next_local_id = 0
                return [], [], []
            
            # 將 YOLO 追蹤 ID 映射為本地 ID (從 0 開始)
            local_ids = []
            current_track_ids = set(raw_track_ids)
            
            # 清理已不存在的追蹤 ID
            stale_ids = [tid for tid in self._track_to_local_id if tid not in current_track_ids]
            for tid in stale_ids:
                del self._track_to_local_id[tid]
            
            for track_id in raw_track_ids:
                if track_id not in self._track_to_local_id:
                    # 分配新的本地 ID
                    self._track_to_local_id[track_id] = self._next_local_id
                    self._next_local_id += 1
                local_ids.append(self._track_to_local_id[track_id])
            
            # 如果所有人都離開過，重新從 0 開始編號
            if len(self._track_to_local_id) == 0:
                self._next_local_id = 0
            
            return keypoints_list, boxes_list, local_ids
            
        except Exception as e:
            print(f"YOLO Extract Error: {e}")
            import traceback
            traceback.print_exc()
            return [], [], []
    
    def extract_formatted(self, frame: np.ndarray) -> List[List[Any]]:
        """
        執行 YOLO 並返回 WiseEye2 格式的關鍵點列表
        
        格式: [ [box_data, kpt1, kpt2...], ... ]
        box_data: [x, y, w, h, confidence, target]
        kpt: [x, y, conf, target]
        
        Args:
            frame: BGR 影像
            
        Returns:
            與 WiseEye2 相容的格式化資料
        """
        keypoints_list, boxes_list, track_ids = self.extract(frame)
        
        formatted_persons = []
        
        for kpts, box, track_id in zip(keypoints_list, boxes_list, track_ids):
            x1, y1, x2, y2, conf = box[:5]
            w, h = x2 - x1, y2 - y1
            
            # box_data: [x, y, w, h, confidence, target]
            # target 現在使用追蹤 ID 而非固定的 0
            box_data = [float(x1), float(y1), float(w), float(h), float(conf * 100), int(track_id)]
            
            # 關鍵點列表
            kpt_list = []
            for k in kpts:
                # [x, y, conf, target] - 關鍵點的 target 也使用追蹤 ID
                kpt_list.append([float(k[0]), float(k[1]), float(k[2]), int(track_id)])
            
            person_data = [box_data] + kpt_list
            formatted_persons.append(person_data)
        
        return formatted_persons
    
    def draw_skeleton(self, frame: np.ndarray, keypoints_list: List[np.ndarray], 
                     boxes_list: List[np.ndarray], 
                     track_ids: Optional[List[int]] = None) -> np.ndarray:
        """
        在影像上繪製骨架
        
        Args:
            frame: BGR 影像
            keypoints_list: 關鍵點列表
            boxes_list: 邊界框列表
            track_ids: 追蹤 ID 列表（可選）
            
        Returns:
            繪製後的影像
        """
        # COCO 骨架連接
        SKELETON = [
            (0, 1), (0, 2), (1, 3), (2, 4),
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
            (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16)
        ]
        
        # 如果沒有提供 track_ids，使用索引
        if track_ids is None:
            track_ids = list(range(len(keypoints_list)))
        
        display = frame.copy()
        
        for idx, (kpts, box) in enumerate(zip(keypoints_list, boxes_list)):
            track_id = track_ids[idx] if idx < len(track_ids) else idx
            # 繪製邊界框
            x1, y1, x2, y2, conf = box[:5]
            cv2.rectangle(display, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(display, f"ID:{track_id} {conf:.2f}", (int(x1), int(y1)-5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # 解析關鍵點
            parsed_kpts = []
            for k in kpts:
                parsed_kpts.append((int(k[0]), int(k[1]), float(k[2])))
            
            # 繪製連線
            for p1, p2 in SKELETON:
                if p1 < len(parsed_kpts) and p2 < len(parsed_kpts):
                    kp1, kp2 = parsed_kpts[p1], parsed_kpts[p2]
                    if kp1[2] > 0.3 and kp2[2] > 0.3:
                        cv2.line(display, (kp1[0], kp1[1]), (kp2[0], kp2[1]), (255, 255, 0), 2)
            
            # 繪製關鍵點
            for kp in parsed_kpts:
                if kp[2] > 0.3:
                    cv2.circle(display, (kp[0], kp[1]), 3, (0, 255, 255), -1)
        
        return display
    
    def get_model_info(self) -> dict:
        """獲取當前模型資訊"""
        return {
            "model_type": self.model_type.value,
            "model_path": self.model_path,
            "ready": self.ready,
            "conf_threshold": self.conf_threshold,
        }
