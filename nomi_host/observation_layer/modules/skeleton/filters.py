"""
filters.py - 專業的骨架濾波與插值模組

這個模組提供系統性的骨架預處理:
1. One Euro Filter - 低延遲自適應濾波（業界標準）
2. 速度限制濾波 - 過濾異常跳動
3. 解剖學約束濾波 - 確保骨骼結構合理
4. Cubic Spline 插值 - 平滑的時間插值
"""

import math
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import CubicSpline, interp1d

# ============================================================================
# One Euro Filter - 業界標準的低延遲自適應濾波器
# 參考: https://gery.casiez.net/1euro/
# ============================================================================

def _smoothing_factor(t_e: float, cutoff: float) -> float:
    """計算平滑因子"""
    r = 2 * math.pi * cutoff * t_e
    return r / (r + 1)


def _exponential_smoothing(a: float, x: float, x_prev: float) -> float:
    """指數平滑"""
    return a * x + (1 - a) * x_prev


class OneEuroFilter:
    """
    1€ Filter - 專為實時追蹤設計的自適應低通濾波器
    
    參數調整指南：
    - min_cutoff: 降低以減少抖動（但增加延遲），建議 0.5-1.5
    - beta: 增加以減少快速移動時的延遲，建議 0.001-0.1
    - d_cutoff: 通常保持 1.0
    """
    
    def __init__(
        self, 
        t0: float, 
        x0: float, 
        dx0: float = 0.0, 
        min_cutoff: float = 1.0, 
        beta: float = 0.007, 
        d_cutoff: float = 1.0
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = float(x0)
        self.dx_prev = float(dx0)
        self.t_prev = float(t0)

    def __call__(self, t: float, x: float) -> float:
        t_e = t - self.t_prev
        if t_e <= 0:
            return self.x_prev
        
        # 濾波導數
        a_d = _smoothing_factor(t_e, self.d_cutoff)
        dx = (x - self.x_prev) / t_e
        dx_hat = _exponential_smoothing(a_d, dx, self.dx_prev)

        # 自適應截止頻率 - 移動越快，截止頻率越高（延遲越低）
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = _smoothing_factor(t_e, cutoff)
        x_hat = _exponential_smoothing(a, x, self.x_prev)

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat


class SkeletonOneEuroFilter:
    """
    為 17 個關鍵點（COCO 格式）的完整骨架濾波器
    每個關鍵點的 x, y 座標分別使用獨立的 One Euro Filter
    """
    
    def __init__(
        self, 
        num_keypoints: int = 17, 
        min_cutoff: float = 0.8,  # 低 FPS 建議使用較低值
        beta: float = 0.01,       # 低 FPS 建議使用較高值
        confidence_threshold: float = 0.1
    ):
        self.num_keypoints = num_keypoints
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.confidence_threshold = confidence_threshold
        # {person_id: {kpt_idx: (filter_x, filter_y)}}
        self.filters: Dict[int, Dict[int, Tuple[OneEuroFilter, OneEuroFilter]]] = {}
        # 追蹤上一次的平滑結果
        self.last_result: Dict[int, np.ndarray] = {}
    
    def filter(
        self, 
        person_id: int, 
        keypoints: np.ndarray, 
        timestamp: float
    ) -> np.ndarray:
        """
        對骨架關鍵點進行 One Euro 濾波
        
        Args:
            person_id: 人物 ID
            keypoints: shape (17, 3) 的 numpy 陣列 [x, y, score]
            timestamp: 時間戳（秒）
            
        Returns:
            平滑後的 keypoints
        """
        result = keypoints.copy()
        
        if person_id not in self.filters:
            # 初始化濾波器
            self.filters[person_id] = {}
            for i in range(self.num_keypoints):
                x, y, s = keypoints[i]
                if s > self.confidence_threshold and x > 0 and y > 0:
                    self.filters[person_id][i] = (
                        OneEuroFilter(timestamp, x, min_cutoff=self.min_cutoff, beta=self.beta),
                        OneEuroFilter(timestamp, y, min_cutoff=self.min_cutoff, beta=self.beta)
                    )
            self.last_result[person_id] = result.copy()
            return result
        
        for i in range(self.num_keypoints):
            x, y, s = keypoints[i]
            
            if s > self.confidence_threshold and x > 0 and y > 0:
                if i in self.filters[person_id]:
                    # 使用現有濾波器
                    fx, fy = self.filters[person_id][i]
                    result[i, 0] = fx(timestamp, x)
                    result[i, 1] = fy(timestamp, y)
                else:
                    # 新出現的有效點，初始化濾波器
                    self.filters[person_id][i] = (
                        OneEuroFilter(timestamp, x, min_cutoff=self.min_cutoff, beta=self.beta),
                        OneEuroFilter(timestamp, y, min_cutoff=self.min_cutoff, beta=self.beta)
                    )
            else:
                # 置信度低或座標無效，使用上一次的結果
                if person_id in self.last_result:
                    result[i, :2] = self.last_result[person_id][i, :2]
                    result[i, 2] = s * 0.5  # 降低置信度
        
        self.last_result[person_id] = result.copy()
        return result
    
    def reset(self, person_id: Optional[int] = None):
        """重置濾波器狀態"""
        if person_id is None:
            self.filters.clear()
            self.last_result.clear()
        else:
            self.filters.pop(person_id, None)
            self.last_result.pop(person_id, None)


# ============================================================================
# 解剖學約束濾波器
# ============================================================================

class AnatomicalFilter:
    """
    基於人體解剖學約束的過濾器
    檢查骨骼長度和身體結構的合理性
    """
    
    # COCO 骨架連接（骨骼）
    BONES = [
        (5, 7), (7, 9),     # 左臂：左肩-左肘-左腕
        (6, 8), (8, 10),    # 右臂：右肩-右肘-右腕
        (11, 13), (13, 15), # 左腿：左髖-左膝-左踝
        (12, 14), (14, 16), # 右腿：右髖-右膝-右踝
        (5, 6),             # 肩膀
        (11, 12),           # 髖部
        (5, 11),            # 左軀幹
        (6, 12),            # 右軀幹
    ]
    
    # 骨骼長度比例限制（相對於參考長度）
    BONE_LENGTH_LIMITS = {
        (5, 7): (0.15, 0.6),    # 上臂
        (7, 9): (0.1, 0.5),     # 前臂
        (6, 8): (0.15, 0.6),    # 上臂
        (8, 10): (0.1, 0.5),    # 前臂
        (11, 13): (0.2, 0.8),   # 大腿
        (13, 15): (0.15, 0.7),  # 小腿
        (12, 14): (0.2, 0.8),   # 大腿
        (14, 16): (0.15, 0.7),  # 小腿
        (5, 6): (0.1, 0.5),     # 肩寬
        (11, 12): (0.08, 0.4),  # 髖寬
        (5, 11): (0.2, 0.8),    # 軀幹
        (6, 12): (0.2, 0.8),    # 軀幹
    }
    
    def __init__(self, confidence_threshold: float = 0.3):
        self.confidence_threshold = confidence_threshold
        # 追蹤每個人的歷史骨骼長度
        self.bone_history: Dict[int, Dict[Tuple[int, int], deque]] = {}
    
    def filter(
        self, 
        person_id: int, 
        keypoints: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> np.ndarray:
        """
        過濾不符合解剖學約束的關鍵點
        
        Args:
            person_id: 人物 ID
            keypoints: shape (17, 3)
            bbox: (x, y, w, h) 邊界框
            
        Returns:
            過濾後的 keypoints
        """
        result = keypoints.copy()
        
        # 計算參考長度
        if bbox is not None:
            ref_length = np.sqrt(bbox[2]**2 + bbox[3]**2)
        else:
            # 使用肩膀到髖部的距離
            shoulder_center = (keypoints[5, :2] + keypoints[6, :2]) / 2
            hip_center = (keypoints[11, :2] + keypoints[12, :2]) / 2
            ref_length = np.linalg.norm(shoulder_center - hip_center)
            if ref_length < 20:
                ref_length = 150  # 預設值
        
        # 初始化歷史記錄
        if person_id not in self.bone_history:
            self.bone_history[person_id] = {bone: deque(maxlen=10) for bone in self.BONES}
        
        # 檢查每個骨骼
        for (p1, p2) in self.BONES:
            s1 = keypoints[p1, 2]
            s2 = keypoints[p2, 2]
            
            if s1 < self.confidence_threshold or s2 < self.confidence_threshold:
                continue
            
            x1, y1 = keypoints[p1, :2]
            x2, y2 = keypoints[p2, :2]
            
            # 檢查座標是否有效
            if x1 <= 0 or y1 <= 0 or x2 <= 0 or y2 <= 0:
                continue
            
            bone_length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            normalized_length = bone_length / ref_length
            
            # 檢查是否在合理範圍內
            if (p1, p2) in self.BONE_LENGTH_LIMITS:
                min_ratio, max_ratio = self.BONE_LENGTH_LIMITS[(p1, p2)]
                
                if normalized_length < min_ratio or normalized_length > max_ratio:
                    # 骨骼長度異常
                    # 使用歷史平均值或降低置信度
                    history = self.bone_history[person_id][(p1, p2)]
                    
                    if len(history) > 3:
                        avg_length = np.mean(list(history))
                        
                        # 如果當前長度與歷史差異太大
                        if abs(bone_length - avg_length) > avg_length * 0.5:
                            # 降低置信度較低的那個點
                            if s1 < s2:
                                result[p1, 2] = s1 * 0.3
                            else:
                                result[p2, 2] = s2 * 0.3
                    else:
                        # 歷史不足，直接降低置信度
                        if s1 < s2:
                            result[p1, 2] = s1 * 0.5
                        else:
                            result[p2, 2] = s2 * 0.5
                else:
                    # 正常長度，加入歷史
                    self.bone_history[person_id][(p1, p2)].append(bone_length)
        
        # 邊界框約束
        if bbox is not None:
            bx, by, bw, bh = bbox
            margin = max(bw, bh) * 0.3
            
            for i in range(len(result)):
                x, y, s = result[i]
                if s > 0:
                    # 檢查是否超出擴展邊界框
                    if (x < bx - margin or x > bx + bw + margin or
                        y < by - margin or y > by + bh + margin):
                        result[i, 2] = 0  # 超出範圍，設置為無效
        
        return result
    
    def reset(self, person_id: Optional[int] = None):
        """重置歷史記錄"""
        if person_id is None:
            self.bone_history.clear()
        else:
            self.bone_history.pop(person_id, None)


# ============================================================================
# Cubic Spline 骨架插值器
# ============================================================================

class SkeletonInterpolator:
    """
    骨架序列插值器 - 從低 FPS 插值到高 FPS
    使用 Cubic Spline 實現平滑的動作過渡
    """
    
    def __init__(
        self, 
        num_keypoints: int = 17,
        confidence_threshold: float = 0.3
    ):
        self.num_keypoints = num_keypoints
        self.confidence_threshold = confidence_threshold
    
    def interpolate_pair(
        self,
        prev_keypoints: np.ndarray,  # shape: (17, 3)
        curr_keypoints: np.ndarray,  # shape: (17, 3)
        num_frames: int,
        method: str = 'hermite'
    ) -> List[np.ndarray]:
        """
        在兩幀之間插值生成中間幀
        
        Args:
            prev_keypoints: 前一幀關鍵點
            curr_keypoints: 當前幀關鍵點
            num_frames: 要生成的幀數（包含終點，不包含起點）
            method: 'linear', 'hermite', 'smoothstep'
            
        Returns:
            插值後的幀列表
        """
        if num_frames <= 1:
            return [curr_keypoints.copy()]
        
        results = []
        
        for i in range(1, num_frames + 1):
            t = i / num_frames  # 0 -> 1
            
            # 使用不同的插值曲線
            if method == 'hermite':
                # Hermite smoothstep: 3t² - 2t³
                t_smooth = t * t * (3 - 2 * t)
            elif method == 'smoothstep':
                # Smootherstep: 6t⁵ - 15t⁴ + 10t³
                t_smooth = t * t * t * (t * (t * 6 - 15) + 10)
            else:
                # Linear
                t_smooth = t
            
            interp = np.zeros_like(prev_keypoints)
            
            for j in range(self.num_keypoints):
                prev_pos = prev_keypoints[j, :2]
                curr_pos = curr_keypoints[j, :2]
                prev_score = prev_keypoints[j, 2]
                curr_score = curr_keypoints[j, 2]
                
                # 如果任一點無效，使用有效的那個
                if prev_score < self.confidence_threshold or prev_pos[0] <= 0:
                    interp[j] = curr_keypoints[j]
                elif curr_score < self.confidence_threshold or curr_pos[0] <= 0:
                    interp[j] = prev_keypoints[j]
                else:
                    # 兩個都有效，進行插值
                    interp[j, 0] = (1 - t_smooth) * prev_pos[0] + t_smooth * curr_pos[0]
                    interp[j, 1] = (1 - t_smooth) * prev_pos[1] + t_smooth * curr_pos[1]
                    interp[j, 2] = (1 - t_smooth) * prev_score + t_smooth * curr_score
            
            results.append(interp)
        
        return results
    
    def interpolate_sequence(
        self,
        keypoints_sequence: np.ndarray,  # shape: (T, 17, 3)
        timestamps: np.ndarray,          # shape: (T,)
        target_fps: float = 30.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        將整個序列插值到目標 FPS
        
        Args:
            keypoints_sequence: 原始骨架序列
            timestamps: 每幀的時間戳
            target_fps: 目標 FPS
            
        Returns:
            (interpolated_sequence, new_timestamps)
        """
        T, V, C = keypoints_sequence.shape
        
        if T < 2:
            return keypoints_sequence, timestamps
        
        # 計算新的時間點
        duration = timestamps[-1] - timestamps[0]
        num_new_frames = max(int(duration * target_fps) + 1, T)
        new_timestamps = np.linspace(timestamps[0], timestamps[-1], num_new_frames)
        
        # 為每個關鍵點的每個座標分別插值
        new_sequence = np.zeros((num_new_frames, V, C), dtype=np.float32)
        
        for kpt_idx in range(V):
            scores = keypoints_sequence[:, kpt_idx, 2]
            valid_mask = scores > self.confidence_threshold
            
            if valid_mask.sum() < 2:
                # 有效點不足，使用線性插值或填充
                for coord_idx in range(C):
                    new_sequence[:, kpt_idx, coord_idx] = np.interp(
                        new_timestamps, timestamps, keypoints_sequence[:, kpt_idx, coord_idx]
                    )
            else:
                # 對 x, y 座標使用 cubic spline
                for coord_idx in range(2):
                    values = keypoints_sequence[:, kpt_idx, coord_idx]
                    
                    if valid_mask.sum() >= 4:
                        try:
                            cs = CubicSpline(
                                timestamps[valid_mask],
                                values[valid_mask],
                                extrapolate=True
                            )
                            new_sequence[:, kpt_idx, coord_idx] = cs(new_timestamps)
                        except Exception:
                            # Fallback to linear
                            new_sequence[:, kpt_idx, coord_idx] = np.interp(
                                new_timestamps,
                                timestamps[valid_mask],
                                values[valid_mask]
                            )
                    else:
                        new_sequence[:, kpt_idx, coord_idx] = np.interp(
                            new_timestamps,
                            timestamps[valid_mask],
                            values[valid_mask]
                        )
                
                # 插值置信度
                new_sequence[:, kpt_idx, 2] = np.interp(
                    new_timestamps, timestamps, scores
                )
        
        return new_sequence, new_timestamps
    
    @staticmethod
    def uniform_sample(
        keypoints_sequence: np.ndarray,
        target_length: int = 48
    ) -> np.ndarray:
        """
        均勻採樣到固定長度（MMAction2 標準預處理）
        
        Args:
            keypoints_sequence: shape (T, 17, 3)
            target_length: 目標幀數
            
        Returns:
            重採樣後的序列 shape (target_length, 17, 3)
        """
        T, V, C = keypoints_sequence.shape
        
        if T == target_length:
            return keypoints_sequence.copy()
        
        if T >= target_length:
            # 下採樣
            indices = np.linspace(0, T - 1, target_length).astype(int)
            return keypoints_sequence[indices]
        else:
            # 上採樣（插值）
            result = np.zeros((target_length, V, C), dtype=np.float32)
            old_indices = np.arange(T)
            new_indices = np.linspace(0, T - 1, target_length)
            
            for kpt_idx in range(V):
                for coord_idx in range(C):
                    f = interp1d(
                        old_indices, 
                        keypoints_sequence[:, kpt_idx, coord_idx],
                        kind='linear', 
                        fill_value='extrapolate'
                    )
                    result[:, kpt_idx, coord_idx] = f(new_indices)
            
            return result


# ============================================================================
# 完整的骨架預處理管道
# ============================================================================

class SkeletonPreprocessor:
    """
    完整的骨架預處理管道
    
    處理流程:
    1. 解剖學約束過濾 - 確保骨骼結構合理
    2. One Euro 時間平滑 - 低延遲自適應濾波
    3. 時間插值 - 從低 FPS 到高 FPS
    """
    
    def __init__(
        self,
        num_keypoints: int = 17,
        target_fps: float = 15.0,
        # One Euro Filter 參數（針對低 FPS 優化）
        one_euro_min_cutoff: float = 0.5,
        one_euro_beta: float = 0.01,
        # 置信度閾值
        confidence_threshold: float = 0.1
    ):
        self.num_keypoints = num_keypoints
        self.target_fps = target_fps
        self.confidence_threshold = confidence_threshold
        
        # 初始化各個濾波器
        self.one_euro = SkeletonOneEuroFilter(
            num_keypoints, 
            one_euro_min_cutoff, 
            one_euro_beta,
            confidence_threshold
        )
        self.anatomical_filter = AnatomicalFilter(confidence_threshold)
        self.interpolator = SkeletonInterpolator(num_keypoints, confidence_threshold)
        
        # 上一幀的處理結果
        self.last_processed: Dict[int, np.ndarray] = {}
        self.last_timestamp: Dict[int, float] = {}
    
    def process_frame(
        self,
        person_id: int,
        keypoints: np.ndarray,
        timestamp: float,
        bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> Tuple[np.ndarray, List[np.ndarray]]:
        """
        處理單幀骨架數據並生成插值幀
        
        Args:
            person_id: 人物 ID
            keypoints: 原始關鍵點 shape (17, 3)
            timestamp: 時間戳
            bbox: 邊界框
            
        Returns:
            (processed_keypoints, interpolated_frames)
            - processed_keypoints: 處理後的當前幀
            - interpolated_frames: 從上一幀到當前幀的插值幀列表
        """
        # Step 1: 解剖學約束過濾
        filtered = self.anatomical_filter.filter(person_id, keypoints, bbox)
        
        # Step 2: One Euro 時間平滑
        smoothed = self.one_euro.filter(person_id, filtered, timestamp)
        
        # Step 3: 生成插值幀
        interpolated_frames = []
        
        if person_id in self.last_processed and person_id in self.last_timestamp:
            prev_kpts = self.last_processed[person_id]
            prev_time = self.last_timestamp[person_id]
            
            time_diff = timestamp - prev_time
            # 如果時間差太大（超過 1 秒），視為新出現的人，不進行插值
            if 0 < time_diff < 1.0:
                # 計算需要的插值幀數
                target_interval = 1.0 / self.target_fps
                num_frames = int(time_diff / target_interval)
                num_frames = min(max(num_frames, 1), 30)  # 限制在 1-30 幀
                
                # 生成插值幀
                interpolated_frames = self.interpolator.interpolate_pair(
                    prev_kpts, smoothed, num_frames, method='hermite'
                )
            elif time_diff >= 1.0:
                # 重置該人物的濾波器狀態，避免從過時的位置開始平滑
                self.one_euro.reset(person_id)
        
        # 更新狀態
        self.last_processed[person_id] = smoothed.copy()
        self.last_timestamp[person_id] = timestamp
        
        return smoothed, interpolated_frames
    
    def reset(self, person_id: Optional[int] = None):
        """重置所有狀態"""
        self.one_euro.reset(person_id)
        self.anatomical_filter.reset(person_id)
        
        if person_id is None:
            self.last_processed.clear()
            self.last_timestamp.clear()
        else:
            self.last_processed.pop(person_id, None)
            self.last_timestamp.pop(person_id, None)
