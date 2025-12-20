import random
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ============================================================
# COCO 骨架定義
# ============================================================
COCO_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16)
]

# 預設骨架顏色 (Rainbow)
SKELETON_COLORS = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0),
    (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
    (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
    (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
    (255, 0, 170),
]

# 下半身關鍵點索引（用於特別過濾）
LOWER_BODY_INDICES = {11, 12, 13, 14, 15, 16}  # 髖、膝、踝

class Visualizer:
    @staticmethod
    def get_person_color(person_id: int) -> Tuple[int, int, int]:
        """根據 Person ID 生成固定顏色"""
        random.seed(person_id)
        # 生成高飽和度、高亮度的顏色
        color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        return color

    @staticmethod
    def draw_skeleton(frame: np.ndarray, keypoints: np.ndarray, 
                      person_id: Optional[int] = None,
                      box: Optional[Tuple[int, int, int, int]] = None,
                      thickness: int = 2, conf_threshold: float = 0.1,
                      show_confidence: bool = False) -> np.ndarray:
        """
        繪製單人骨架
        
        Args:
            frame: 影像 (會被直接修改)
            keypoints: 關鍵點 (17, 3) [x, y, conf]
            person_id: 人物 ID (用於生成顏色)
            box: 邊界框 (x, y, w, h)
            thickness: 線條粗細
            conf_threshold: 置信度閾值
            show_confidence: 是否顯示置信度
        """
        h, w = frame.shape[:2]
        
        # 獲取該人物的專屬顏色 (用於 ID 標籤或邊框)
        id_color = Visualizer.get_person_color(person_id) if person_id is not None else (0, 255, 0)
        
        def is_valid_point(idx):
            """檢查關鍵點是否有效（置信度夠高且座標在畫面範圍內）"""
            # 修改：移除下半身特殊閾值，統一使用 conf_threshold (0.1)
            threshold = conf_threshold
            if idx >= len(keypoints): return False
            if keypoints[idx, 2] <= threshold:
                return False
            x, y = keypoints[idx, 0], keypoints[idx, 1]
            if x <= 0 or y <= 0 or x >= w or y >= h:
                return False
            return True
        
        # 繪製邊界框 (如果有提供)
        if box is not None:
            bx, by, bw, bh = box
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), id_color, 2)
            
            # 繪製 ID 標籤背景
            if person_id is not None:
                label = f"ID: {person_id}"
                (label_w, label_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                # 確保標籤不會超出畫面頂部
                label_y = max(by, label_h + 10)
                cv2.rectangle(frame, (bx, label_y - label_h - 10), (bx + label_w + 10, label_y), id_color, -1)
                cv2.putText(frame, label, (bx + 5, label_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        # 繪製骨架連線 (使用 Rainbow 顏色)
        for i, (start, end) in enumerate(COCO_SKELETON):
            if is_valid_point(start) and is_valid_point(end):
                pt1 = (int(keypoints[start, 0]), int(keypoints[start, 1]))
                pt2 = (int(keypoints[end, 0]), int(keypoints[end, 1]))
                color = SKELETON_COLORS[i % len(SKELETON_COLORS)]
                cv2.line(frame, pt1, pt2, color, thickness)
        
        # 繪製關鍵點
        for i in range(len(keypoints)):
            if not is_valid_point(i):
                continue
                
            conf = keypoints[i, 2]
            x, y = keypoints[i, 0], keypoints[i, 1]
            pt = (int(x), int(y))
            
            # 根據置信度調整顏色：綠色=高，黃色=中，紅色=低
            if conf > 0.7:
                k_color = (0, 255, 0)  # 綠色
            elif conf > 0.5:
                k_color = (0, 255, 255)  # 黃色
            else:
                k_color = (0, 165, 255)  # 橙色
            
            cv2.circle(frame, pt, 5, k_color, -1)
            cv2.circle(frame, pt, 5, (0, 0, 0), 1)
            
            # 顯示置信度
            if show_confidence:
                cv2.putText(frame, f"{conf:.1f}", (pt[0]+8, pt[1]-5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
                           
        return frame

    @staticmethod
    def draw_info_overlay(frame: np.ndarray, info: dict) -> np.ndarray:
        output = frame.copy()
        overlay = output.copy()
        cv2.rectangle(overlay, (10, 10), (380, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, output, 0.4, 0, output)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        mode = info.get('mode', 'N/A')
        sample_fps = info.get('sample_fps', 0)
        output_fps = info.get('output_fps', 30)
        
        cv2.putText(output, f"Mode: {mode}", (20, 35), font, 0.6, (255, 255, 0), 1)
        
        # 在 Interpolated 視圖顯示補幀資訊
        if mode == 'Interpolated':
            interp_t = info.get('interp_t', 0.0)
            cv2.putText(output, f"Sample: {sample_fps:.0f} FPS -> Output: {output_fps} FPS", (20, 60), font, 0.5, (0, 255, 255), 1)
            cv2.putText(output, f"Interpolation t: {interp_t:.2f}", (20, 85), font, 0.5, (255, 255, 255), 1)
        else:
            cv2.putText(output, f"Sample FPS: {sample_fps:.0f}", (20, 60), font, 0.6, (0, 255, 255), 1)
            cv2.putText(output, f"Buffer: {info.get('buffer', 0)}/{info.get('buffer_max', 48)}", 
                       (20, 85), font, 0.6, (255, 255, 255), 1)
        
        cv2.putText(output, f"Action: {info.get('action', 'N/A')}", (20, 110), font, 0.5, (0, 255, 0), 1)
        
        return output


class SkeletonPlayer:
    """
    骨架序列播放器 - 負責管理補幀緩衝區的播放進度
    
    改進版本：
    - 使用追加式緩衝區，避免覆蓋導致的跳幀
    - 智慧播放速度控制，根據緩衝區深度自動調整
    - 支援變動幀率的輸入源
    """
    def __init__(self, processor=None):
        self.processor = processor
        self.buffer = []  # 內部緩衝區
        self.play_index = 0
        self.last_frame = None  # 快取最後一幀，用於緩衝區空時顯示
        self.frames_played = 0
        self.buffer_low_count = 0  # 連續緩衝區過低的次數
        
    def set_buffer(self, new_frames: list):
        """
        追加新幀到緩衝區（而非覆蓋）
        
        Args:
            new_frames: 新的補幀列表
        """
        if not new_frames:
            return
            
        # 找出真正新的幀（避免重複添加）
        if self.buffer:
            # 比較 timestamp 來判斷是否為新幀
            last_ts = self.buffer[-1].timestamp if self.buffer else 0
            new_frames = [f for f in new_frames if f.timestamp > last_ts]
        
        if new_frames:
            self.buffer.extend(new_frames)
            
            # 限制緩衝區最大長度，保留最新的幀
            max_buffer_size = 120  # 約 4 秒的 30 FPS
            if len(self.buffer) > max_buffer_size:
                # 調整 play_index
                overflow = len(self.buffer) - max_buffer_size
                self.buffer = self.buffer[overflow:]
                self.play_index = max(0, self.play_index - overflow)
        
    def get_next_frame(self):
        """
        獲取下一幀要顯示的骨架幀
        
        Returns:
            SkeletonFrame or None
        """
        if self.processor:
            # 從 processor 取得新幀並追加
            new_frames = self.processor.get_interpolated_frames()
            self.set_buffer(new_frames)
            
        if not self.buffer:
            return self.last_frame  # 緩衝區空時，返回最後一幀
            
        buffer_len = len(self.buffer)
        remaining = buffer_len - self.play_index
        
        # 緩衝區已經播放完畢
        if self.play_index >= buffer_len:
            self.buffer_low_count += 1
            return self.last_frame
        
        # 獲取當前幀
        try:
            target_frame = self.buffer[self.play_index]
            self.last_frame = target_frame
            self.frames_played += 1
        except IndexError:
            return self.last_frame
            
        # 智慧播放速度控制
        # 根據緩衝區剩餘量動態調整播放速度
        if remaining <= 2:
            # 緩衝區快空了，暫停等待新幀
            self.buffer_low_count += 1
            # 不增加 play_index，等待緩衝區補充
            if self.buffer_low_count < 3:
                return target_frame
            # 如果連續多次緩衝區過低，才往前推進
            step = 1
        elif remaining <= 5:
            # 緩衝區較少，減速播放
            step = 1
            self.buffer_low_count = 0
        elif remaining <= 15:
            # 緩衝區正常，正常速度
            step = 1
            self.buffer_low_count = 0
        elif remaining <= 30:
            # 緩衝區較多，稍微加速
            step = 1
            self.buffer_low_count = 0
        else:
            # 緩衝區太滿，快速消耗
            step = 2
            self.buffer_low_count = 0
            
        self.play_index += step
        
        # 定期清理已播放的舊幀，釋放記憶體
        if self.play_index > 60:
            cleanup_count = self.play_index - 30
            self.buffer = self.buffer[cleanup_count:]
            self.play_index -= cleanup_count
        
        return target_frame
    
    def get_buffer_status(self) -> dict:
        """獲取緩衝區狀態（用於調試）"""
        return {
            "buffer_size": len(self.buffer),
            "play_index": self.play_index,
            "remaining": len(self.buffer) - self.play_index,
            "frames_played": self.frames_played,
            "buffer_low_count": self.buffer_low_count
        }
    
    def reset(self):
        """重置播放狀態（但保留緩衝區）"""
        # 不清空緩衝區，只重置播放位置到最新位置
        if self.buffer:
            # 從最新幀開始播放
            self.play_index = max(0, len(self.buffer) - 1)
        else:
            self.play_index = 0
        self.buffer_low_count = 0
        
    def clear(self):
        """完全清空緩衝區和狀態"""
        self.buffer = []
        self.play_index = 0
        self.last_frame = None
        self.frames_played = 0
        self.buffer_low_count = 0
