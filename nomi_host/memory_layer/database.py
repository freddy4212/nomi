"""
database.py - 資料庫管理模組

負責：
- PostgreSQL + TimescaleDB + pgvector 連線管理
- 資料表建立與遷移
- 基本的 CRUD 操作封裝

需要安裝：
    pip install psycopg2-binary
"""

import json
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

try:
    from .config import memory_config
    from .data_models import MemberState, PerceptionEvent
except (ImportError, ValueError):
    from config import memory_config
    from data_models import MemberState, PerceptionEvent

# 嘗試導入 numpy (用於處理感知層傳來的數值類型)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# 嘗試導入 psycopg2
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None


def _ensure_python_type(val: Any) -> Any:
    """
    確保數值為 Python 原生類型，避免 psycopg2 無法處理 numpy 類型
    """
    if not NUMPY_AVAILABLE:
        return val
    
    if isinstance(val, (np.float32, np.float64, np.float16)):
        return float(val)
    if isinstance(val, (np.int32, np.int64, np.int16, np.int8)):
        return int(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, list):
        return [_ensure_python_type(item) for item in val]
    return val


class DatabaseError(Exception):
    """資料庫錯誤"""
    pass


class DatabaseNotConnectedError(DatabaseError):
    """資料庫未連線錯誤"""
    pass


