"""
data_models.py - 資料模型定義

定義感知層與記憶層之間溝通的資料格式
確保資料的結構化與型別安全
"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ActionCandidate:
    """動作候選項"""
    label: str          # 動作標籤
    confidence: float   # 信心度 (0.0 ~ 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        # 確保 confidence 是 Python 原生 float（避免 numpy float32 無法 JSON 序列化）
        return {"label": self.label, "confidence": float(self.confidence)}


@dataclass
class BoundingBox:
    """邊界框"""
    x: int      # 左上角 X
    y: int      # 左上角 Y
    w: int      # 寬度
    h: int      # 高度
    
    def to_list(self) -> List[int]:
        return [self.x, self.y, self.w, self.h]
    
    @classmethod
    def from_tuple(cls, bbox: Tuple[int, int, int, int]) -> "BoundingBox":
        return cls(x=bbox[0], y=bbox[1], w=bbox[2], h=bbox[3])
    
    @property
    def center(self) -> Tuple[int, int]:
        """取得中心點座標"""
        return (self.x + self.w // 2, self.y + self.h // 2)
    
    @property
    def aspect_ratio(self) -> float:
        """取得高寬比"""
        return self.h / self.w if self.w > 0 else 0.0


@dataclass
class EnvironmentData:
    """環境資訊"""
    temperature: Optional[float] = None     # 溫度 (°C)
    humidity: Optional[float] = None        # 濕度 (%)
    co2: Optional[float] = None             # 二氧化碳 (ppm)
    light: Optional[float] = None           # 光照 (lux)
    sound_event: Optional[str] = None       # 聲音事件標籤 (如: "glass_break", "scream")
    room: Optional[str] = None              # 房間名稱 (如: "Living Room")
    activity_label: Optional[str] = None    # 活動標籤 (如: "cooking", "sleeping") - 來自環境感測器/資料集的 Ground Truth
    ground_truth_action: Optional[str] = None  # NTU 動作編碼 (如: "A043") - 用於評估準確度
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PerceptionEvent:
    """
    感知事件 - 從 Receiver 傳送到記憶層的資料單元
    
    這是感知層與記憶層之間的「契約」，定義了所有需要被記憶的資訊。
    """
    
    # === 時間標記 ===
    timestamp: float                        # Unix timestamp (毫秒精度)
    frame_no: int                           # WiseEye2 的幀序號 (用於順序重建)
    
    # === 人物識別 ===
    person_id: int                          # 臨時 ID (ReID 比對後的結果)
    reid_vector: Optional[List[float]] = None   # ReID 特徵向量 (512 維)
    matched_member_id: Optional[int] = None     # 匹配到的成員 ID (若已註冊)
    
    # === 空間資訊 ===
    bbox: Optional[BoundingBox] = None      # 邊界框
    keypoints: Optional[List[List[float]]] = None # 17 個骨架點 [[x, y, score], ...]
    visibility: bool = True                 # 是否在鏡頭內可見
    
    # === 動作資訊 ===
    action_label: str = "Unknown"           # 主要動作標籤
    action_confidence: float = 0.0          # 主要動作信心度
    action_candidates: List[ActionCandidate] = field(default_factory=list)  # 其他候選動作
    action_duration: float = 0.0            # 動作持續時間 (秒)
    motion_magnitude: float = 0.0           # 動作幅度 (歸一化後)
    
    # === 環境資訊 ===
    environment: Optional[EnvironmentData] = None
    
    # === 來源標記 ===
    source_device: str = "WiseEye2"         # 資料來源裝置
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典 (用於 JSON 序列化)"""
        return {
            "timestamp": self.timestamp,
            "frame_no": self.frame_no,
            "person_id": self.person_id,
            "reid_vector": self.reid_vector,
            "matched_member_id": self.matched_member_id,
            "bbox": self.bbox.to_list() if self.bbox else None,
            "keypoints": self.keypoints,
            "visibility": self.visibility,
            "action_label": self.action_label,
            "action_confidence": self.action_confidence,
            "action_candidates": [c.to_dict() for c in self.action_candidates],
            "action_duration": self.action_duration,
            "motion_magnitude": self.motion_magnitude,
            "environment": self.environment.to_dict() if self.environment else None,
            "source_device": self.source_device,
        }
    
    def to_json(self) -> str:
        """轉換為 JSON 字串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerceptionEvent":
        """從字典建立實例"""
        bbox = None
        if data.get("bbox"):
            bbox = BoundingBox(*data["bbox"])
        
        candidates = []
        for c in data.get("action_candidates", []):
            candidates.append(ActionCandidate(**c))
        
        env = None
        if data.get("environment"):
            env = EnvironmentData(**data["environment"])
        
        return cls(
            timestamp=data["timestamp"],
            frame_no=data["frame_no"],
            person_id=data["person_id"],
            reid_vector=data.get("reid_vector"),
            matched_member_id=data.get("matched_member_id"),
            bbox=bbox,
            keypoints=data.get("keypoints"),
            visibility=data.get("visibility", True),
            action_label=data.get("action_label", "Unknown"),
            action_confidence=data.get("action_confidence", 0.0),
            action_candidates=candidates,
            action_duration=data.get("action_duration", 0.0),
            motion_magnitude=data.get("motion_magnitude", 0.0),
            environment=env,
            source_device=data.get("source_device", "WiseEye2"),
        )


@dataclass
class MemberState:
    """
    成員當前狀態 - 記憶層維護的即時狀態
    
    這是記憶層對每個在場成員的「認知」。
    """
    person_id: int                          # 臨時 ID
    member_id: Optional[int] = None         # 已註冊成員 ID
    member_name: Optional[str] = None       # 成員名稱
    
    # 最後已知狀態
    last_seen_time: float = 0.0             # 最後看到的時間
    last_bbox: Optional[BoundingBox] = None # 最後位置
    last_action: str = "Unknown"            # 最後動作
    last_action_start: float = 0.0          # 當前動作開始時間
    last_location: Optional[str] = None     # 最後所在位置 (房間)
    last_action_duration: float = 0.0       # 最後動作持續時間
    
    # 可見性狀態
    is_visible: bool = True                 # 是否在鏡頭內
    disappear_direction: Optional[str] = None  # 消失方向 (如: "left", "right", "top", "bottom")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "person_id": self.person_id,
            "member_id": self.member_id,
            "member_name": self.member_name,
            "last_seen_time": self.last_seen_time,
            "last_bbox": self.last_bbox.to_list() if self.last_bbox else None,
            "last_action": self.last_action,
            "last_action_start": self.last_action_start,
            "last_location": self.last_location,
            "last_action_duration": self.last_action_duration,
            "is_visible": self.is_visible,
            "disappear_direction": self.disappear_direction,
        }


def create_perception_event(
    person_id: int,
    frame_no: int,
    bbox: Tuple[int, int, int, int],
    action_label: str,
    action_confidence: float,
    action_candidates: List[Tuple[str, float]],
    action_duration: float = 0.0,
    motion_magnitude: float = 0.0,
    reid_vector: Optional[List[float]] = None,
    matched_member_id: Optional[int] = None,
    environment: Optional[Dict[str, Any]] = None,
    source_device: str = "WiseEye2",
    keypoints: Optional[List[List[float]]] = None,
) -> PerceptionEvent:
    """
    工廠函數：建立 PerceptionEvent
    
    這個函數簡化了從 Receiver 建立感知事件的流程。
    """
    # 打上 Unix 時間戳 (毫秒精度)
    timestamp = time.time()
    
    # 建立邊界框
    bbox_obj = BoundingBox.from_tuple(bbox) if bbox else None
    
    # 建立動作候選列表
    candidates = [
        ActionCandidate(label=label, confidence=conf)
        for label, conf in action_candidates
    ]
    
    # 建立環境資料
    env_data = None
    if environment:
        env_data = EnvironmentData(**environment)
    
    return PerceptionEvent(
        timestamp=timestamp,
        frame_no=frame_no,
        person_id=person_id,
        reid_vector=reid_vector,
        matched_member_id=matched_member_id,
        bbox=bbox_obj,
        keypoints=keypoints,
        visibility=True,
        action_label=action_label,
        action_confidence=action_confidence,
        action_candidates=candidates,
        action_duration=action_duration,
        motion_magnitude=motion_magnitude,
        environment=env_data,
        source_device=source_device,
    )
