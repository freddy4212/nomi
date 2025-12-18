"""
action_recognizer.py - MMAction2 動作識別模組

這個模組負責：
- 載入 MMAction2 骨架動作識別模型
- 將骨架序列轉換為 MMAction2 輸入格式
- 執行動作推理
- 將預測結果轉換為人類可讀的描述

支援的模型：
- PoseC3D: 基於 3D CNN 的骨架動作識別
- ST-GCN: 基於圖卷積網路的骨架動作識別
"""

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .config import config
except ImportError:
    from config import config

from collections import deque


@dataclass
class ActionResult:
    """動作識別結果"""
    person_id: int  # 人物 ID
    action_label: str  # 動作標籤
    action_description: str  # 動作描述
    confidence: float  # 信心度
    top_k_actions: List[Tuple[str, float]]  # Top-K
    simplified_label: str = ""  # 簡化標籤
    motion_status: str = ""     # 動作強度
    duration: float = 0.0       # 該動作持續時間（秒）
    is_stable: bool = False     # 動作是否已穩定
    raw_scores: Optional[np.ndarray] = None


class TemporalFilter:
    """使用滑動窗口投票機制穩定識別結果"""
    def __init__(self, window_size: int = 5, min_confidence: float = 0.3):
        self.window_size = window_size
        self.min_confidence = min_confidence
        self.history = deque(maxlen=window_size)  # 存儲 (label, confidence) 
        self.current_stable_label = "等待中..."
        self.current_stable_confidence = 0.0
    
    def update(self, label: str, confidence: float) -> Tuple[str, float]:
        """添加新結果並返回穩定的結果"""
        # 低信心度結果不加入歷史
        if confidence >= self.min_confidence:
            self.history.append((label, confidence))
        
        if len(self.history) == 0:
            return self.current_stable_label, self.current_stable_confidence
        
        # 使用加權投票：信心度作為權重
        vote_scores = {}
        for hist_label, hist_conf in self.history:
            if hist_label not in vote_scores:
                vote_scores[hist_label] = 0.0
            vote_scores[hist_label] += hist_conf
        
        # 找出最高分的標籤
        best_label = max(vote_scores, key=vote_scores.get)
        # 計算平均信心度
        label_count = sum(1 for l, _ in self.history if l == best_label)
        avg_confidence = vote_scores[best_label] / label_count
        
        self.current_stable_label = best_label
        self.current_stable_confidence = avg_confidence
        
        return best_label, avg_confidence
    
    def clear(self):
        self.history.clear()
        self.current_stable_label = "等待中..."
        self.current_stable_confidence = 0.0