class DatabaseManager:
    """
    資料庫管理器
    
    使用 PostgreSQL + TimescaleDB + pgvector 作為記憶層儲存。
    """
    
    def __init__(self):
        """初始化資料庫管理器"""
        self.config = memory_config.database
        self._local = threading.local()
        self._connected = False
        self._connection_error: Optional[str] = None
        
        # 嘗試連線
        self._try_connect()
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if memory_config.debug:
            print(f"[MemoryDB][{time.time():.3f}] {msg}")
    
    @property
    def is_connected(self) -> bool:
        """是否已連線到資料庫"""
        return self._connected
    
    @property
    def connection_error(self) -> Optional[str]:
        """連線錯誤訊息"""
        return self._connection_error
    
    def _try_connect(self) -> bool:
        """嘗試連線到資料庫"""
        if not PSYCOPG2_AVAILABLE:
            self._connection_error = "psycopg2 未安裝，請執行: pip install psycopg2-binary"
            self.debug_log(self._connection_error)
            return False
        
        try:
            conn = self._get_connection()
            if conn:
                self._init_database()
                self._connected = True
                self._connection_error = None
                self.debug_log("DatabaseManager connected to PostgreSQL")
                return True
        except Exception as e:
            self._connected = False
            self._connection_error = str(e)
            self.debug_log(f"Database connection failed: {e}")
            return False
    
    def _get_connection(self):
        """取得執行緒安全的資料庫連線"""
        if not PSYCOPG2_AVAILABLE:
            raise DatabaseError("psycopg2 未安裝")
        
        if not hasattr(self._local, 'connection') or self._local.connection is None or self._local.connection.closed:
            try:
                self._local.connection = psycopg2.connect(**self.config.get_dsn())
                self._local.connection.autocommit = False
            except psycopg2.OperationalError as e:
                raise DatabaseNotConnectedError(f"無法連線到 PostgreSQL: {e}")
        return self._local.connection
    
    @contextmanager
    def get_cursor(self) -> Generator:
        """取得資料庫游標的 Context Manager"""
        if not self._connected:
            raise DatabaseNotConnectedError("資料庫未連線")
        
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.debug_log(f"Database error: {e}")
            raise
        finally:
            cursor.close()

    def get_iot_devices(self) -> List[Dict[str, Any]]:
        """取得所有 IoT 裝置"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT * FROM iot_devices ORDER BY device_id ASC")
                return cursor.fetchall()
        except Exception as e:
            self.debug_log(f"Error fetching IoT devices: {e}")
            return []

    def add_iot_device(self, name: str, type: str, location: str = "", description: str = "", icon: str = "Cpu") -> bool:
        """新增 IoT 裝置"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO iot_devices (name, type, location, description, icon) VALUES (%s, %s, %s, %s, %s)",
                    (name, type, location, description, icon)
                )
                return True
        except Exception as e:
            self.debug_log(f"Error adding IoT device: {e}")
            return False
    
    def _init_database(self):
        """初始化資料庫結構"""
        self.debug_log(f"Initializing database: {self.config.database}")
        
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # === 啟用擴展 ===
            if self.config.use_timescaledb:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                self.debug_log("TimescaleDB extension enabled")
            
            if self.config.use_pgvector:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                self.debug_log("pgvector extension enabled")
            
            # === 成員註冊表 ===
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS member_registry (
                    member_id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    reid_vector vector({self.config.vector_dimension}),
                    habit_profile JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    sample_count INTEGER DEFAULT 1
                )
            ''')
            
            # === 統一時序流 (核心記憶表) ===
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS unified_telemetry (
                    id BIGSERIAL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    frame_no INTEGER NOT NULL,
                    person_id INTEGER NOT NULL,
                    matched_member_id INTEGER REFERENCES member_registry(member_id),
                    bbox JSONB,
                    keypoints JSONB,
                    visibility BOOLEAN DEFAULT TRUE,
                    action_label TEXT,
                    action_confidence REAL,
                    action_candidates JSONB,
                    action_duration REAL DEFAULT 0,
                    motion_magnitude REAL DEFAULT 0,
                    environment JSONB,
                    reid_vector vector({self.config.vector_dimension}),
                    source_device TEXT DEFAULT 'WiseEye2',
                    PRIMARY KEY (timestamp, id)
                )
            ''')
            
            # 將 unified_telemetry 轉換為 TimescaleDB hypertable
            if self.config.use_timescaledb:
                cursor.execute('''
                    SELECT create_hypertable('unified_telemetry', 'timestamp', 
                        if_not_exists => TRUE,
                        migrate_data => TRUE
                    )
                ''')
                self.debug_log("unified_telemetry converted to hypertable")
            
            # 建立索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_telemetry_person 
                ON unified_telemetry(person_id, timestamp DESC)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_telemetry_action 
                ON unified_telemetry(action_label, timestamp DESC)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_telemetry_member 
                ON unified_telemetry(matched_member_id, timestamp DESC)
            ''')
            
            # === 成員狀態快照表 ===
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS member_state_snapshot (
                    person_id INTEGER PRIMARY KEY,
                    member_id INTEGER REFERENCES member_registry(member_id),
                    member_name TEXT,
                    last_seen_time TIMESTAMPTZ,
                    last_bbox JSONB,
                    last_action TEXT,
                    last_action_start TIMESTAMPTZ,
                    last_location TEXT,
                    last_action_duration REAL DEFAULT 0,
                    is_visible BOOLEAN DEFAULT TRUE,
                    disappear_direction TEXT,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')

            # === IoT 裝置管理表 ===
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS iot_devices (
                    device_id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT DEFAULT 'Online',
                    location TEXT,
                    description TEXT,
                    icon TEXT,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')

            # 插入範例資料 (如果表是空的或缺少新裝置)
            cursor.execute("SELECT COUNT(*) as count FROM iot_devices")
            current_count = cursor.fetchone()['count']
            if current_count < 11:
                # 如果資料不夠，先清空再重新插入完整的範例集 (開發階段方便同步)
                if current_count > 0:
                    cursor.execute("TRUNCATE TABLE iot_devices RESTART IDENTITY")
                
                sample_devices = [
                    ('客廳空調', 'Air Conditioner', 'Online', '客廳', '大金變頻空調', 'Wind'),
                    ('主臥照明', 'Light', 'Online', '主臥室', '智慧調光燈', 'Lightbulb'),
                    ('廚房冰箱', 'Refrigerator', 'Online', '廚房', '智慧溫控冰箱', 'Refrigerator'),
                    ('掃地機器人', 'Robot Vacuum', 'Online', '全屋', '石頭掃地機 S8', 'Disc'),
                    ('電視', 'TV', 'Offline', '客廳', 'Sony 65吋 4K 電視', 'Tv'),
                    ('智慧音箱', 'Speaker', 'Online', '書房', 'HomePod mini', 'Speaker'),
                    ('門鎖', 'Door Lock', 'Online', '玄關', '鹿客智慧門鎖', 'Lock'),
                    ('香氛機', 'Fragrance', 'Online', '客廳', '無印良品超音波芬香噴霧器', 'Waves'),
                    ('電動窗簾', 'Curtains', 'Online', '主臥室', 'Aqara 智慧窗簾電機', 'Columns'),
                    ('緊急按鈕', 'Emergency Button', 'Online', '浴室', '無線緊急求助按鈕', 'Bell'),
                    ('全熱交換機', 'HRV', 'Online', '陽台', '大金全熱交換器', 'Fan')
                ]
                cursor.executemany('''
                    INSERT INTO iot_devices (name, type, status, location, description, icon)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', sample_devices)
            
            # 嘗試新增欄位 (如果表已存在但欄位不存在)
            try:
                cursor.execute("ALTER TABLE member_state_snapshot ADD COLUMN IF NOT EXISTS last_location TEXT;")
                cursor.execute("ALTER TABLE member_state_snapshot ADD COLUMN IF NOT EXISTS last_action_duration REAL DEFAULT 0;")
                cursor.execute("ALTER TABLE unified_telemetry ADD COLUMN IF NOT EXISTS keypoints JSONB;")
            except Exception as e:
                self.debug_log(f"Column migration warning: {e}")
            
            conn.commit()
            self.debug_log("Database tables created/verified")
            
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"初始化資料庫失敗: {e}")
        finally:
            cursor.close()
    
    # ==================== 寫入操作 ====================
    
    def insert_perception_event(self, event: PerceptionEvent) -> int:
        """
        寫入感知事件
        
        Args:
            event: 感知事件物件
            
        Returns:
            插入的記錄 ID
        """
        if not self._connected:
            return -1
        
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO unified_telemetry (
                    timestamp, frame_no, person_id, matched_member_id,
                    bbox, keypoints, visibility, action_label, action_confidence,
                    action_candidates, action_duration, motion_magnitude,
                    environment, reid_vector, source_device
                ) VALUES (
                    to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            ''', (
                event.timestamp,
                event.frame_no,
                event.person_id,
                event.matched_member_id,
                json.dumps(event.bbox.to_list()) if event.bbox else None,
                json.dumps(event.keypoints) if event.keypoints else None,
                event.visibility,
                event.action_label,
                event.action_confidence,
                json.dumps([c.to_dict() for c in event.action_candidates]),
                event.action_duration,
                event.motion_magnitude,
                json.dumps(event.environment.to_dict()) if event.environment else None,
                event.reid_vector,  # pgvector 會自動處理 list
                event.source_device,
            ))
            result = cursor.fetchone()
            return result['id'] if result else -1
    
    def check_persistent_inactivity(self, person_id: int, duration_minutes: int, threshold: float) -> bool:
        """
        檢查某人是否在過去 X 分鐘內的平均動作幅度都低於閾值
        這是支援 RuleEngine 的 Hybrid 查詢功能
        """
        if not self.is_connected:
            return False
            
        try:
            with self.get_cursor() as cursor:
                # 使用 TimescaleDB 強大的時間桶查詢
                # 我們不查詢每一筆，而是查詢聚合後的統計，效率極高
                query = """
                    SELECT AVG(motion_magnitude)
                    FROM unified_telemetry
                    WHERE person_id = %s
                      AND timestamp > (NOW() - INTERVAL '%s minutes')
                """
                cursor.execute(query, (person_id, duration_minutes))
                result = cursor.fetchone()
                
                if result and result['avg'] is not None:
                    avg_motion = float(result['avg'])
                    # 如果平均動作小於閾值，判定為長時間靜止
                    return avg_motion < threshold
                return False
        except Exception as e:
            self.debug_log(f"Check inactivity error: {e}")
            return False

    def insert_perception_events_batch(self, events: List[PerceptionEvent]) -> int:
        """
        批次寫入感知事件
        
        Args:
            events: 感知事件列表
            
        Returns:
            成功插入的記錄數
        """
        if not events or not self._connected:
            return 0
        
        with self.get_cursor() as cursor:
            data = []
            for event in events:
                data.append((
                    event.timestamp,
                    event.frame_no,
                    event.person_id,
                    event.matched_member_id,
                    json.dumps(event.bbox.to_list()) if event.bbox else None,
                    json.dumps(event.keypoints) if event.keypoints else None,
                    _ensure_python_type(event.visibility),
                    event.action_label,
                    _ensure_python_type(event.action_confidence),
                    json.dumps([c.to_dict() for c in event.action_candidates]),
                    _ensure_python_type(event.action_duration),
                    _ensure_python_type(event.motion_magnitude),
                    json.dumps(event.environment.to_dict()) if event.environment else None,
                    _ensure_python_type(event.reid_vector),
                    event.source_device,
                ))
            
            psycopg2.extras.execute_batch(cursor, '''
                INSERT INTO unified_telemetry (
                    timestamp, frame_no, person_id, matched_member_id,
                    bbox, keypoints, visibility, action_label, action_confidence,
                    action_candidates, action_duration, motion_magnitude,
                    environment, reid_vector, source_device
                ) VALUES (
                    to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s
                )
            ''', data)
            
            return len(data)
    
    def update_member_state(self, state: MemberState):
        """
        更新成員狀態快照
        
        Args:
            state: 成員狀態物件
        """
        if not self._connected:
            return
        
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO member_state_snapshot (
                    person_id, member_id, member_name,
                    last_seen_time, last_bbox, last_action,
                    last_action_start, last_location, last_action_duration,
                    is_visible, disappear_direction,
                    updated_at
                ) VALUES (%s, %s, %s, to_timestamp(%s), %s, %s, to_timestamp(%s), %s, %s, %s, %s, NOW())
                ON CONFLICT (person_id) DO UPDATE SET
                    member_id = EXCLUDED.member_id,
                    member_name = EXCLUDED.member_name,
                    last_seen_time = EXCLUDED.last_seen_time,
                    last_bbox = EXCLUDED.last_bbox,
                    last_action = EXCLUDED.last_action,
                    last_action_start = EXCLUDED.last_action_start,
                    last_location = EXCLUDED.last_location,
                    last_action_duration = EXCLUDED.last_action_duration,
                    is_visible = EXCLUDED.is_visible,
                    disappear_direction = EXCLUDED.disappear_direction,
                    updated_at = NOW()
            ''', (
                state.person_id,
                state.member_id,
                state.member_name,
                state.last_seen_time,
                json.dumps(state.last_bbox.to_list()) if state.last_bbox else None,
                state.last_action,
                state.last_action_start,
                state.last_location,
                state.last_action_duration,
                state.is_visible,
                state.disappear_direction,
            ))
    
    # ==================== 查詢操作 ====================
    
    def query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        執行自定義 SQL 查詢
        
        Args:
            sql: SQL 語句
            params: 參數元組
            
        Returns:
            查詢結果列表
        """
        if not self._connected:
            return []
        
        with self.get_cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()

    def get_person_history(
        self, 
        person_id: int, 
        duration_sec: float = 60.0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查詢某人的歷史記錄
        
        Args:
            person_id: 人物 ID
            duration_sec: 往回查詢的秒數
            limit: 最大返回筆數
            
        Returns:
            歷史記錄列表
        """
        if not self._connected:
            return []
        
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM unified_telemetry
                WHERE person_id = %s AND timestamp >= NOW() - (%s || ' seconds')::interval
                ORDER BY timestamp DESC
                LIMIT %s
            ''', (person_id, duration_sec, limit))
            
            return cursor.fetchall()
    
    def get_member_states(self) -> List[Dict[str, Any]]:
        """
        取得所有成員的當前狀態 (包含成員名稱)
        
        Returns:
            成員狀態列表
        """
        if not self._connected:
            return []
        
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT s.*, m.name as member_name
                FROM member_state_snapshot s
                LEFT JOIN member_registry m ON s.member_id = m.member_id
                ORDER BY s.last_seen_time DESC
            ''')
            return cursor.fetchall()
    
    def get_recent_events(
        self, 
        duration_sec: float = 60.0,
        action_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查詢最近的事件 (包含成員名稱)
        
        Args:
            duration_sec: 往回查詢的秒數
            action_filter: 動作標籤過濾 (可選)
            limit: 最大返回筆數
            
        Returns:
            事件列表
        """
        if not self._connected:
            return []
        
        with self.get_cursor() as cursor:
            base_query = '''
                SELECT t.*, m.name as member_name
                FROM unified_telemetry t
                LEFT JOIN member_registry m ON t.matched_member_id = m.member_id
                WHERE t.timestamp >= NOW() - (%s || ' seconds')::interval
            '''
            
            if action_filter:
                cursor.execute(base_query + ' AND t.action_label = %s ORDER BY t.timestamp DESC LIMIT %s', 
                               (duration_sec, action_filter, limit))
            else:
                cursor.execute(base_query + ' ORDER BY t.timestamp DESC LIMIT %s', 
                               (duration_sec, limit))
            
            return cursor.fetchall()

    def get_events_in_range(
        self,
        member_id: int,
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        """
        查詢指定成員在特定時間範圍內的事件
        
        Args:
            member_id: 成員 ID
            start_time: 開始時間戳 (Unix Timestamp)
            end_time: 結束時間戳 (Unix Timestamp)
            
        Returns:
            事件列表
        """
        if not self._connected:
            return []
            
        with self.get_cursor() as cursor:
            # Debug: Check what's in the DB for this member
            cursor.execute("SELECT COUNT(*) FROM unified_telemetry WHERE matched_member_id = %s", (member_id,))
            result = cursor.fetchone()
            total_count = result['count'] if result and member_id != 0 else 0
            
            if member_id == 0:
                # 查詢未知訪客 (matched_member_id 為 NULL)
                cursor.execute('''
                    SELECT t.*, '未知訪客' as member_name
                    FROM unified_telemetry t
                    WHERE t.matched_member_id IS NULL
                    AND t.timestamp >= to_timestamp(%s) - interval '2 seconds'
                    AND t.timestamp <= to_timestamp(%s) + interval '2 seconds'
                    ORDER BY t.timestamp ASC
                ''', (start_time, end_time))
            elif member_id == -1:
                # 特別模式：查詢時間範圍內的所有事件 (用於評估/除錯)
                cursor.execute('''
                    SELECT t.*, COALESCE(m.name, '未知訪客') as member_name
                    FROM unified_telemetry t
                    LEFT JOIN member_registry m ON t.matched_member_id = m.member_id
                    WHERE t.timestamp >= to_timestamp(%s) - interval '2 seconds'
                    AND t.timestamp <= to_timestamp(%s) + interval '2 seconds'
                    ORDER BY t.timestamp ASC
                ''', (start_time, end_time))
            else:
                # 這裡優先查詢 matched_member_id，若無則查 person_id
                cursor.execute('''
                    SELECT t.*, m.name as member_name
                    FROM unified_telemetry t
                    LEFT JOIN member_registry m ON t.matched_member_id = m.member_id
                    WHERE (t.matched_member_id = %s OR t.person_id = %s)
                    AND t.timestamp >= to_timestamp(%s) - interval '2 seconds'
                    AND t.timestamp <= to_timestamp(%s) + interval '2 seconds'
                    ORDER BY t.timestamp ASC
                ''', (member_id, member_id, start_time, end_time))
            
            results = cursor.fetchall()
            print(f"[Database] Range query for member {member_id}: {len(results)} results (Total in DB for member: {total_count})")
            return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        取得資料庫統計資訊
        
        Returns:
            統計資訊字典
        """
        if not self._connected:
            return {
                "connected": False,
                "error": self._connection_error,
            }
        
        with self.get_cursor() as cursor:
            # 總記錄數
            cursor.execute('SELECT COUNT(*) as count FROM unified_telemetry')
            total_records = cursor.fetchone()['count']
            
            # 今日記錄數
            cursor.execute('''
                SELECT COUNT(*) as count FROM unified_telemetry 
                WHERE timestamp >= CURRENT_DATE
            ''')
            today_records = cursor.fetchone()['count']
            
            # 成員數
            cursor.execute('SELECT COUNT(*) as count FROM member_registry')
            member_count = cursor.fetchone()['count']
            
            # 活躍狀態數
            cursor.execute('SELECT COUNT(*) as count FROM member_state_snapshot')
            active_states = cursor.fetchone()['count']
            
            return {
                "connected": True,
                "total_records": total_records,
                "today_records": today_records,
                "member_count": member_count,
                "active_states": active_states,
                "database": f"PostgreSQL @ {self.config.host}:{self.config.port}/{self.config.database}",
            }
    
    # ==================== 成員管理 (ReID) ====================
    
    def register_member(self, name: str, vector: List[float]) -> int:
        """
        註冊新成員或更新現有成員的向量
        
        Args:
            name: 成員名稱
            vector: ReID 特徵向量
            
        Returns:
            成員 ID
        """
        if not self._connected:
            return -1
            
        with self.get_cursor() as cursor:
            # 使用 PostgreSQL 的 ON CONFLICT 語法進行 Upsert
            cursor.execute('''
                INSERT INTO member_registry (name, reid_vector, updated_at)
                VALUES (%s, %s::vector, NOW())
                ON CONFLICT (name) 
                DO UPDATE SET 
                    reid_vector = EXCLUDED.reid_vector,
                    updated_at = NOW(),
                    sample_count = member_registry.sample_count + 1
                RETURNING member_id
            ''', (name, _ensure_python_type(vector)))
            result = cursor.fetchone()
            return result['member_id'] if result else -1

    def delete_member(self, name: str) -> bool:
        """刪除成員"""
        if not self._connected:
            return False
        with self.get_cursor() as cursor:
            # 先取得 member_id
            cursor.execute('SELECT member_id FROM member_registry WHERE name = %s', (name,))
            res = cursor.fetchone()
            if not res:
                return False
            member_id = res['member_id']
            
            # 解除 unified_telemetry 的關聯 (設為 NULL)
            cursor.execute('UPDATE unified_telemetry SET matched_member_id = NULL WHERE matched_member_id = %s', (member_id,))
            
            # 解除 member_state_snapshot 的關聯
            cursor.execute('UPDATE member_state_snapshot SET member_id = NULL, member_name = NULL WHERE member_id = %s', (member_id,))
            
            # 刪除成員
            cursor.execute('DELETE FROM member_registry WHERE member_id = %s', (member_id,))
            return True

    def delete_member_by_id(self, member_id: int) -> bool:
        """透過 ID 刪除成員"""
        if not self._connected:
            return False
        with self.get_cursor() as cursor:
            # 解除 unified_telemetry 的關聯 (設為 NULL)
            cursor.execute('UPDATE unified_telemetry SET matched_member_id = NULL WHERE matched_member_id = %s', (member_id,))
            
            # 解除 member_state_snapshot 的關聯
            cursor.execute('UPDATE member_state_snapshot SET member_id = NULL, member_name = NULL WHERE member_id = %s', (member_id,))
            
            # 刪除成員
            cursor.execute('DELETE FROM member_registry WHERE member_id = %s', (member_id,))
            return True

    def update_member_name(self, member_id: int, new_name: str) -> bool:
        """更新成員名稱"""
        if not self._connected:
            return False
        with self.get_cursor() as cursor:
            cursor.execute('UPDATE member_registry SET name = %s, updated_at = NOW() WHERE member_id = %s', (new_name, member_id))
            return cursor.rowcount > 0

    def delete_all_members(self) -> bool:
        """刪除所有成員"""
        if not self._connected:
            return False
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM member_registry')
            return True

    def clear_all_data(self) -> bool:
        """清除所有資料 (保留成員註冊表)"""
        if not self._connected:
            self.debug_log("Cannot clear data: Database not connected")
            return False
        try:
            self.debug_log("Executing TRUNCATE on unified_telemetry and member_state_snapshot...")
            with self.get_cursor() as cursor:
                # 清除遙測資料和狀態快照
                cursor.execute('TRUNCATE TABLE unified_telemetry, member_state_snapshot CASCADE')
            self.debug_log("Database cleared successfully")
            return True
        except Exception as e:
            self.debug_log(f"Clear all data error: {e}")
            return False

    def get_all_members(self) -> List[Dict[str, Any]]:
        """取得所有已註冊成員"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cursor.execute('SELECT member_id, name, reid_vector, sample_count, created_at, updated_at FROM member_registry ORDER BY name')
                result = cursor.fetchall()
                conn.commit()
                return result
            finally:
                cursor.close()
        except Exception as e:
            self.debug_log(f"get_all_members error: {e}")
            # 清除可能損壞的連線
            if hasattr(self._local, 'connection'):
                try:
                    self._local.connection.close()
                except:
                    pass
                self._local.connection = None
            return []

    def find_nearest_member(self, vector: List[float], threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        尋找最接近的成員 (使用 pgvector 的餘弦距離)
        
        Args:
            vector: 待比對的向量
            threshold: 距離閾值 (餘弦距離越小越接近，0 為完全相同)
            
        Returns:
            最接近的成員資料，若未找到或超過閾值則返回 None
        """
        if not self.config.use_pgvector:
            return None
        
        # 驗證向量
        if vector is None or len(vector) == 0:
            return None
            
        try:
            # 確保連線可用（多線程環境下可能需要重新連線）
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            try:
                # 確保向量是 Python list
                vec_list = _ensure_python_type(vector)
                
                # <=> 是餘弦距離 (Cosine Distance)
                cursor.execute('''
                    SELECT member_id, name, reid_vector <=> %s::vector as distance
                    FROM member_registry
                    ORDER BY distance ASC
                    LIMIT 1
                ''', (vec_list,))
                result = cursor.fetchone()
                conn.commit()
                
                if result and result['distance'] <= threshold:
                    return result
                return None
            finally:
                cursor.close()
                
        except Exception as e:
            self.debug_log(f"find_nearest_member error: {e}")
            # 清除可能損壞的連線
            if hasattr(self._local, 'connection'):
                try:
                    self._local.connection.close()
                except:
                    pass
                self._local.connection = None
            return None

    def close(self):
        """關閉資料庫連線"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
            self._connected = False
            self.debug_log("Database connection closed")
