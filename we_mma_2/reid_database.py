"""
reid_database.py - ReID 向量資料庫模組

這個模組負責：
- 使用 SQLite 儲存人物向量
- 計算向量相似度
- 管理已註冊的人物資料
"""

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .config import config
except ImportError:
    from config import config


@dataclass
class RegisteredPerson:
    """已註冊的人物資料"""
    id: int
    name: str
    vector: np.ndarray
    created_at: float
    updated_at: float
    sample_count: int  # 用於平均向量的樣本數


class ReIDDatabase:
    """ReID 向量資料庫"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化資料庫
        
        Args:
            db_path: 資料庫檔案路徑，預設為 we_mma_2/reid_vectors.db
        """
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "reid_vectors.db")
        
        self.db_path = db_path
        self._init_database()
        
        # 快取已註冊的人物（避免頻繁讀取資料庫）
        self._cache: Dict[int, RegisteredPerson] = {}
        self._cache_valid = False
        
        self.debug_log(f"Database initialized: {db_path}")
    
    def debug_log(self, msg: str):
        """除錯日誌"""
        if config.debug:
            print(f"[ReIDDB][{time.time():.3f}] {msg}")
    
    def _init_database(self):
        """初始化資料庫表格"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                vector TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                sample_count INTEGER DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _vector_to_json(self, vector: np.ndarray) -> str:
        """將向量轉換為 JSON 字串"""
        return json.dumps(vector.tolist())
    
    def _json_to_vector(self, json_str: str) -> np.ndarray:
        """將 JSON 字串轉換為向量"""
        return np.array(json.loads(json_str), dtype=np.float32)
    
    def add_person(self, name: str, vector: np.ndarray) -> int:
        """
        新增人物
        
        Args:
            name: 人物名稱
            vector: 特徵向量
            
        Returns:
            新增的人物 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = time.time()
        vector_json = self._vector_to_json(vector)
        
        try:
            cursor.execute('''
                INSERT INTO persons (name, vector, created_at, updated_at, sample_count)
                VALUES (?, ?, ?, ?, 1)
            ''', (name, vector_json, now, now))
            
            person_id = cursor.lastrowid
            conn.commit()
            
            self._cache_valid = False
            self.debug_log(f"Added person: {name} (ID: {person_id})")
            
            return person_id
            
        except sqlite3.IntegrityError:
            # 名稱已存在，更新向量
            self.debug_log(f"Person {name} already exists, updating...")
            conn.close()
            return self.update_person_vector(name, vector)
        finally:
            conn.close()
    
    def update_person_vector(self, name: str, new_vector: np.ndarray, 
                             use_average: bool = True) -> int:
        """
        更新人物向量（可選擇使用平均值）
        
        Args:
            name: 人物名稱
            new_vector: 新的特徵向量
            use_average: 是否使用移動平均
            
        Returns:
            人物 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, vector, sample_count FROM persons WHERE name = ?', (name,))
        row = cursor.fetchone()
        
        if row is None:
            conn.close()
            return self.add_person(name, new_vector)
        
        person_id, old_vector_json, sample_count = row
        
        if use_average:
            old_vector = self._json_to_vector(old_vector_json)
            # 計算移動平均
            new_sample_count = sample_count + 1
            averaged_vector = (old_vector * sample_count + new_vector) / new_sample_count
            # 正規化
            norm = np.linalg.norm(averaged_vector)
            if norm > 0:
                averaged_vector = averaged_vector / norm
            final_vector = averaged_vector
        else:
            final_vector = new_vector
            new_sample_count = 1
        
        now = time.time()
        vector_json = self._vector_to_json(final_vector)
        
        cursor.execute('''
            UPDATE persons 
            SET vector = ?, updated_at = ?, sample_count = ?
            WHERE id = ?
        ''', (vector_json, now, new_sample_count, person_id))
        
        conn.commit()
        conn.close()
        
        self._cache_valid = False
        self.debug_log(f"Updated person: {name} (samples: {new_sample_count})")
        
        return person_id
    
    def get_all_persons(self) -> List[RegisteredPerson]:
        """獲取所有已註冊的人物"""
        if self._cache_valid:
            return list(self._cache.values())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, vector, created_at, updated_at, sample_count FROM persons')
        rows = cursor.fetchall()
        conn.close()
        
        self._cache = {}
        for row in rows:
            person = RegisteredPerson(
                id=row[0],
                name=row[1],
                vector=self._json_to_vector(row[2]),
                created_at=row[3],
                updated_at=row[4],
                sample_count=row[5]
            )
            self._cache[person.id] = person
        
        self._cache_valid = True
        return list(self._cache.values())
    
    def get_person_by_name(self, name: str) -> Optional[RegisteredPerson]:
        """根據名稱獲取人物"""
        persons = self.get_all_persons()
        for person in persons:
            if person.name == name:
                return person
        return None
    
    def delete_person(self, name: str) -> bool:
        """刪除人物"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM persons WHERE name = ?', (name,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        if deleted:
            self._cache_valid = False
            self.debug_log(f"Deleted person: {name}")
        
        return deleted
    
    def delete_all(self) -> int:
        """刪除所有人物"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM persons')
        count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        self._cache_valid = False
        self.debug_log(f"Deleted all persons: {count}")
        
        return count
    
    @staticmethod
    def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        """計算餘弦相似度"""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))
    
    def identify(self, query_vector: np.ndarray, 
                 threshold: float = 0.6) -> Tuple[Optional[str], float]:
        """
        識別人物
        
        Args:
            query_vector: 查詢向量
            threshold: 相似度閾值
            
        Returns:
            (人物名稱, 相似度) 或 (None, 0.0)
        """
        persons = self.get_all_persons()
        
        if not persons:
            return None, 0.0
        
        best_match = None
        best_score = 0.0
        
        for person in persons:
            score = self.cosine_similarity(query_vector, person.vector)
            if score > best_score:
                best_score = score
                best_match = person.name
        
        if best_score >= threshold:
            return best_match, best_score
        
        return None, best_score
    
    def identify_batch(self, query_vectors: List[np.ndarray], 
                       threshold: float = 0.6) -> List[Tuple[Optional[str], float]]:
        """
        批量識別人物
        
        Args:
            query_vectors: 查詢向量列表
            threshold: 相似度閾值
            
        Returns:
            [(人物名稱, 相似度), ...] 列表
        """
        return [self.identify(v, threshold) for v in query_vectors]
    
    def get_person_count(self) -> int:
        """獲取已註冊人數"""
        return len(self.get_all_persons())


# 全域資料庫實例
_db_instance: Optional[ReIDDatabase] = None


def get_reid_database() -> ReIDDatabase:
    """獲取全域資料庫實例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = ReIDDatabase()
    return _db_instance