class ActionRecognizer:
    """
    MMAction2 動作識別器
    
    使用骨架序列進行動作識別，支援多種預訓練模型
    """
    
    def __init__(self):
        """初始化動作識別器"""
        self.model = None
        self.model_loaded = False
        self.device = config.action.device
        self.lock = threading.Lock()
        
        # 動作描述模板 (簡化版)
        self.simplified_descriptions = {
            "坐著": "這個人正在坐著",
            "站立": "這個人正在站立",
            "走路": "這個人正在行走",
            "跑步": "這個人正在跑步",
            "跳躍": "這個人正在跳躍",
            "運動/伸展": "這個人正在進行運動或伸展",
            "打架/衝突": "偵測到可能的衝突動作",
            "蹲下/低姿態": "這個人正蹲下或彎腰",
            "躺下/跌倒": "偵測到跌倒或躺下的異常狀態",
            "靜止/等待": "這個人目前保持靜止",
            "等待中...": "正在分析動作..."
        }
        
        # 最近的預測結果快取
        self.last_results: Dict[int, ActionResult] = {}
        self.last_inference_time: float = 0.0
        
        # 時序濾波器（每個 ID 一個）
        self.temporal_filters: Dict[int, TemporalFilter] = {}
        
        # 狀態追蹤：{person_id: {"label": str, "start_time": float}}
        self.state_tracker: Dict[int, Dict[str, Any]] = {}
        
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[ActionRecognizer][{time.time():.3f}] {msg}")

    def _get_description(self, label: str) -> str:
        """獲取動作描述"""
        return self.simplified_descriptions.get(label, f"正在進行 {label}")
    
    def load_model(self) -> bool:
        """
        載入 MMAction2 模型
        
        Returns:
            是否載入成功
        """
        try:
            self.debug_log("Loading MMAction2 model...")
            
            # 嘗試導入 MMAction2
            try:
                from mmaction.apis import init_recognizer

                # 載入模型配置和權重
                self.model = init_recognizer(
                    config.action.config_file,
                    config.action.checkpoint_file,
                    device=self.device
                )
                self.model_loaded = True
                self.debug_log("MMAction2 model loaded successfully")
                return True
                
            except ImportError:
                self.debug_log("MMAction2 not installed, using fallback mode")
                # 使用回退模式（基於規則的簡單動作識別）
                self.model_loaded = False
                return False
                
        except Exception as e:
            self.debug_log(f"Failed to load model: {e}")
            self.model_loaded = False
            return False
    
    def recognize(
        self, 
        skeleton_sequence: np.ndarray,
        person_id: int = 0,
        motion_magnitude: float = 0.0,
        visibility_info: Dict[str, Any] = None,
        bbox: Tuple[int, int, int, int] = None
    ) -> Optional[ActionResult]:
        """
        識別骨架序列的動作
        
        Args:
            skeleton_sequence: 骨架序列，shape (T, V, C)
            person_id: 人物 ID
            motion_magnitude: 動作幅度（像素/幀）
            visibility_info: 骨架可見性資訊
            bbox: 邊界框 (x, y, w, h)
            
        Returns:
            動作識別結果
        """
        if skeleton_sequence is None:
            return None
        
        with self.lock:
            try:
                start_time = time.time()
                
                if self.model_loaded and self.model is not None:
                    # 使用 MMAction2 進行推理
                    result = self._mmaction2_inference(skeleton_sequence, person_id)
                else:
                    # 使用回退模式
                    result = self._fallback_inference(skeleton_sequence, person_id)
                
                self.last_inference_time = time.time() - start_time
                
                if result:
                    # === 應用簡化模式與層次化邏輯 ===
                    
                    # 1. 計算簡化類別分數
                    if result.raw_scores is not None and hasattr(config, 'simplified'):
                        simplified_scores = np.zeros(len(config.simplified.labels))
                        for orig_idx, simp_idx in config.simplified.mapping.items():
                            if orig_idx < len(result.raw_scores):
                                simplified_scores[simp_idx] += result.raw_scores[orig_idx]
                        
                        # 歸一化
                        total = simplified_scores.sum()
                        if total > 0:
                            simplified_scores /= total
                            
                        # 找出最佳簡化類別
                        top_simp_idx = np.argmax(simplified_scores)
                        simp_label = config.simplified.labels[top_simp_idx]
                        simp_score = float(simplified_scores[top_simp_idx])
                        
                        # 更新結果中的簡化標籤
                        result.simplified_label = simp_label
                        
                        # === 應用時序濾波 ===
                        if person_id not in self.temporal_filters:
                            self.temporal_filters[person_id] = TemporalFilter()
                        
                        stable_label, stable_conf = self.temporal_filters[person_id].update(
                            simp_label, simp_score
                        )
                        
                        # 使用穩定後的結果
                        simp_label = stable_label
                        simp_score = stable_conf
                        result.simplified_label = stable_label
                        result.confidence = stable_conf # 更新信心度為穩定後的
                        
                        # 2. 判斷動作強度類型
                        if motion_magnitude < config.motion.threshold_low:
                            motion_type = "靜止"
                            # 減少「靜止/等待」的權重，優先判定為具體姿態
                            valid_actions = ["坐著", "站立", "蹲下/低姿態"]
                        elif motion_magnitude > config.motion.threshold_high:
                            motion_type = "劇烈"
                            valid_actions = ["跳躍", "打架/衝突", "躺下/跌倒", "跑步", "走路"]
                        else:
                            motion_type = "移動"
                            valid_actions = ["站立", "走路", "運動/伸展", "蹲下/低姿態"]
                            
                        result.motion_status = f"{motion_magnitude:.1f} ({motion_type})"
                        
                        # 3. 智慧過濾邏輯
                        final_action = simp_label
                        final_confidence = simp_score
                        
                        # 預先判斷坐姿可能性
                        is_sitting_likely = False
                        aspect_ratio = 0.0
                        if visibility_info:
                            is_sitting_likely = visibility_info.get('is_sitting_likely', False)
                            if bbox is not None:
                                x, y, w, h = bbox
                                aspect_ratio = h / w if w > 0 else 0
                                # 強化比例判定：
                                # 1. 如果比例明顯是長方形（站立通常 > 1.3），則極大機率是站立
                                if aspect_ratio > 1.3:
                                    is_sitting_likely = False
                                # 2. 如果比例接近正方形或更扁，且下半身可見度不高，極大機率是坐著
                                elif aspect_ratio < 1.1:
                                    is_sitting_likely = True
                        
                        # (A) 骨架可見性與比例過濾（優先級最高）
                        if visibility_info:
                            # 如果判定為坐著，強制修正站立類動作
                            if is_sitting_likely:
                                if final_action in ["站立", "走路", "跳躍", "跑步", "靜止/等待", "運動/伸展"]:
                                    final_action = "坐著"
                                    final_confidence = max(0.8, final_confidence)
                            # 反之，如果判定為站立，但模型誤判為坐著或運動（可能是因為手部動作誤導）
                            elif not is_sitting_likely:
                                if final_action in ["坐著", "運動/伸展"] and motion_type != "劇烈":
                                    final_action = "站立"
                                    final_confidence = 0.7
                            
                            # 針對「刷牙/摸頭」等手部動作的邏輯修正：
                            hand_sensitive_actions = ["刷牙", "梳頭", "吃東西", "喝水", "觸摸頭", "觸摸頸"]
                            upper_ratio = visibility_info.get('upper_ratio', 0.0)
                            if result.action_label in hand_sensitive_actions and upper_ratio < 0.4:
                                # 手部不可見卻判定為手部動作，降級為基礎姿態
                                if motion_type == "靜止":
                                    final_action = "坐著" if is_sitting_likely else "站立"
                                else:
                                    final_action = "站立"
                        
                        # (B) 動作強度過濾
                        if final_action not in valid_actions:
                            # 嘗試從簡化分數中找第二高且符合強度的
                            sorted_indices = np.argsort(simplified_scores)[::-1]
                            found_better = False
                            for idx in sorted_indices[1:]: # 跳過第一名
                                label = config.simplified.labels[idx]
                                if label in valid_actions:
                                    final_action = label
                                    final_confidence = float(simplified_scores[idx])
                                    found_better = True
                                    break
                            
                            # 如果都沒找到，且是靜止狀態，強制歸類為基礎姿態
                            if not found_better and motion_type == "靜止":
                                final_action = "坐著" if is_sitting_likely else "站立"
                                final_confidence = 0.5
                        
                        # (C) 最終兜底：如果還是「靜止/等待」，但在靜止狀態下，強制轉為姿態
                        if final_action == "靜止/等待" and motion_type == "靜止":
                            final_action = "坐著" if is_sitting_likely else "站立"
                            final_confidence = 0.6
                        
                        # 更新最終結果
                        result.simplified_label = final_action
                        result.action_label = final_action # 覆蓋原始標籤，讓輸出乾淨
                        
                        # === 狀態持續時間追蹤 ===
                        now = time.time()
                        if person_id not in self.state_tracker or self.state_tracker[person_id]["label"] != final_action:
                            self.state_tracker[person_id] = {"label": final_action, "start_time": now}
                            result.duration = 0.0
                        else:
                            result.duration = now - self.state_tracker[person_id]["start_time"]
                        
                        # 智慧描述合成：如果是坐著進行特定動作
                        description = self._get_description(final_action)
                        if is_sitting_likely and final_action != "坐著":
                            description = f"坐著{description.replace('這個人正在', '')}"
                        
                        # 如果動作持續很久，增加描述強度
                        if result.duration > 10:
                            description += f" (已持續 {int(result.duration)} 秒)"
                        
                        result.action_description = description
                        
                    self.last_results[person_id] = result
                
                return result
                
            except Exception as e:
                self.debug_log(f"Recognition error: {e}")
                return None
    
    def _mmaction2_inference(
        self, 
        skeleton_sequence: np.ndarray,
        person_id: int
    ) -> Optional[ActionResult]:
        """
        使用 MMAction2 進行推理
        
        Args:
            skeleton_sequence: 骨架序列，shape (T, V, C) 其中 C=3 (x, y, score)
            person_id: 人物 ID
            
        Returns:
            動作識別結果
        """
        try:
            from mmaction.apis import inference_skeleton

            # 準備輸入資料
            # inference_skeleton 期望 pose_results 是一個列表，每個元素代表一幀
            # 每幀包含 'keypoints' shape (num_persons, num_keypoints, 2)
            # 和 'keypoint_scores' shape (num_persons, num_keypoints)
            
            T, V, C = skeleton_sequence.shape  # T=幀數, V=關鍵點數, C=3(x,y,score)
            
            # 清理 NaN 值
            skeleton_sequence = np.nan_to_num(skeleton_sequence, nan=0.0)
            
            # 檢查是否有足夠的有效資料
            valid_mask = skeleton_sequence[:, :, 2] > 0.1  # 置信度大於 0.1
            if valid_mask.sum() < T * V * 0.3:  # 至少 30% 的點是有效的
                self.debug_log("Not enough valid keypoints for recognition")
                return None
            
            pose_results = []
            for t in range(T):
                frame_keypoints = skeleton_sequence[t, :, :2]  # (V, 2) - 只取 x, y
                frame_scores = skeleton_sequence[t, :, 2]  # (V,) - 取 score
                
                # 添加 person 維度: (1, V, 2) 和 (1, V)
                pose_results.append({
                    'keypoints': frame_keypoints[np.newaxis, ...].astype(np.float32),  # (1, V, 2)
                    'keypoint_scores': frame_scores[np.newaxis, ...].astype(np.float32)  # (1, V)
                })
            
            # 執行推理
            result = inference_skeleton(
                self.model,
                pose_results,
                img_shape=(480, 640)  # 影像尺寸
            )
            
            if result is not None:
                # 解析結果 - ActionDataSample 格式
                scores = result.pred_score.cpu().numpy()
                top_indices = np.argsort(scores)[::-1][:5]
                
                top_action_idx = top_indices[0]
                top_score = float(scores[top_action_idx])
                
                # 獲取動作標籤
                if top_action_idx < len(config.action.action_labels):
                    action_label = config.action.action_labels[top_action_idx]
                else:
                    action_label = f"動作 {top_action_idx}"
                
                # 建構 Top-K 結果
                top_k_actions = []
                for idx in top_indices:
                    label = config.action.action_labels[idx] if idx < len(config.action.action_labels) else f"動作 {idx}"
                    top_k_actions.append((label, float(scores[idx])))
                
                return ActionResult(
                    person_id=person_id,
                    action_label=action_label,
                    action_description=self._get_description(action_label),
                    confidence=top_score,
                    top_k_actions=top_k_actions,
                    raw_scores=scores
                )
            
            return None
            
        except Exception as e:
            self.debug_log(f"MMAction2 inference error: {e}")
            import traceback
            if config.debug:
                traceback.print_exc()
            return None
    
    def _fallback_inference(
        self, 
        skeleton_sequence: np.ndarray,
        person_id: int
    ) -> Optional[ActionResult]:
        """
        回退模式：基於規則的簡單動作識別
        
        這是一個簡化的動作識別，當 MMAction2 未安裝時使用。
        基於骨架運動特徵進行簡單判斷。
        
        Args:
            skeleton_sequence: 骨架序列
            person_id: 人物 ID
            
        Returns:
            動作識別結果
        """
        if len(skeleton_sequence) < 10:
            return None
        
        # 計算運動特徵
        # 1. 整體移動量
        center_positions = np.mean(skeleton_sequence[:, :, :2], axis=1)  # (T, 2)
        total_movement = np.sum(np.abs(np.diff(center_positions, axis=0)))
        
        # 2. 垂直運動（用於檢測跳躍）
        vertical_movement = np.std(center_positions[:, 1])
        
        # 3. 手臂運動
        # 手腕索引：9 (右手腕), 10 (左手腕)
        wrist_positions = skeleton_sequence[:, [9, 10], :2]
        wrist_movement = np.sum(np.abs(np.diff(wrist_positions, axis=0)))
        
        # 4. 腿部運動
        # 腳踝索引：15 (右腳踝), 16 (左腳踝)
        ankle_positions = skeleton_sequence[:, [15, 16], :2]
        ankle_movement = np.sum(np.abs(np.diff(ankle_positions, axis=0)))
        
        # 5. 姿態高度（用於檢測坐下/站立）
        hip_positions = skeleton_sequence[:, [11, 12], 1]  # 髖部 Y 坐標
        avg_hip_height = np.mean(hip_positions)
        
        # 基於規則判斷動作
        action_scores = {}
        
        # 跳躍檢測
        if vertical_movement > 50:
            action_scores["跳躍"] = min(vertical_movement / 100, 1.0)
        
        # 行走/跑步檢測
        if total_movement > 100:
            if total_movement > 300:
                action_scores["跑步"] = min(total_movement / 500, 1.0)
            else:
                action_scores["走路"] = min(total_movement / 200, 1.0)
        
        # 坐下/站立檢測
        if avg_hip_height > 300:  # 較低的髖部位置
            action_scores["坐著"] = 0.6
        
        # 站立（預設）
        if not action_scores:
            action_scores["站立"] = 0.5
        
        # 找到最高分數的動作
        best_action = max(action_scores.items(), key=lambda x: x[1])
        action_label = best_action[0]
        confidence = best_action[1]
        
        # 建構 Top-K 結果
        sorted_actions = sorted(action_scores.items(), key=lambda x: x[1], reverse=True)
        top_k_actions = sorted_actions[:5]
        
        return ActionResult(
            person_id=person_id,
            action_label=action_label,
            action_description=self._get_description(action_label),
            confidence=confidence,
            top_k_actions=top_k_actions
        )
    
    def recognize_all(
        self, 
        sequences_info: Dict[int, Dict[str, Any]]
    ) -> Dict[int, ActionResult]:
        """
        識別多個人物的動作
        
        Args:
            sequences_info: 字典，鍵為人物 ID，值為包含 sequence, motion, visibility 的字典
            
        Returns:
            字典，鍵為人物 ID，值為動作識別結果
        """
        results = {}
        
        # 清理已經消失的人物 ID
        current_ids = set(sequences_info.keys())
        ids_to_remove = [pid for pid in self.last_results.keys() if pid not in current_ids]
        for pid in ids_to_remove:
            self.last_results.pop(pid, None)
            self.temporal_filters.pop(pid, None)
            self.state_tracker.pop(pid, None)
            
        for person_id, info in sequences_info.items():
            sequence = info.get('sequence')
            motion = info.get('motion', 0.0)
            visibility = info.get('visibility', None)
            
            result = self.recognize(
                sequence, 
                person_id, 
                motion, 
                visibility, 
                info.get('bbox')
            )
            if result:
                results[person_id] = result
        return results
    
    def get_last_results(self) -> Dict[int, ActionResult]:
        """獲取最近的識別結果"""
        return self.last_results.copy()
    
    def get_formatted_description(self) -> str:
        """
        獲取格式化的動作描述（用於 GUI 顯示）
        
        Returns:
            多行格式化描述文字
        """
        if not self.last_results:
            return "未偵測到人物或正在累積資料..."
        
        lines = []
        lines.append("=" * 40)
        lines.append("【動作識別結果】")
        lines.append("=" * 40)
        
        for person_id, result in sorted(self.last_results.items()):
            # 顯示 ReID 的 Person ID
            lines.append(f"\n👤 人物 (ID: {person_id}):")
            
            # 優先顯示簡化標籤
            if result.simplified_label:
                lines.append(f"   動作: {result.simplified_label}")
                if result.motion_status:
                    lines.append(f"   狀態: {result.motion_status}")
            else:
                lines.append(f"   動作: {result.action_label}")
                
            lines.append(f"   描述: {result.action_description}")
            lines.append(f"   信心度: {result.confidence * 100:.1f}%")
            
            if len(result.top_k_actions) > 1:
                lines.append("   其他可能:")
                for action, score in result.top_k_actions[1:3]:
                    lines.append(f"     - {action}: {score * 100:.1f}%")
        
        lines.append("\n" + "=" * 40)
        lines.append(f"推理時間: {self.last_inference_time * 1000:.1f} ms")
        
        return "\n".join(lines)
    
    def is_ready(self) -> bool:
        """檢查識別器是否就緒"""
        return True  # 回退模式始終可用


