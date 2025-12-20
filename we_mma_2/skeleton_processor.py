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
            confidence_threshold=0.1, # 降低閾值以包含更多點
        )
        
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
        if upper_ratio >= 0.5 and lower_ratio < 0.5:
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
                # 修正：收緊閾值，避免站立被誤判為坐著
                hip_knee_ratio = hip_knee_dist / body_height if body_height > 0 else 0
                
                # 新增：大腿水平判斷 (Thigh Horizontal Check)
                # 如果大腿的水平距離大於垂直距離的一定比例，表示大腿是平放的（坐姿）
                # 計算左右大腿的投影
                is_thigh_horizontal = False
                if hip_valid and knee_valid:
                    # 左大腿
                    if left_hip[2] >= confidence_threshold and left_knee[2] >= confidence_threshold:
                        l_dx = abs(left_knee[0] - left_hip[0])
                        l_dy = abs(left_knee[1] - left_hip[1])
                        if l_dx > l_dy * 1.0: # 嚴格化：水平分量必須大於垂直分量
                            is_thigh_horizontal = True
                    # 右大腿
                    if not is_thigh_horizontal and right_hip[2] >= confidence_threshold and right_knee[2] >= confidence_threshold:
                        r_dx = abs(right_knee[0] - right_hip[0])
                        r_dy = abs(right_knee[1] - right_hip[1])
                        if r_dx > r_dy * 1.0:
                            is_thigh_horizontal = True

                # 另外檢查膝蓋的彎曲：如果腳踝 Y 座標接近或高於膝蓋，表示腿是彎曲的
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
                    
                    # 坐著時膝蓋到腳踝的距離也會較短
                    # 收緊閾值：hip_knee_ratio < 0.55 (原 0.6) 且 knee_ankle_dist < 0.55 * body_height
                    if hip_knee_ratio < 0.55 and knee_ankle_dist < body_height * 0.55:
                        is_sitting_likely = True
                    # 額外判斷：如果膝蓋非常接近髖部（比例 < 0.35），直接判定為坐著
                    elif hip_knee_ratio < 0.35:
                        is_sitting_likely = True
                    # 如果大腿是水平的，極大機率是坐著
                    elif is_thigh_horizontal:
                        is_sitting_likely = True
                        
                elif hip_knee_ratio < 0.45: # 收緊無腳踝時的閾值 (原 0.5)
                    # 沒有腳踝資料，但髖膝距離小
                    is_sitting_likely = True
                elif is_thigh_horizontal:
                    # 沒有腳踝資料，但大腿水平
                    is_sitting_likely = True
                
                # === 強制站立檢查 ===
                # 如果髖膝垂直距離很大（接近或超過身長），這絕對是站立
                if hip_knee_ratio > 0.7:
                    is_sitting_likely = False
        
        # 方法 3: 基於邊界框比例判斷
        # 坐著時，人的邊界框高寬比通常接近 1:1 或更扁
        # 站著時，高寬比通常 > 1.5
        if not is_sitting_likely and target_person.box is not None:
            x, y, w, h = target_person.box
            if w > 0:
                aspect_ratio = h / w
                # 如果高寬比 < 1.2 (原 1.35)，且不是全身可見（可能腿被遮擋），極可能是坐著
                if aspect_ratio < 1.2:
                    # 如果下半身可見度低，更加確認
                    if lower_ratio < 0.6:
                        is_sitting_likely = True
                    # 如果比例非常扁 (< 1.0)，直接判定
                    elif aspect_ratio < 1.0:
                        is_sitting_likely = True
        
        # 判斷是否全身可見
        is_full_body = (upper_ratio >= 0.7 and lower_ratio >= 0.7)
        
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
            found = False
            for person in frame.persons:
                if person.person_id == person_id:
                    recent_keypoints.append(person.get_keypoints(use_smoothed=True))
                    target_person_latest = person
                    found = True
                    break
        
        if len(recent_keypoints) < 2 or target_person_latest is None:
            return 0.0
            
        # 獲取邊界框大小用於歸一化（解決遠近問題）
        _, _, w, h = target_person_latest.box
        bbox_diag = np.sqrt(w**2 + h**2)
        if bbox_diag < 10: bbox_diag = 100.0 # 防止除以零
            
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

    def _init_tracking(self):
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
            # 沒有偵測到任何人，更新所有追蹤中的人為不可見
            self._update_invisible_persons(frame_data.timestamp, set())
            empty_frame = SkeletonFrame(
                timestamp=frame_data.timestamp,
                frame_no=frame_data.frame_no,
                persons=[]
            )
            # 將空幀加入 interpolated_buffer，這樣 Receiver 才能知道沒有人
            self._add_to_interpolated_buffer(empty_frame)
            # 重設 ID 映射（沒有人時重新從 0 開始）
            self._sender_to_local_id.clear()
            self._next_local_id = 0
            return empty_frame
        
        persons = []
        interpolated_persons_list = []  # 儲存每個人的插值幀
        detected_person_ids = set()  # 本幀偵測到的人物 ID（本地 ID）
        current_sender_ids = set()  # 本幀 Sender 傳來的原始 ID
        
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
            
            # 獲取對應的 ReID 向量 (與 keypoints 索引對應)
            reid_vector = None
            if hasattr(frame_data, 'reid_results') and idx < len(frame_data.reid_results):
                reid_vector = frame_data.reid_results[idx]
                if reid_vector is not None:
                    reid_vector = np.array(reid_vector, dtype=np.float32)
            
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
                    person_id=person_id,
                    keypoints=keypoints,
                    timestamp=frame_data.timestamp,
                    bbox=box
                )
                
                person = PersonSkeleton(
                    person_id=person_id,
                    box=box,
                    score=float(score),
                    keypoints=keypoints.copy(),  # 保存原始關鍵點
                    timestamp=frame_data.timestamp,
                    smoothed_keypoints=smoothed_keypoints,  # 保存平滑後的關鍵點
                    reid_vector=reid_vector,  # 保存 ReID 向量
                    is_visible=True,
                    last_seen_time=frame_data.timestamp
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
        
        # 更新未偵測到的人物狀態（離開偵測）
        self._update_invisible_persons(frame_data.timestamp, detected_person_ids)
        
        if not persons:
            # 沒有偵測到任何人，建立空幀並加入緩衝區
            empty_frame = SkeletonFrame(
                timestamp=frame_data.timestamp,
                frame_no=frame_data.frame_no,
                persons=[]
            )
            # 將空幀加入 interpolated_buffer，這樣 Receiver 才能知道沒有人
            self._add_to_interpolated_buffer(empty_frame)
            # 重設 ID 映射
            self._sender_to_local_id.clear()
            self._next_local_id = 0
            return empty_frame
        
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
        interpolated_persons_list: List[Tuple[int, Tuple, float, List[np.ndarray], Optional[np.ndarray]]],
        base_timestamp: float,
        frame_no: int
    ):
        """
        將預處理器生成的插值幀加入緩衝區
        """
        if not interpolated_persons_list:
            return
        
        # 找出最多的插值幀數
        max_frames = max(len(frames) for _, _, _, frames, _ in interpolated_persons_list) if interpolated_persons_list else 0
        
        if max_frames == 0:
            return
        
        self.debug_log(f"Adding {max_frames} interpolated frames from preprocessor")
        
        for frame_idx in range(max_frames):
            interp_persons = []
            
            for person_id, box, score, frames, reid_vector in interpolated_persons_list:
                if frame_idx < len(frames):
                    interp_kpts = frames[frame_idx]
                    
                    interp_person = PersonSkeleton(
                        person_id=person_id,
                        box=box,
                        score=score,
                        keypoints=interp_kpts,  # 插值幀沒有真正的原始資料
                        timestamp=base_timestamp,
                        smoothed_keypoints=interp_kpts,
                        reid_vector=reid_vector
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
                
                # === 智能插值邏輯 (防止點飛向原點) ===
                interp_keypoints = np.zeros_like(prev_kp)
                
                # 1. 分數插值 (線性)
                interp_keypoints[:, 2] = (1 - t_smooth) * prev_kp[:, 2] + t_smooth * curr_kp[:, 2]
                
                # 2. 位置插值
                # 判斷有效性 (score > 0.1 且不是原點)
                p_valid = (prev_kp[:, 2] > 0.1) & ((prev_kp[:, 0] > 1) | (prev_kp[:, 1] > 1))
                c_valid = (curr_kp[:, 2] > 0.1) & ((curr_kp[:, 0] > 1) | (curr_kp[:, 1] > 1))
                
                # Case 1: 兩者都有效 -> 正常插值
                both_valid = p_valid & c_valid
                interp_keypoints[both_valid, :2] = (1 - t_smooth) * prev_kp[both_valid, :2] + t_smooth * curr_kp[both_valid, :2]
                
                # Case 2: 只有前一幀有效 -> 保持前一幀位置 (避免飛向原點)
                only_p = p_valid & (~c_valid)
                interp_keypoints[only_p, :2] = prev_kp[only_p, :2]
                
                # Case 3: 只有當前幀有效 -> 使用當前幀位置
                only_c = (~p_valid) & c_valid
                interp_keypoints[only_c, :2] = curr_kp[only_c, :2]
                
                # Case 4: 都無效 -> 保持 0 (已由 zeros_like 初始化)
                
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
        
        # 只針對「當前畫面中」的人物進行識別
        # 這樣當人離開畫面時，識別結果會立即消失
        latest_frame = self.get_latest_interpolated_frame()
        if not latest_frame or not latest_frame.persons:
            return {}
            
        current_person_ids = [p.person_id for p in latest_frame.persons]
        
        # 取最近的 sequence_length 幀
        frames = list(self.interpolated_buffer)[-config.interpolation.sequence_length:]
        
        # 為每個人物建構序列
        sequences = {}
        for person_id in current_person_ids:
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
    
    def _update_invisible_persons(self, current_time: float, detected_ids: set):
        """
        更新未偵測到的人物狀態
        
        Args:
            current_time: 當前時間戳
            detected_ids: 本幀偵測到的人物 ID 集合
        """
        persons_to_remove = []
        
        for person_id, person in self.person_tracker.items():
            if person_id not in detected_ids:
                # 這個人本幀沒有被偵測到
                time_since_seen = current_time - person.last_seen_time
                
                if person.is_visible:
                    # 檢查是否超過消失超時
                    if time_since_seen >= self.disappear_timeout:
                        # 標記為不可見
                        person.is_visible = False
                        
                        # 計算消失方向（根據最後位置）
                        x, y, w, h = person.box
                        cx, cy = x + w // 2, y + h // 2
                        
                        # 假設畫面是 640x480 (根據實際配置調整)
                        frame_w, frame_h = 640, 480
                        
                        # 判斷消失方向
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
                
                # 檢查是否超過移除超時
                if time_since_seen >= self.remove_timeout:
                    persons_to_remove.append(person_id)
                    self.debug_log(f"Person {person_id} removed from tracker (unseen for {time_since_seen:.1f}s)")
        
        # 移除過期的人物
        for person_id in persons_to_remove:
            del self.person_tracker[person_id]
    
    def get_visible_persons(self) -> List[int]:
        """
        獲取當前可見的人物 ID 列表
        
        Returns:
            可見人物的 ID 列表
        """
        return [pid for pid, p in self.person_tracker.items() if p.is_visible]
    
    def get_invisible_persons(self) -> List[Tuple[int, str, Tuple[int, int, int, int]]]:
        """
        獲取當前不可見但仍在追蹤中的人物資訊
        
        Returns:
            [(person_id, disappear_direction, last_bbox), ...]
        """
        return [
            (pid, p.disappear_direction, p.box) 
            for pid, p in self.person_tracker.items() 
            if not p.is_visible
        ]
