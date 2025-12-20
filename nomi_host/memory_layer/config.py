"""
config.py - 記憶層配置

集中管理所有記憶層相關的配置參數
記憶層專用 PostgreSQL + TimescaleDB + pgvector
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """PostgreSQL 資料庫連線配置"""
    # PostgreSQL 連線參數
    host: str = "localhost"
    port: int = 5432
    database: str = "home_agent"
    user: str = "home_agent"
    password: str = "home_agent_pwd"
    
    # 連線池設定
    min_connections: int = 1
    max_connections: int = 5
    
    # 連線超時 (秒)
    connect_timeout: int = 10
    
    # 是否啟用 TimescaleDB 擴展
    use_timescaledb: bool = True
    
    # 是否啟用 pgvector 擴展
    use_pgvector: bool = True
    
    # pgvector 向量維度 (對應 ReID 模型輸出)
    vector_dimension: int = 512
    
    def get_connection_string(self) -> str:
        """取得 PostgreSQL 連線字串"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def get_dsn(self) -> dict:
        """取得 psycopg2 連線參數"""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "connect_timeout": self.connect_timeout,
        }


@dataclass
class QueueConfig:
    """隊列配置"""
    # MemoryQueue 最大容量 (防止記憶體溢出)
    memory_queue_maxsize: int = 1000
    
    # InferenceQueue 最大容量
    inference_queue_maxsize: int = 100
    
    # 批次寫入大小 (累積多少筆後一次寫入)
    batch_size: int = 1
    
    # 批次寫入超時 (即使未滿 batch_size 也強制寫入)
    batch_timeout_sec: float = 0.5


@dataclass
class RetentionConfig:
    """資料保留策略"""
    # 詳細軌跡保留天數
    telemetry_retention_days: int = 30
    
    # 事件摘要保留天數
    event_summary_retention_days: int = 365
    
    # 是否自動清理過期資料
    auto_cleanup: bool = True
    
    # 清理檢查間隔 (小時)
    cleanup_interval_hours: int = 24


@dataclass
class MemoryConfig:
    """記憶層總配置"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    queue: QueueConfig = field(default_factory=QueueConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    
    # 除錯模式
    debug: bool = True
    
    # 記憶層服務埠號 (用於未來的 API 服務)
    api_port: int = 8765


# 全域配置實例
memory_config = MemoryConfig()
