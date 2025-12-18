"""
skeleton_processor.py - 骨架資料處理與補幀模組

這個模組負責：
- 處理從 WiseEye2 接收的骨架資料
- 將骨架資料轉換為 MMAction2 所需的格式
- 實現補幀功能（將 1-2 FPS 插值到 15 FPS）
- 維護骨架序列緩衝區
- 使用專業的骨架濾波器進行平滑和過濾
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .config import config
    from .serial_receiver import FrameData
    from .skeleton_filters import SkeletonPreprocessor
except ImportError:
    from config import config
    from serial_receiver import FrameData
    from skeleton_filters import SkeletonPreprocessor


@dataclass
class PersonSkeleton:
    """單一人物的骨架資料"""
    person_id: int  # 人物 ID（來自追蹤）
    box: Tuple[int, int, int, int]  # (x, y, w, h) 邊界框
    score: float  # 檢測信心度
    keypoints: np.ndarray  # shape: (17, 3) - (x, y, score) - 原始關鍵點
    timestamp: float  # 時間戳
    smoothed_keypoints: Optional[np.ndarray] = None  # 平滑後的關鍵點（用於補幀和動作識別）
    
    def get_keypoints(self, use_smoothed: bool = False) -> np.ndarray:
        """
        獲取關鍵點
        
        Args:
            use_smoothed: 是否使用平滑後的關鍵點
            
        Returns:
            關鍵點陣列
        """
        if use_smoothed and self.smoothed_keypoints is not None:
            return self.smoothed_keypoints
        return self.keypoints


@dataclass
class SkeletonFrame:
    """單一幀的所有人物骨架"""
    timestamp: float
    frame_no: int
    persons: List[PersonSkeleton]


class SkeletonSmoother:
    """
    骨架平滑器 - 使用指數移動平均和速度限制來減少雜訊
    """
    
    def __init__(self, alpha: float = 0.3, max_velocity: float = 50.0, 
                 velocity_conf_threshold: float = 0.6):
        """
        初始化平滑器
        
        Args:
            alpha: EMA 平滑係數 (0-1)，越小越平滑
            max_velocity: 每幀最大移動像素數，超過則視為異常
            velocity_conf_threshold: 速度異常判定的置信度閾值
        """
        self.alpha = alpha
        self.max_velocity = max_velocity
        self.velocity_conf_threshold = velocity_conf_threshold
        # 每個人物的平滑狀態: {person_id: smoothed_keypoints}
        self.states: Dict[int, np.ndarray] = {}
        # 前一幀的關鍵點（用於速度計算）
        self.prev_keypoints: Dict[int, np.ndarray] = {}
        # 歷史速度（用於檢測異常）
        self.velocity_history: Dict[int, List[float]] = {}
        # 連續異常計數
        self.anomaly_count: Dict[int, np.ndarray] = {}
        
    def smooth(self, person_id: int, keypoints: np.ndarray, box: Tuple[int, int, int, int] = None) -> np.ndarray:
        """
        平滑關鍵點
        
        Args:
            person_id: 人物 ID
            keypoints: 原始關鍵點 shape (17, 3)
            box: 邊界框 (x, y, w, h)，用於過濾超出範圍的點
            
        Returns:
            平滑後的關鍵點
        """
        # 確保輸入沒有 NaN
        keypoints = np.nan_to_num(keypoints, nan=0.0)
        num_kpts = keypoints.shape[0]
        
        # 先進行位置合理性過濾
        keypoints = self._filter_unreasonable_positions(keypoints, box)
        
        if person_id not in self.states:
            # 第一次看到這個人，初始化狀態
            self.states[person_id] = keypoints.copy()
            self.prev_keypoints[person_id] = keypoints.copy()
            self.velocity_history[person_id] = [0.0] * 5  # 保存最近5幀的平均速度
            self.anomaly_count[person_id] = np.zeros(num_kpts, dtype=np.int32)
            return keypoints.copy()
        
        prev_kp = self.prev_keypoints[person_id]
        smoothed = self.states[person_id].copy()
        
        # 計算本幀的平均速度
        frame_velocities = []
        
        # 對每個關鍵點進行處理
        for i in range(num_kpts):
            curr_pos = keypoints[i, :2]
            prev_pos = prev_kp[i, :2]
            curr_score = float(keypoints[i, 2])
            prev_score = float(prev_kp[i, 2])
            
            # 確保 score 在有效範圍內
            curr_score = max(0.0, min(1.0, curr_score))
            
            # 如果當前位置是 (0, 0) 或置信度太低，使用前一幀
            if (curr_pos[0] == 0 and curr_pos[1] == 0) or curr_score < 0.3:
                smoothed[i, :2] = self.states[person_id][i, :2]  # 使用平滑狀態而非原始前一幀
                smoothed[i, 2] = max(prev_score * 0.9, 0.1)  # 置信度衰減
                self.anomaly_count[person_id][i] = min(self.anomaly_count[person_id][i] + 1, 10)
                continue
            
            # 計算移動速度
            velocity = np.linalg.norm(curr_pos - prev_pos)
            frame_velocities.append(velocity)
            
            # 計算歷史平均速度
            avg_history_velocity = np.mean(self.velocity_history[person_id]) if self.velocity_history[person_id] else 0
            
            # 判斷是否為異常跳動
            is_anomaly = False
            if velocity > self.max_velocity:
                is_anomaly = True
            elif velocity > avg_history_velocity * 3 and avg_history_velocity > 5:
                # 速度突然變為歷史平均的3倍以上
                is_anomaly = True
            
            # 如果是異常且置信度不夠高，拒絕這個點
            if is_anomaly and curr_score < self.velocity_conf_threshold:
                # 使用平滑狀態，但稍微向當前位置移動
                smoothed[i, :2] = 0.9 * self.states[person_id][i, :2] + 0.1 * curr_pos
                smoothed[i, 2] = curr_score * 0.8
                self.anomaly_count[person_id][i] = min(self.anomaly_count[person_id][i] + 1, 10)
            else:
                # 正常情況：根據置信度和異常歷史調整 alpha
                anomaly_factor = 1.0 / (1.0 + 0.2 * self.anomaly_count[person_id][i])
                effective_alpha = self.alpha * (0.5 + 0.5 * curr_score) * anomaly_factor
                
                # EMA 平滑
                smoothed[i, :2] = (1 - effective_alpha) * self.states[person_id][i, :2] + effective_alpha * curr_pos
                smoothed[i, 2] = curr_score
                # 重置異常計數
                self.anomaly_count[person_id][i] = max(0, self.anomaly_count[person_id][i] - 1)
        
        # 更新歷史速度
        if frame_velocities:
            avg_velocity = np.mean(frame_velocities)
            self.velocity_history[person_id].append(avg_velocity)
            if len(self.velocity_history[person_id]) > 5:
                self.velocity_history[person_id].pop(0)
        
        # 確保輸出沒有 NaN
        smoothed = np.nan_to_num(smoothed, nan=0.0)
        
        # 更新狀態
        self.states[person_id] = smoothed.copy()
        self.prev_keypoints[person_id] = keypoints.copy()
        
        return smoothed
    
    def _filter_unreasonable_positions(
        self, 
        keypoints: np.ndarray, 
        box: Tuple[int, int, int, int] = None
    ) -> np.ndarray:
        """
        過濾不合理的關鍵點位置
        
        Args:
            keypoints: 關鍵點 shape (17, 3)
            box: 邊界框 (x, y, w, h)
            
        Returns:
            過濾後的關鍵點
        """
        filtered = keypoints.copy()
        
        if box is not None:
            bx, by, bw, bh = box
            # 擴展邊界框範圍（允許一定的超出）
            margin = max(bw, bh) * 0.5
            min_x, max_x = bx - margin, bx + bw + margin
            min_y, max_y = by - margin, by + bh + margin
            
            for i in range(len(filtered)):
                x, y, s = filtered[i]
                # 如果點超出擴展邊界框太遠，視為異常
                if x < min_x or x > max_x or y < min_y or y > max_y:
                    filtered[i, 2] = 0  # 將置信度設為 0，後續會被過濾
        
        # 檢查骨骼長度合理性（基於 COCO 骨架）
        # 定義骨骼連接和最大合理長度比例（相對於邊界框對角線）
        bone_pairs = [
            (5, 7), (7, 9),   # 左臂
            (6, 8), (8, 10),  # 右臂
            (11, 13), (13, 15),  # 左腿
            (12, 14), (14, 16),  # 右腿
            (5, 6),  # 肩膀
            (11, 12),  # 臀部
        ]
        
        if box is not None:
            bx, by, bw, bh = box
            diag = np.sqrt(bw**2 + bh**2)
            max_bone_length = diag * 0.8  # 單個骨骼最大長度為對角線的 80%
            
            for p1, p2 in bone_pairs:
                if p1 < len(filtered) and p2 < len(filtered):
                    x1, y1, s1 = filtered[p1]
                    x2, y2, s2 = filtered[p2]
                    
                    if s1 > 0 and s2 > 0:
                        bone_length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                        if bone_length > max_bone_length:
                            # 骨骼長度異常，降低置信度
                            # 保留置信度較高的那個點
                            if s1 < s2:
                                filtered[p1, 2] = 0
                            else:
                                filtered[p2, 2] = 0
        
        # 檢查身體對稱性（左右應該大致對稱）
        # 左右肩膀、左右臀部
        symmetric_pairs = [(5, 6), (11, 12)]
        for left, right in symmetric_pairs:
            if left < len(filtered) and right < len(filtered):
                lx, ly, ls = filtered[left]
                rx, ry, rs = filtered[right]
                
                if ls > 0 and rs > 0:
                    # 左右應該在水平方向上相對，不應該距離太遠
                    if box is not None:
                        bx, by, bw, bh = box
                        # 左右點的垂直距離不應該超過邊界框高度的 50%
                        if abs(ly - ry) > bh * 0.5:
                            if ls < rs:
                                filtered[left, 2] = 0
                            else:
                                filtered[right, 2] = 0
        
        return filtered
    
    def reset(self, person_id: Optional[int] = None):
        """重置平滑狀態"""
        if person_id is None:
            self.states.clear()
            self.prev_keypoints.clear()
        else:
            self.states.pop(person_id, None)
            self.prev_keypoints.pop(person_id, None)


class SkeletonProcessor:
    """骨架資料處理器 - 使用專業的骨架濾波器"""
    
    def __init__(self):
        """初始化骨架處理器"""
        # 原始幀緩衝區（保存最近的原始幀）
        self.raw_buffer: deque = deque(maxlen=config.interpolation.buffer_size)
        
        # 補幀後的序列緩衝區（用於動作識別）
        # 增大緩衝區以支援流暢播放（約 8 秒的 15 FPS）
        self.interpolated_buffer: deque = deque(maxlen=120)
        
        # 使用專業的骨架預處理器（包含 One Euro Filter + 解剖學約束 + Cubic Spline 插值）
        self.preprocessor = SkeletonPreprocessor(
            num_keypoints=config.skeleton.num_keypoints,
            target_fps=config.interpolation.target_fps,
            one_euro_min_cutoff=0.5,  # 針對低 FPS 優化
            one_euro_beta=0.01,       # 針對低 FPS 優化
            confidence_threshold=config.skeleton.confidence_threshold
        )
        
        # 人物追蹤器（簡單的 ID 分配）
        self.person_tracker: Dict[int, PersonSkeleton] = {}
        
        # 補幀計數器
        self.interpolated_frame_count = 0

    def analyze_visibility(self, person_id: int) -> Dict[str, Any]:
        """
        分析指定人物的骨架可見性
        
        Args:
            person_id: 人物 ID
            
        Returns:
            可見性分析結果字典
        """
        # 獲取最新的一幀
        if not self.interpolated_buffer:
            return {
                'upper_visible': 0, 'lower_visible': 0,
                'upper_ratio': 0.0, 'lower_ratio': 0.0,
                'is_sitting_likely': False, 'is_full_body': False
            }
            
        latest_frame = self.interpolated_buffer[-1]
        target_person = None
        for person in latest_frame.persons:
            if person.person_id == person_id:
                target_person = person
                break
        
        if target_person is None:
            return {
                'upper_visible': 0, 'lower_visible': 0,
                'upper_ratio': 0.0, 'lower_ratio': 0.0,
                'is_sitting_likely': False, 'is_full_body': False
            }
            
        keypoints = target_person.get_keypoints(use_smoothed=True)
        
        # 定義上半身和下半身索引
        UPPER_BODY_INDICES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # 頭 + 手臂
        LOWER_BODY_INDICES = [11, 12, 13, 14, 15, 16]  # 髖 + 腿
        
        confidence_threshold = 0.3
        
        # 計算上半身可見點數
        upper_visible = sum(1 for i in UPPER_BODY_INDICES if keypoints[i, 2] >= confidence_threshold)
        
        # 計算下半身可見點數
        lower_visible = sum(1 for i in LOWER_BODY_INDICES if keypoints[i, 2] >= confidence_threshold)
        
        upper_ratio = upper_visible / len(UPPER_BODY_INDICES)
        lower_ratio = lower_visible / len(LOWER_BODY_INDICES)
        
        # 判斷是否可能坐著：上半身可見但下半身幾乎不可見
        is_sitting_likely = (upper_ratio >= 0.5 and lower_ratio < 0.3)
        
        # 判斷是否全身可見
        is_full_body = (upper_ratio >= 0.7 and lower_ratio >= 0.5)
        
        # 計算總可見點數和平均置信度
        visible_mask = keypoints[:, 2] >= confidence_threshold
        visible_count = int(np.sum(visible_mask))
        avg_conf = float(np.mean(keypoints[visible_mask, 2])) if visible_count > 0 else 0.0
        
        # 判斷骨架是否有效 (簡單規則)
        # 至少 5 個點可見，且平均置信度 > 0.4
        is_valid = (visible_count >= 5 and avg_conf >= 0.4)
        
        return {
            'upper_visible': upper_visible,
            'lower_visible': lower_visible,
            'upper_ratio': upper_ratio,
            'lower_ratio': lower_ratio,
            'is_sitting_likely': is_sitting_likely,
            'is_full_body': is_full_body,
            'visible_count': visible_count,
            'avg_conf': avg_conf,
            'is_valid': is_valid
        }

    def get_motion_magnitude(self, person_id: int) -> float:
        """
        計算指定人物的動作幅度
        
        Args:
            person_id: 人物 ID
            
        Returns:
            動作幅度（像素/幀）
        """
        if len(self.interpolated_buffer) < 5:
            return 0.0
            
        # 收集該人物最近的關鍵點序列
        recent_keypoints = []
        # 取最近 20 幀
        frames_to_check = list(self.interpolated_buffer)[-min(20, len(self.interpolated_buffer)):]
        
        for frame in frames_to_check:
            found = False
            for person in frame.persons:
                if person.person_id == person_id:
                    recent_keypoints.append(person.get_keypoints(use_smoothed=True))
                    found = True
                    break
            if not found and recent_keypoints:
                # 如果中間有一幀沒抓到人，中斷或補上一幀？這裡選擇跳過
                pass
        
        if len(recent_keypoints) < 2:
            return 0.0
            
        # 計算每幀之間的平均位移
        total_motion = 0.0
        count = 0
        
        for i in range(1, len(recent_keypoints)):
            prev_kp = recent_keypoints[i-1]
            curr_kp = recent_keypoints[i]
            
            # 只計算可見的關鍵點
            for j in range(17):
                if prev_kp[j, 2] > 0.3 and curr_kp[j, 2] > 0.3:
                    dist = np.linalg.norm(curr_kp[j, :2] - prev_kp[j, :2])
                    total_motion += dist
                    count += 1
        
        if count == 0:
            return 0.0
            
        return total_motion / count
        self.next_person_id: int = 0
        
        # 最後處理的時間戳
        self.last_frame_time: float = 0.0
        
        # 統計
        self.interpolated_frame_count: int = 0
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[SkeletonProcessor][{time.time():.3f}] {msg}")
    
    def process_frame(self, frame_data: FrameData) -> Optional[SkeletonFrame]:
        """
        處理一幀資料，提取骨架資訊
        
        Args:
            frame_data: 從串口接收的幀資料
            
        Returns:
            處理後的骨架幀，如果沒有檢測到人則返回 None
        """
        if not frame_data.keypoints:
            return SkeletonFrame(
                timestamp=frame_data.timestamp,
                frame_no=frame_data.frame_no,
                persons=[]
            )
        
        persons = []
        interpolated_persons_list = []  # 儲存每個人的插值幀
        
        for idx, person_data in enumerate(frame_data.keypoints):
            if not person_data or len(person_data) < 1:
                continue
            
            # 解析邊界框 [x, y, w, h, score, target]
            box_data = person_data[0]
            if len(box_data) < 6:
                continue
                
            x, y, w, h, score, target = box_data[:6]
            box = (int(x), int(y), int(w), int(h))
            
            # 解析關鍵點
            keypoints = self._parse_keypoints(person_data[1:])
            
            if keypoints is not None:
                # 過濾掉沒有足夠有效關鍵點的檢測（可能是誤檢）
                # 即使有邊界框，如果沒有骨架點，也應該忽略
                valid_count = np.sum(keypoints[:, 2] > config.skeleton.confidence_threshold)
                if valid_count < 5:  # 至少要有 3 個有效點才視為有效人物
                    continue
                
                # 使用專業的預處理器（One Euro Filter + 解剖學約束）
                smoothed_keypoints, interp_frames = self.preprocessor.process_frame(
                    person_id=idx,
                    keypoints=keypoints,
                    timestamp=frame_data.timestamp,
                    bbox=box
                )
                
                person = PersonSkeleton(
                    person_id=idx,
                    box=box,
                    score=float(score),
                    keypoints=keypoints.copy(),  # 保存原始關鍵點
                    timestamp=frame_data.timestamp,
                    smoothed_keypoints=smoothed_keypoints  # 保存平滑後的關鍵點
                )
                persons.append(person)
                interpolated_persons_list.append((idx, box, float(score), interp_frames))
        
        if not persons:
            return SkeletonFrame(
                timestamp=frame_data.timestamp,
                frame_no=frame_data.frame_no,
                persons=[]
            )
        
        skeleton_frame = SkeletonFrame(
            timestamp=frame_data.timestamp,
            frame_no=frame_data.frame_no,
            persons=persons
        )
        
        # 加入原始緩衝區
        self.raw_buffer.append(skeleton_frame)
        
        # 處理插值幀（由預處理器生成）
        self._add_interpolated_frames(interpolated_persons_list, frame_data.timestamp, frame_data.frame_no)
        
        return skeleton_frame
    
    def _add_interpolated_frames(
        self, 
        interpolated_persons_list: List[Tuple[int, Tuple, float, List[np.ndarray]]],
        base_timestamp: float,
        frame_no: int
    ):
        """
        將預處理器生成的插值幀加入緩衝區
        """
        if not interpolated_persons_list:
            return
        
        # 找出最多的插值幀數
        max_frames = max(len(frames) for _, _, _, frames in interpolated_persons_list) if interpolated_persons_list else 0
        
        if max_frames == 0:
            return
        
        self.debug_log(f"Adding {max_frames} interpolated frames from preprocessor")
        
        for frame_idx in range(max_frames):
            interp_persons = []
            
            for person_id, box, score, frames in interpolated_persons_list:
                if frame_idx < len(frames):
                    interp_kpts = frames[frame_idx]
                    
                    interp_person = PersonSkeleton(
                        person_id=person_id,
                        box=box,
                        score=score,
                        keypoints=interp_kpts,  # 插值幀沒有真正的原始資料
                        timestamp=base_timestamp,
                        smoothed_keypoints=interp_kpts
                    )
                    interp_persons.append(interp_person)
            
            if interp_persons:
                interp_frame = SkeletonFrame(
                    timestamp=base_timestamp,
                    frame_no=frame_no,
                    persons=interp_persons
                )
                self.interpolated_buffer.append(interp_frame)
                self.interpolated_frame_count += 1
    
    def _parse_keypoints(self, kpts_data: List[Any]) -> Optional[np.ndarray]:
        """
        解析關鍵點資料
        
        Args:
            kpts_data: 關鍵點資料列表
            
        Returns:
            shape (17, 3) 的 numpy 陣列，或 None
        """
        keypoints = np.zeros((config.skeleton.num_keypoints, 3), dtype=np.float32)
        
        for i, kp in enumerate(kpts_data):
            if i >= config.skeleton.num_keypoints:
                break
                
            # 處理可能的雙重嵌套
            if len(kp) == 1 and isinstance(kp[0], list):
                kp = kp[0]
            
            if len(kp) >= 4:
                kp_x, kp_y, kp_s, kp_t = kp[:4]
                keypoints[i] = [float(kp_x), float(kp_y), float(kp_s)]
        
        return keypoints
    
    def _interpolate_frames(self):
        """
        執行補幀操作
        
        將低 FPS 的原始幀插值為較高 FPS 的序列
        """
        if len(self.raw_buffer) < 2:
            return
        
        # 取最近兩幀進行插值
        prev_frame = self.raw_buffer[-2]
        curr_frame = self.raw_buffer[-1]
        
        time_diff = curr_frame.timestamp - prev_frame.timestamp
        
        if time_diff <= 0:
            return
        
        # 計算需要插入的幀數
        target_interval = 1.0 / config.interpolation.target_fps
        num_interp_frames = int(time_diff / target_interval)
        
        if num_interp_frames <= 1:
            # 時間差太小，直接加入當前幀
            self._add_to_interpolated_buffer(curr_frame)
            return
        
        # 限制最大補幀數量
        num_interp_frames = min(num_interp_frames, 30)
        
        self.debug_log(f"Interpolating {num_interp_frames} frames (time_diff={time_diff:.3f}s)")
        
        # 對每個人物進行插值
        for i in range(1, num_interp_frames + 1):
            t = i / num_interp_frames
            interp_timestamp = prev_frame.timestamp + t * time_diff
            
            interp_persons = self._interpolate_persons(
                prev_frame.persons, 
                curr_frame.persons, 
                t
            )
            
            interp_frame = SkeletonFrame(
                timestamp=interp_timestamp,
                frame_no=prev_frame.frame_no,  # 使用前一幀的編號
                persons=interp_persons
            )
            
            self._add_to_interpolated_buffer(interp_frame)
            self.interpolated_frame_count += 1
    
    def _interpolate_persons(
        self, 
        prev_persons: List[PersonSkeleton], 
        curr_persons: List[PersonSkeleton], 
        t: float
    ) -> List[PersonSkeleton]:
        """
        對人物骨架進行平滑插值
        
        Args:
            prev_persons: 前一幀的人物列表
            curr_persons: 當前幀的人物列表
            t: 插值係數 (0.0 到 1.0)
            
        Returns:
            插值後的人物列表
        """
        if config.interpolation.interpolation_method == "copy":
            # 簡單複製模式：直接使用前一幀或當前幀
            return prev_persons if t < 0.5 else curr_persons
        
        # 使用平滑的 Hermite 插值（smoothstep）減少突兀感
        # smoothstep: t_smooth = 3t^2 - 2t^3
        t_smooth = t * t * (3 - 2 * t)
        
        interp_persons = []
        
        # 簡單匹配：根據索引配對（可以改進為根據位置或 ID 匹配）
        for i, prev_person in enumerate(prev_persons):
            if i < len(curr_persons):
                curr_person = curr_persons[i]
                
                # 使用平滑後的關鍵點進行插值
                prev_kp = prev_person.get_keypoints(use_smoothed=True)
                curr_kp = curr_person.get_keypoints(use_smoothed=True)
                interp_keypoints = (1 - t_smooth) * prev_kp + t_smooth * curr_kp
                
                # 平滑插值邊界框
                px, py, pw, ph = prev_person.box
                cx, cy, cw, ch = curr_person.box
                interp_box = (
                    int((1 - t_smooth) * px + t_smooth * cx),
                    int((1 - t_smooth) * py + t_smooth * cy),
                    int((1 - t_smooth) * pw + t_smooth * cw),
                    int((1 - t_smooth) * ph + t_smooth * ch)
                )
                
                # 插值幀：keypoints 和 smoothed_keypoints 都設為插值結果
                interp_person = PersonSkeleton(
                    person_id=prev_person.person_id,
                    box=interp_box,
                    score=(1 - t_smooth) * prev_person.score + t_smooth * curr_person.score,
                    keypoints=interp_keypoints,  # 插值幀沒有真正的原始資料
                    timestamp=0.0,  # 會在外層設置
                    smoothed_keypoints=interp_keypoints  # 插值結果也作為平滑值
                )
                interp_persons.append(interp_person)
            else:
                # 沒有對應的當前幀人物，使用前一幀
                interp_persons.append(prev_person)
        
        return interp_persons
    
    def _add_to_interpolated_buffer(self, frame: SkeletonFrame):
        """將幀加入補幀緩衝區"""
        self.interpolated_buffer.append(frame)
    
    def get_skeleton_sequence(self, person_idx: int = 0) -> Optional[np.ndarray]:
        """
        獲取指定人物的骨架序列（用於 MMAction2）
        
        Args:
            person_idx: 人物索引
            
        Returns:
            shape (T, V, C) 的骨架序列，T=幀數, V=關鍵點數, C=坐標維度(3)
            如果資料不足則返回 None
        """
        if len(self.interpolated_buffer) < config.interpolation.sequence_length:
            self.debug_log(f"Not enough frames: {len(self.interpolated_buffer)}/{config.interpolation.sequence_length}")
            return None
        
        # 取最近的 sequence_length 幀
        frames = list(self.interpolated_buffer)[-config.interpolation.sequence_length:]
        
        # 建構序列陣列
        sequence = np.zeros(
            (config.interpolation.sequence_length, config.skeleton.num_keypoints, 3),
            dtype=np.float32
        )
        
        for t, frame in enumerate(frames):
            if person_idx < len(frame.persons):
                sequence[t] = frame.persons[person_idx].keypoints
            elif frame.persons:
                # 如果指定的人不存在，使用第一個人
                sequence[t] = frame.persons[0].keypoints
        
        return sequence
    
    def get_all_skeleton_sequences(self) -> Dict[int, np.ndarray]:
        """
        獲取所有人物的骨架序列
        
        Returns:
            字典，鍵為人物 ID，值為骨架序列
        """
        if len(self.interpolated_buffer) < config.interpolation.sequence_length:
            return {}
        
        # 找出所有出現過的人物 ID
        all_person_ids = set()
        frames = list(self.interpolated_buffer)[-config.interpolation.sequence_length:]
        
        for frame in frames:
            for person in frame.persons:
                all_person_ids.add(person.person_id)
        
        # 為每個人物建構序列
        sequences = {}
        for person_id in all_person_ids:
            sequence = np.zeros(
                (config.interpolation.sequence_length, config.skeleton.num_keypoints, 3),
                dtype=np.float32
            )
            
            for t, frame in enumerate(frames):
                # 尋找對應的人物
                for person in frame.persons:
                    if person.person_id == person_id:
                        sequence[t] = person.keypoints
                        break
            
            sequences[person_id] = sequence
        
        return sequences
    
    def get_latest_frame(self) -> Optional[SkeletonFrame]:
        """獲取最新的骨架幀"""
        if self.raw_buffer:
            return self.raw_buffer[-1]
        return None
    
    def get_latest_interpolated_frame(self) -> Optional[SkeletonFrame]:
        """獲取最新的補幀骨架幀"""
        if self.interpolated_buffer:
            return self.interpolated_buffer[-1]
        return None
    
    def get_interpolated_frames(self) -> List[SkeletonFrame]:
        """
        獲取補幀緩衝區中的所有骨架幀（用於流暢播放）
        
        Returns:
            補幀骨架幀列表的副本
        """
        return list(self.interpolated_buffer)
    
    def get_buffer_status(self) -> Dict[str, int]:
        """獲取緩衝區狀態"""
        return {
            "raw_frames": len(self.raw_buffer),
            "interpolated_frames": len(self.interpolated_buffer),
            "total_interpolated": self.interpolated_frame_count,
            "sequence_ready": len(self.interpolated_buffer) >= config.interpolation.sequence_length
        }
    
    def clear(self):
        """清空所有緩衝區"""
        self.raw_buffer.clear()
        self.interpolated_buffer.clear()
        self.person_tracker.clear()
        self.preprocessor.reset()  # 使用新的預處理器
        self.interpolated_frame_count = 0



