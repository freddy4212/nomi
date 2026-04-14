"""
processor.py - 骨架資料處理與補幀模組

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
    from ...config import config
    from .filters import SkeletonPreprocessor
except ImportError:
    from observation_layer.config import config
    from observation_layer.modules.skeleton.filters import SkeletonPreprocessor


@dataclass
class PersonSkeleton:
    """單一人物的骨架資料"""
    person_id: int  # 人物 ID（來自追蹤）
    box: Tuple[int, int, int, int]  # (x, y, w, h) 邊界框
    score: float  # 檢測信心度
    keypoints: np.ndarray  # shape: (17, 3) - (x, y, score) - 原始關鍵點
    timestamp: float  # 時間戳
    smoothed_keypoints: Optional[np.ndarray] = None  # 平滑後的關鍵點（用於補幀和動作識別）
    reid_vector: Optional[np.ndarray] = None  # ReID 特徵向量
    is_visible: bool = True  # 人物是否在畫面中
    last_seen_time: float = 0.0  # 最後一次被偵測到的時間戳
    disappear_direction: Optional[str] = None  # 消失方向 (left, right, top, bottom)
    _visibility_event_sent: bool = False  # 內部標記：是否已發送離開事件
    
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
    environment: Dict[str, Any] = field(default_factory=dict)


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
            # 修改：降低閾值以包含更多點 (0.3 -> 0.1)
            if (curr_pos[0] == 0 and curr_pos[1] == 0) or curr_score < 0.1:
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
            confidence_threshold=0.1, # 降低閾值以包含更多點 (Reverted to 0.1 to match we_mma_2)
        )
        
        # 時間戳平滑狀態 (解決網路突發傳輸導致的 Jitter)
        self._last_stable_time = 0.0
        self._last_frame_no = -1
        
        # 人物追蹤器（簡單的 ID 分配）
        self.person_tracker: Dict[int, PersonSkeleton] = {}
        
        # ID 映射：將 Sender 的追蹤 ID 映射為從 0 開始的連續本地 ID
        self._sender_to_local_id: Dict[int, int] = {}
        self._next_local_id: int = 0
        
        # 離開偵測配置
        self.disappear_timeout: float = 1.5  # 超過 1.5 秒未偵測到即視為離開
        self.remove_timeout: float = 30.0  # 超過 30 秒後從追蹤器中移除
        
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
        # COCO 格式: 0=鼻子, 1-4=眼睛耳朵, 5-10=肩膀手肘手腕, 11-12=髖部, 13-14=膝蓋, 15-16=腳踝
        UPPER_BODY_INDICES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # 頭 + 手臂
        LOWER_BODY_INDICES = [11, 12, 13, 14, 15, 16]  # 髖 + 腿
        
        confidence_threshold = 0.3
        
        # 計算上半身可見點數
        upper_visible = sum(1 for i in UPPER_BODY_INDICES if keypoints[i, 2] >= confidence_threshold)
        
        # 計算下半身可見點數
        lower_visible = sum(1 for i in LOWER_BODY_INDICES if keypoints[i, 2] >= confidence_threshold)
        
        upper_ratio = upper_visible / len(UPPER_BODY_INDICES)
        lower_ratio = lower_visible / len(LOWER_BODY_INDICES)
        
        # === 基於骨架幾何的坐姿判斷 ===
        is_sitting_likely = False
        
        # 方法 1: 下半身不可見（被桌子等遮擋）
        if upper_ratio >= 0.5 and lower_ratio < 0.6:
            is_sitting_likely = True
        
        # 方法 2: 基於關鍵點位置判斷（髖、膝、踝的相對位置）
        # 坐著時，膝蓋和髖部的 Y 座標差距會比站著小很多
        # 索引: 11=左髖, 12=右髖, 13=左膝, 14=右膝, 15=左踝, 16=右踝
        if not is_sitting_likely and lower_ratio >= 0.5:
            left_hip = keypoints[11]
            right_hip = keypoints[12]
            left_knee = keypoints[13]
            right_knee = keypoints[14]
            left_ankle = keypoints[15]
            right_ankle = keypoints[16]
            
            # 檢查關鍵點是否有效
            hip_valid = left_hip[2] >= confidence_threshold or right_hip[2] >= confidence_threshold
            knee_valid = left_knee[2] >= confidence_threshold or right_knee[2] >= confidence_threshold
            ankle_valid = left_ankle[2] >= confidence_threshold or right_ankle[2] >= confidence_threshold
            
            if hip_valid and knee_valid:
                # 計算平均髖部和膝蓋 Y 座標
                hip_y = 0
                hip_count = 0
                if left_hip[2] >= confidence_threshold:
                    hip_y += left_hip[1]
                    hip_count += 1
                if right_hip[2] >= confidence_threshold:
                    hip_y += right_hip[1]
                    hip_count += 1
                hip_y = hip_y / hip_count if hip_count > 0 else 0
                
                knee_y = 0
                knee_count = 0
                if left_knee[2] >= confidence_threshold:
                    knee_y += left_knee[1]
                    knee_count += 1
                if right_knee[2] >= confidence_threshold:
                    knee_y += right_knee[1]
                    knee_count += 1
                knee_y = knee_y / knee_count if knee_count > 0 else 0
                
                # 計算頭部 Y 座標（鼻子或肩膀作為備選）
                nose_y = keypoints[0][1] if keypoints[0][2] >= confidence_threshold else 0
                if nose_y == 0:
                    # 嘗試用肩膀平均值
                    left_shoulder = keypoints[5]
                    right_shoulder = keypoints[6]
                    if left_shoulder[2] >= confidence_threshold:
                        nose_y = left_shoulder[1]
                    elif right_shoulder[2] >= confidence_threshold:
                        nose_y = right_shoulder[1]
                
                # 坐著時，髖部到膝蓋的距離會很小（接近水平）
                # 站著時，髖部到膝蓋會有明顯的垂直距離
                hip_knee_dist = abs(knee_y - hip_y)
                
                # 計算身體總高度（頭到髖的距離）作為參考
                body_height = abs(hip_y - nose_y) if nose_y > 0 else 100
                
                # 正規化：坐著時 hip_knee_ratio 通常 < 0.5，站著時 > 0.6
                hip_knee_ratio = hip_knee_dist / body_height if body_height > 0 else 0
                
                # 新增：大腿水平判斷 (Thigh Horizontal Check)
                is_thigh_horizontal = False
                if hip_valid and knee_valid:
                    # 左大腿
                    if left_hip[2] >= confidence_threshold and left_knee[2] >= confidence_threshold:
                        l_dx = abs(left_knee[0] - left_hip[0])
                        l_dy = abs(left_knee[1] - left_hip[1])
                        if l_dx > l_dy * 1.0:
                            is_thigh_horizontal = True
                    # 右大腿
                    if not is_thigh_horizontal and right_hip[2] >= confidence_threshold and right_knee[2] >= confidence_threshold:
                        r_dx = abs(right_knee[0] - right_hip[0])
                        r_dy = abs(right_knee[1] - right_hip[1])
                        if r_dx > r_dy * 1.0:
                            is_thigh_horizontal = True

                # 另外檢查膝蓋的彎曲
                if ankle_valid and knee_count > 0:
                    ankle_y = 0
                    ankle_count = 0
                    if left_ankle[2] >= confidence_threshold:
                        ankle_y += left_ankle[1]
                        ankle_count += 1
                    if right_ankle[2] >= confidence_threshold:
                        ankle_y += right_ankle[1]
                        ankle_count += 1
                    ankle_y = ankle_y / ankle_count if ankle_count > 0 else 0
                    
                    knee_ankle_dist = abs(ankle_y - knee_y)
                    
                    if hip_knee_ratio < 0.55 and knee_ankle_dist < body_height * 0.55:
                        is_sitting_likely = True
                    elif hip_knee_ratio < 0.35:
                        is_sitting_likely = True
                    elif is_thigh_horizontal:
                        is_sitting_likely = True
                        
                elif hip_knee_ratio < 0.45:
                    is_sitting_likely = True
                elif is_thigh_horizontal:
                    is_sitting_likely = True
                
                # === 強制站立檢查 ===
                if hip_knee_ratio > 0.7:
                    is_sitting_likely = False
        
        # 方法 3: 基於邊界框比例判斷
        if not is_sitting_likely and target_person.box is not None:
            x, y, w, h = target_person.box
            if w > 0:
                aspect_ratio = h / w
                # 放寬高寬比閾值 (1.2 -> 1.35)，適應坐姿挺直的情況
                if aspect_ratio < 1.35:
                    if lower_ratio < 0.6:
                        is_sitting_likely = True
                    elif aspect_ratio < 1.0:
                        is_sitting_likely = True
        
        # 判斷是否全身可見
        is_full_body = (upper_ratio >= 0.7 and lower_ratio >= 0.7)
        
        # 計算總可見點數和平均置信度
        visible_mask = keypoints[:, 2] >= confidence_threshold
        visible_count = int(np.sum(visible_mask))
        avg_conf = float(np.mean(keypoints[visible_mask, 2])) if visible_count > 0 else 0.0
        
        # 判斷骨架是否有效 (簡單規則)
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
        計算指定人物的動作幅度（歸一化後的位移）
        
        Args:
            person_id: 人物 ID
            
        Returns:
            動作幅度（歸一化單位/幀）
        """
        if len(self.interpolated_buffer) < 5:
            return 0.0
            
        # 收集該人物最近的關鍵點序列
        recent_keypoints = []
        # 取最近 15 幀（約 1 秒）
        frames_to_check = list(self.interpolated_buffer)[-min(15, len(self.interpolated_buffer)):]
        
        target_person_latest = None
        for frame in frames_to_check:
            for person in frame.persons:
                if person.person_id == person_id:
                    recent_keypoints.append(person.get_keypoints(use_smoothed=True))
                    target_person_latest = person
                    break
        
        if len(recent_keypoints) < 2 or target_person_latest is None:
            return 0.0
            
        # 獲取邊界框大小用於歸一化（解決遠近問題）
        _, _, w, h = target_person_latest.box
        bbox_diag = np.sqrt(w**2 + h**2)
        if bbox_diag < 10: bbox_diag = 100.0
            
        # 定義穩定點 (肩膀、臀部、中心)
        STABLE_POINTS = [5, 6, 11, 12]
        
        # 計算每幀之間的平均位移
        total_motion = 0.0
        count = 0
        
        for i in range(1, len(recent_keypoints)):
            prev_kp = recent_keypoints[i-1]
            curr_kp = recent_keypoints[i]
            
            # 計算這一幀的位移
            frame_motion = 0.0
            frame_count = 0
            
            for j in range(17):
                if prev_kp[j, 2] > 0.3 and curr_kp[j, 2] > 0.3:
                    dist = np.linalg.norm(curr_kp[j, :2] - prev_kp[j, :2])
                    
                    # 穩定點權重較高，末梢點權重較低（減少雜訊影響）
                    weight = 2.0 if j in STABLE_POINTS else 0.5
                    frame_motion += dist * weight
                    frame_count += weight
            
            if frame_count > 0:
                # 歸一化：位移相對於人體大小 (百分比)
                normalized_motion = (frame_motion / frame_count) / bbox_diag * 1000
                total_motion += normalized_motion
                count += 1
        
        if count == 0:
            return 0.0
            
        return total_motion / count
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[SkeletonProcessor][{time.time():.3f}] {msg}")
    
    def process_frame(self, frame_data: Any) -> Optional[SkeletonFrame]:
        """
        處理一幀資料，提取骨架資訊
        
        Args:
            frame_data: 從網路接收的幀資料
            
        Returns:
            處理後的骨架幀，如果沒有檢測到人則返回 None
        """
        if not frame_data.keypoints:
            # 沒有偵測到任何人，更新所有追蹤中的人為不可見
            self._update_invisible_persons(frame_data.timestamp, set())
            empty_frame = SkeletonFrame(
                timestamp=frame_data.timestamp,
                frame_no=frame_data.frame_no,
                persons=[],
                environment=frame_data.environment
            )
            # 將空幀加入 interpolated_buffer
            self._add_to_interpolated_buffer(empty_frame)
            # 重設 ID 映射（沒有人時重新從 0 開始）
            self._sender_to_local_id.clear()
            self._next_local_id = 0
            return empty_frame
        
        # === 時間戳平滑處理 ===
        # 解決網路突發傳輸 (Burst) 導致多幀在極短時間內到達，
        # 造成 OneEuroFilter 計算出極大速度而失效的問題
        current_time = frame_data.timestamp
        frame_no = frame_data.frame_no
        timestamp_to_use = current_time
        
        if self._last_frame_no < 0:
            self._last_frame_no = frame_no
            self._last_stable_time = current_time
        else:
            frame_diff = frame_no - self._last_frame_no
            # 如果幀號亂跳、重置或間隔太大，則重置平滑狀態
            # 因應 Simulator 可能每次都斷線並重送 Frame 0，這裡放寬條件
            if frame_no == 0 and frame_diff <= 0:
                 # 偵測到模擬器重新啟動或 Frame No 重置，強制前進時間戳
                 # 這樣可以讓 Interpolation 認為這是一個新的有效幀，而不是重複或過舊的幀
                 timestamp_to_use = self._last_stable_time + 0.1
                 self._last_frame_no = frame_no
                 self._last_stable_time = timestamp_to_use
            elif frame_diff < 0 or frame_diff > 10:
                 self._last_frame_no = frame_no
                 self._last_stable_time = current_time
            else:
                 time_diff = current_time - self._last_stable_time
                 # 強制最小時間間隔：每幀至少 0.1 秒 (假設 source fps ~1.5，間隔應為 0.66s)
                 # 這樣可以避免突發傳輸導致的極小 dt
                 min_dt = 0.1 * frame_diff 
                 
                 if time_diff < min_dt:
                     # 接收太快，使用平滑後的時間
                     timestamp_to_use = self._last_stable_time + min_dt
                 else:
                     timestamp_to_use = current_time
                     
                 self._last_stable_time = timestamp_to_use
                 self._last_frame_no = frame_no
        
        persons = []
        interpolated_persons_list = []
        detected_person_ids = set()
        current_sender_ids = set()
        
        for idx, person_data in enumerate(frame_data.keypoints):
            if not person_data or len(person_data) < 1:
                continue
            
            # 解析邊界框 [x, y, w, h, score, target]
            box_data = person_data[0]
            if len(box_data) < 6:
                continue
                
            x, y, w, h, score, target = box_data[:6]
            box = (int(x), int(y), int(w), int(h))
            
            # Sender 傳來的原始追蹤 ID
            sender_id = int(target) if target >= 0 else idx
            current_sender_ids.add(sender_id)
            
            # 將 Sender ID 映射為本地 ID（從 0 開始）
            if sender_id not in self._sender_to_local_id:
                self._sender_to_local_id[sender_id] = self._next_local_id
                self._next_local_id += 1
            person_id = self._sender_to_local_id[sender_id]
            
            # 獲取對應的 ReID 向量
            reid_vector = None
            if hasattr(frame_data, 'reid_results') and idx < len(frame_data.reid_results):
                reid_vector = frame_data.reid_results[idx]
                if reid_vector is not None:
                    reid_vector = np.array(reid_vector, dtype=np.float32)
            
            # 解析關鍵點
            keypoints = self._parse_keypoints(person_data[1:])
            
            if keypoints is not None:
                # 過濾掉沒有足夠有效關鍵點的檢測
                valid_count = np.sum(keypoints[:, 2] > config.skeleton.confidence_threshold)
                if valid_count < 5:
                    continue
                
                # 使用專業的預處理器
                smoothed_keypoints, interp_frames = self.preprocessor.process_frame(
                    person_id=person_id,
                    keypoints=keypoints,
                    timestamp=timestamp_to_use, # 使用平滑後的時間戳
                    bbox=box
                )
                
                person = PersonSkeleton(
                    person_id=person_id,
                    box=box,
                    score=float(score),
                    keypoints=keypoints.copy(),
                    timestamp=timestamp_to_use, # 使用平滑後的時間戳
                    smoothed_keypoints=smoothed_keypoints,
                    reid_vector=reid_vector,
                    is_visible=True,
                    last_seen_time=timestamp_to_use # 使用平滑後的時間戳
                )
                persons.append(person)
                detected_person_ids.add(person_id)
                interpolated_persons_list.append((person_id, box, float(score), interp_frames, reid_vector))
                
                # 更新人物追蹤器狀態
                self.person_tracker[person_id] = person
        
        # 清理已離開的人的 ID 映射
        stale_sender_ids = [sid for sid in self._sender_to_local_id if sid not in current_sender_ids]
        for sid in stale_sender_ids:
            del self._sender_to_local_id[sid]
        
        # 如果所有人都離開了，重設 ID 計數器
        if len(self._sender_to_local_id) == 0:
            self._next_local_id = 0
        
        # 更新未偵測到的人物狀態
        self._update_invisible_persons(frame_data.timestamp, detected_person_ids)
        
        if not persons:
            empty_frame = SkeletonFrame(
                timestamp=frame_data.timestamp,
                frame_no=frame_data.frame_no,
                persons=[],
                environment=frame_data.environment
            )
            self._add_to_interpolated_buffer(empty_frame)
            self._sender_to_local_id.clear()
            self._next_local_id = 0
            return empty_frame
        
        skeleton_frame = SkeletonFrame(
            timestamp=frame_data.timestamp,
            frame_no=frame_data.frame_no,
            persons=persons,
            environment=frame_data.environment
        )
        
        # 加入原始緩衝區
        self.raw_buffer.append(skeleton_frame)
        
        # 處理插值幀
        self._add_interpolated_frames(interpolated_persons_list, frame_data.timestamp, frame_data.frame_no, environment=frame_data.environment)
        
        return skeleton_frame
    
    def _add_interpolated_frames(
        self, 
        interpolated_persons_list: List[Tuple[int, Tuple, float, List[np.ndarray], Optional[np.ndarray]]],
        base_timestamp: float,
        frame_no: int,
        environment: Dict[str, Any] = None
    ):
        """將預處理器生成的插值幀加入緩衝區"""
        if not interpolated_persons_list:
            return
        
        # 找出最多的插值幀數
        max_frames = max(len(frames) for _, _, _, frames, _ in interpolated_persons_list) if interpolated_persons_list else 0
        
        if max_frames == 0:
            return
        
        # 計算每幀的時間間隔 (目標 30 FPS 輸出)
        frame_interval = 1.0 / 30.0
        
        for frame_idx in range(max_frames):
            interp_persons = []
            
            # 給每個補幀一個遞增的 timestamp，避免被 player 過濾掉
            frame_timestamp = base_timestamp + (frame_idx * frame_interval)
            
            for person_id, box, score, frames, reid_vector in interpolated_persons_list:
                if frame_idx < len(frames):
                    interp_kpts = frames[frame_idx]
                    
                    interp_person = PersonSkeleton(
                        person_id=person_id,
                        box=box,
                        score=score,
                        keypoints=interp_kpts,
                        timestamp=frame_timestamp,
                        smoothed_keypoints=interp_kpts,
                        reid_vector=reid_vector
                    )
                    interp_persons.append(interp_person)
            
            if interp_persons:
                interp_frame = SkeletonFrame(
                    timestamp=frame_timestamp,
                    frame_no=frame_no,
                    persons=interp_persons,
                    environment=environment or {}
                )
                self.interpolated_buffer.append(interp_frame)
                self.interpolated_frame_count += 1
    
    def _parse_keypoints(self, kpts_data: List[Any]) -> Optional[np.ndarray]:
        """解析關鍵點資料"""
        keypoints = np.zeros((config.skeleton.num_keypoints, 3), dtype=np.float32)
        
        for i, kp in enumerate(kpts_data):
            if i >= config.skeleton.num_keypoints:
                break
                
            # 處理可能的雙重嵌套
            if len(kp) == 1 and isinstance(kp[0], list):
                kp = kp[0]
            
            if len(kp) >= 4:
                kp_x, kp_y, kp_s, kp_t = kp[:4]
                # Check if score is > 1.0 (e.g. 0-100 range)
                s_val = float(kp_s)
                if s_val > 1.0:
                    s_val = s_val / 100.0
                keypoints[i] = [float(kp_x), float(kp_y), s_val]
        
        return keypoints
    
    def _add_to_interpolated_buffer(self, frame: SkeletonFrame):
        """將幀加入補幀緩衝區"""
        self.interpolated_buffer.append(frame)
    
    def get_skeleton_sequence(self, person_idx: int = 0) -> Optional[np.ndarray]:
        """獲取指定人物的骨架序列"""
        if len(self.interpolated_buffer) < config.interpolation.sequence_length:
            self.debug_log(f"Not enough frames: {len(self.interpolated_buffer)}/{config.interpolation.sequence_length}")
            return None
        
        frames = list(self.interpolated_buffer)[-config.interpolation.sequence_length:]
        
        sequence = np.zeros(
            (config.interpolation.sequence_length, config.skeleton.num_keypoints, 3),
            dtype=np.float32
        )
        
        for t, frame in enumerate(frames):
            if person_idx < len(frame.persons):
                sequence[t] = frame.persons[person_idx].keypoints
            elif frame.persons:
                sequence[t] = frame.persons[0].keypoints
        
        return sequence
    
    def get_all_skeleton_sequences(self) -> Dict[int, np.ndarray]:
        """獲取所有人物的骨架序列"""
        if len(self.interpolated_buffer) < config.interpolation.sequence_length:
            return {}
        
        # 使用 person_tracker 獲取所有可見人物，而不是只看最後一幀
        # 這可以避免因補幀數量不一致導致某人在最後一幀缺失而被忽略的問題
        current_person_ids = self.get_visible_persons()
        
        frames = list(self.interpolated_buffer)[-config.interpolation.sequence_length:]
        
        sequences = {}
        for person_id in current_person_ids:
            sequence = np.zeros(
                (config.interpolation.sequence_length, config.skeleton.num_keypoints, 3),
                dtype=np.float32
            )
            
            last_valid_kpts = None
            found_any = False
            
            for t, frame in enumerate(frames):
                found_in_frame = False
                for person in frame.persons:
                    if person.person_id == person_id:
                        sequence[t] = person.keypoints
                        last_valid_kpts = person.keypoints
                        found_in_frame = True
                        found_any = True
                        break
                
                # 如果該幀缺失該人物（例如補幀長度不一），使用上一次的有效骨架填補
                if not found_in_frame and last_valid_kpts is not None:
                    sequence[t] = last_valid_kpts
            
            if found_any:
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
        """獲取補幀緩衝區中的所有骨架幀"""
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
        self.preprocessor.reset()
        self.interpolated_frame_count = 0
    
    def _update_invisible_persons(self, current_time: float, detected_ids: set):
        """更新未偵測到的人物狀態"""
        persons_to_remove = []
        
        for person_id, person in self.person_tracker.items():
            if person_id not in detected_ids:
                time_since_seen = current_time - person.last_seen_time
                
                if person.is_visible:
                    if time_since_seen >= self.disappear_timeout:
                        person.is_visible = False
                        
                        x, y, w, h = person.box
                        cx, cy = x + w // 2, y + h // 2
                        
                        frame_w, frame_h = 640, 480
                        
                        if cx < frame_w * 0.2:
                            person.disappear_direction = "left"
                        elif cx > frame_w * 0.8:
                            person.disappear_direction = "right"
                        elif cy < frame_h * 0.2:
                            person.disappear_direction = "top"
                        elif cy > frame_h * 0.8:
                            person.disappear_direction = "bottom"
                        else:
                            person.disappear_direction = "unknown"
                        
                        self.debug_log(f"Person {person_id} disappeared to {person.disappear_direction} (timeout: {time_since_seen:.1f}s)")
                
                if time_since_seen >= self.remove_timeout:
                    persons_to_remove.append(person_id)
                    self.debug_log(f"Person {person_id} removed from tracker (unseen for {time_since_seen:.1f}s)")
        
        for person_id in persons_to_remove:
            del self.person_tracker[person_id]
    
    def get_visible_persons(self) -> List[int]:
        """獲取當前可見的人物 ID 列表"""
        return [pid for pid, p in self.person_tracker.items() if p.is_visible]
    
    def get_invisible_persons(self) -> List[Tuple[int, str, Tuple[int, int, int, int]]]:
        """獲取當前不可見但仍在追蹤中的人物資訊"""
        return [
            (pid, p.disappear_direction, p.box) 
            for pid, p in self.person_tracker.items() 
            if not p.is_visible
        ]
