"""
temporal_filter.py - 動作識別時序濾波器
"""

from collections import deque
from typing import Tuple


class TemporalFilter:
    """使用滑動窗口投票機制穩定識別結果"""

    def __init__(self, window_size: int = 2, min_confidence: float = 0.3):
        self.window_size = window_size
        self.min_confidence = min_confidence
        self.history = deque(maxlen=window_size)
        self.current_stable_label = "等待中..."
        self.current_stable_confidence = 0.0

    def update(self, label: str, confidence: float) -> Tuple[str, float]:
        """添加新結果並返回穩定的結果"""
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
