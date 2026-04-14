import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Import data models
try:
    from ...data_models import MemberState, PerceptionEvent
except (ImportError, ValueError):
    from data_models import MemberState, PerceptionEvent

@dataclass
class RuleResult:
    triggered: bool
    label: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class TimeWindowBuffer:
    """每個使用者的時間窗口緩衝區"""
    def __init__(self, window_size_sec: float = 10.0):
        self.window_size_sec = window_size_sec
        self.events: deque[PerceptionEvent] = deque()

    def add(self, event: PerceptionEvent):
        self.events.append(event)
        self._cleanup()

    def _cleanup(self):
        if not self.events:
            return
        current_ts = self.events[-1].timestamp
        while self.events and (current_ts - self.events[0].timestamp > self.window_size_sec):
            self.events.popleft()

    def get_events(self) -> List[PerceptionEvent]:
        return list(self.events)

    def get_motion_trend(self) -> float:
        """計算這段時間內的平均動作幅度"""
        if not self.events:
            return 0.0
        motions = [e.motion_magnitude for e in self.events]
        return sum(motions) / len(motions)

    def check_persistent_action(self, label: str, persistence_ratio: float = 0.8) -> bool:
        """檢查某個動作是否持續存在"""
        if not self.events:
            return False
        
        matches = sum(1 for e in self.events if e.action_label == label)
        return (matches / len(self.events)) >= persistence_ratio

class RuleEngine:
    """
    規則引擎 (Rule-Based Logic)
    
    用於在 Memory Layer 中執行即時邏輯判斷，
    可基於數據趨勢 (Trend) 觸發高層次事件。
    支援混合查詢：即時緩衝區 (RAM) + 歷史資料庫 (DB)。
    """
    def __init__(self, db_manager=None):
        self.buffers: Dict[int, TimeWindowBuffer] = {} # person_id -> Buffer
        self.rules: List[Callable[[TimeWindowBuffer, MemberState, Optional[Any]], Optional[RuleResult]]] = []
        self.db_manager = db_manager
        self.lock = threading.RLock()
        
        # 註冊預設規則
        self._register_default_rules()
        print("[RuleEngine] Initialized with default rules" + (" (DB enabled)" if db_manager else ""))

    def _register_default_rules(self):
        # 範例規則 1: 偵測短時間靜止 (RAM only)
        # 判斷最近 10 秒 (RAM Buffer) 是否靜止
        def check_short_rest(buffer: TimeWindowBuffer, state: MemberState, db=None) -> Optional[RuleResult]:
            # 如果動作幅度持續低於閾值且持續 5 秒以上
            avg_motion = buffer.get_motion_trend()
            # 必須要有足夠的樣本 (30幀) 且 buffer 滿了才算
            if len(buffer.events) > 30 and avg_motion < 2.0:
                return RuleResult(
                    triggered=True,
                    label="短暫靜止",
                    description=f"偵測到用戶 {state.person_id} 短暫靜止",
                    metadata={"avg_motion": avg_motion, "duration": "10s"}
                )
            return None
        
        # 範例規則 2: 偵測長時間靜止 (RAM + DB Hybrid)
        # 如果 RAM 顯示靜止，進一步查詢 DB 確認過去 1 小時狀態
        def check_long_rest(buffer: TimeWindowBuffer, state: MemberState, db=None) -> Optional[RuleResult]:
            # 1. Fast Check: 如果最近 10 秒還在動，那肯定沒靜止 1 小時，直接 return
            avg_motion = buffer.get_motion_trend()
            if len(buffer.events) < 30 or avg_motion >= 2.0:
                return None
            
            # 2. Slow Check: 查詢 DB (如果 DB 有連接)
            # 這裡我們模擬一個假設的 DB 查詢函數，實務上需要在 DatabaseManager 實作
            # 例如: is_inactive = db.check_activity_level(person_id, duration_minutes=60, threshold=2.0)
            if db and hasattr(db, "check_persistent_inactivity"):
                # 假設我們定義一個小時 (60分鐘)
                is_long_inactive = db.check_persistent_inactivity(
                    person_id=state.person_id, 
                    duration_minutes=60, 
                    threshold=2.0
                )
                
                if is_long_inactive:
                    return RuleResult(
                        triggered=True,
                        label="長時間靜止",
                        description=f"用戶 {state.person_id} 已靜止超过 1 小时",
                        metadata={"avg_motion": avg_motion, "duration": "1h"}
                    )
            return None
        
        self.rules.append(check_short_rest)
        self.rules.append(check_long_rest)

    def process_event(self, event: PerceptionEvent, state: Optional[MemberState]) -> List[RuleResult]:
        """處理新事件並執行規則檢查"""
        pid = event.person_id
        if pid is None:
            return []

        with self.lock:
            # 1. 更新緩衝區
            if pid not in self.buffers:
                self.buffers[pid] = TimeWindowBuffer(window_size_sec=10.0) # 預設 10 秒窗口
            
            buffer = self.buffers[pid]
            buffer.add(event)
            
            if not state:
                return []

            # 2. 執行所有規則
            results = []
            for rule in self.rules:
                try:
                    # 傳入 DB manager 供規則使用
                    res = rule(buffer, state, self.db_manager)
                    if res and res.triggered:
                        results.append(res)
                except Exception as e:
                    print(f"[RuleEngine] Error executing rule: {e}")
            
            return results

    def add_rule(self, rule_func: Callable[[TimeWindowBuffer, MemberState], Optional[RuleResult]]):
        """動態新增規則"""
        with self.lock:
            self.rules.append(rule_func)