class ActionRecognizerAsync:
    """
    異步動作識別器
    
    在背景執行緒中執行動作識別，避免阻塞主執行緒
    """
    
    def __init__(self):
        """初始化異步識別器"""
        self.recognizer = ActionRecognizer()
        self.recognition_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.input_queue = threading.Condition()
        self.latest_sequences_info: Optional[Dict[int, Dict[str, Any]]] = None
        self.latest_results: Dict[int, ActionResult] = {}
        self.running = False
        
    def start(self):
        """啟動異步識別"""
        self.stop_event.clear()
        self.running = True
        self.recognition_thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self.recognition_thread.start()
        
    def stop(self):
        """停止異步識別"""
        self.running = False
        self.stop_event.set()
        with self.input_queue:
            self.input_queue.notify_all()
        
    def submit(self, sequences_info: Dict[int, Dict[str, Any]]):
        """
        提交骨架序列進行識別
        
        Args:
            sequences_info: 骨架序列資訊字典
        """
        with self.input_queue:
            self.latest_sequences_info = sequences_info
            self.input_queue.notify()
    
    def _recognition_loop(self):
        """識別執行緒主迴圈"""
        if config.debug:
            print("[ActionRecognizerAsync] Recognition loop started")
        while not self.stop_event.is_set():
            with self.input_queue:
                while self.latest_sequences_info is None and not self.stop_event.is_set():
                    self.input_queue.wait(timeout=0.5)
                
                if self.stop_event.is_set():
                    break
                    
                sequences_info = self.latest_sequences_info
                self.latest_sequences_info = None
            
            if sequences_info is not None:
                if config.debug:
                    print(f"[ActionRecognizerAsync] Processing {len(sequences_info)} person(s)")
                results = self.recognizer.recognize_all(sequences_info)
                
                # 即使結果為空也更新，這樣才能刪除消失的人物
                self.latest_results = results
                
                if config.debug:
                    print(f"[ActionRecognizerAsync] Got {len(results)} result(s)")
            else:
                if config.debug:
                    print("[ActionRecognizerAsync] No sequences info to process")
    
    def get_results(self) -> Dict[int, ActionResult]:
        """獲取最新的識別結果"""
        return self.latest_results.copy()
    
    def get_current_result(self, person_id: int) -> Optional[ActionResult]:
        """
        獲取指定人物的最新識別結果
        
        Args:
            person_id: 人物 ID
            
        Returns:
            識別結果，如果沒有則返回 None
        """
        return self.latest_results.get(person_id)
    
    def get_formatted_description(self) -> str:
        """獲取格式化描述"""
        return self.recognizer.get_formatted_description()
