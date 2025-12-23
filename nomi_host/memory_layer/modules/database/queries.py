"""
queries.py - SQL 查詢建構器

負責：
- 建構常用的 SQL 查詢
- 提供類型安全的查詢介面
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class QueryResult:
    """查詢結果封裝"""
    sql: str
    params: Tuple


class QueryBuilder:
    """
    SQL 查詢建構器
    
    提供類型安全的查詢建構介面，避免 SQL 注入並提高可讀性。
    """
    
    # ==================== 事件查詢 ====================
    
    @staticmethod
    def recent_events(
        duration_sec: float = 60.0,
        action_filter: Optional[str] = None,
        limit: int = 100
    ) -> QueryResult:
        """
        建構最近事件查詢
        
        Args:
            duration_sec: 往回查詢的秒數
            action_filter: 動作標籤過濾
            limit: 最大返回筆數
        """
        base_query = '''
            SELECT t.*, m.name as member_name
            FROM unified_telemetry t
            LEFT JOIN member_registry m ON t.matched_member_id = m.member_id
            WHERE t.timestamp >= NOW() - (%s || ' seconds')::interval
        '''
        
        if action_filter:
            return QueryResult(
                sql=base_query + ' AND t.action_label = %s ORDER BY t.timestamp DESC LIMIT %s',
                params=(duration_sec, action_filter, limit)
            )
        else:
            return QueryResult(
                sql=base_query + ' ORDER BY t.timestamp DESC LIMIT %s',
                params=(duration_sec, limit)
            )
    
    @staticmethod
    def person_history(
        person_id: int,
        duration_sec: float = 60.0,
        limit: int = 100
    ) -> QueryResult:
        """建構個人歷史查詢"""
        return QueryResult(
            sql='''
                SELECT * FROM unified_telemetry
                WHERE person_id = %s AND timestamp >= NOW() - (%s || ' seconds')::interval
                ORDER BY timestamp DESC
                LIMIT %s
            ''',
            params=(person_id, duration_sec, limit)
        )
    
    @staticmethod
    def member_states() -> QueryResult:
        """建構成員狀態查詢"""
        return QueryResult(
            sql='''
                SELECT s.*, m.name as member_name
                FROM member_state_snapshot s
                LEFT JOIN member_registry m ON s.member_id = m.member_id
                ORDER BY s.last_seen_time DESC
            ''',
            params=()
        )
    
    # ==================== 成員管理 ====================
    
    @staticmethod
    def all_members() -> QueryResult:
        """建構所有成員查詢"""
        return QueryResult(
            sql='''
                SELECT member_id, name, reid_vector, sample_count, created_at, updated_at 
                FROM member_registry 
                ORDER BY name
            ''',
            params=()
        )
    
    @staticmethod
    def register_member(name: str, vector: List[float]) -> QueryResult:
        """建構成員註冊/更新查詢"""
        return QueryResult(
            sql='''
                INSERT INTO member_registry (name, reid_vector, updated_at)
                VALUES (%s, %s::vector, NOW())
                ON CONFLICT (name) 
                DO UPDATE SET 
                    reid_vector = EXCLUDED.reid_vector,
                    updated_at = NOW(),
                    sample_count = member_registry.sample_count + 1
                RETURNING member_id
            ''',
            params=(name, vector)
        )
    
    @staticmethod
    def find_nearest_member(vector: List[float]) -> QueryResult:
        """建構最近鄰成員查詢"""
        return QueryResult(
            sql='''
                SELECT member_id, name, reid_vector <=> %s::vector as distance
                FROM member_registry
                ORDER BY distance ASC
                LIMIT 1
            ''',
            params=(vector,)
        )
    
    # ==================== 統計查詢 ====================
    
    @staticmethod
    def total_records() -> QueryResult:
        """總記錄數"""
        return QueryResult(
            sql='SELECT COUNT(*) as count FROM unified_telemetry',
            params=()
        )
    
    @staticmethod
    def today_records() -> QueryResult:
        """今日記錄數"""
        return QueryResult(
            sql='SELECT COUNT(*) as count FROM unified_telemetry WHERE timestamp >= CURRENT_DATE',
            params=()
        )
    
    @staticmethod
    def member_count() -> QueryResult:
        """成員數"""
        return QueryResult(
            sql='SELECT COUNT(*) as count FROM member_registry',
            params=()
        )
    
    @staticmethod
    def active_states_count() -> QueryResult:
        """活躍狀態數"""
        return QueryResult(
            sql='SELECT COUNT(*) as count FROM member_state_snapshot',
            params=()
        )
