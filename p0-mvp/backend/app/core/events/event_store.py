"""
A02 事件日志存储系统
基于SQLite的结构化事件存储
"""

import sqlite3
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

import aiosqlite


class EventType(Enum):
    """事件类型"""
    NPC_ACTION = "npc_action"
    WORLD_STATE = "world_state"
    RELATIONSHIP = "relationship"
    STORY_MOMENT = "story_moment"
    SYSTEM = "system"


@dataclass
class Event:
    """事件数据模型"""
    id: Optional[int] = None
    timestamp: str = ""
    turn: int = 0
    day: int = 1
    time_of_day: str = ""
    
    # 参与者
    actor_id: Optional[str] = None
    actor_name: str = ""
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    
    # 动作
    action: str = ""
    action_type: str = "normal"  # normal, interaction, story_moment
    location: str = ""
    
    # 元数据
    world_mood: str = ""
    status: str = "success"
    elapsed_time: float = 0.0
    score: Optional[float] = None  # 审美评分
    
    # 原始数据
    raw_response: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class EventStore:
    """
    事件存储系统
    支持SQLite存储和JSON Lines导出
    """
    
    def __init__(self, db_path: Path, jsonl_path: Optional[Path] = None):
        self.db_path = db_path
        self.jsonl_path = jsonl_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """初始化数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    day INTEGER DEFAULT 1,
                    time_of_day TEXT DEFAULT '',
                    actor_id TEXT,
                    actor_name TEXT NOT NULL,
                    target_id TEXT,
                    target_name TEXT,
                    action TEXT NOT NULL,
                    action_type TEXT DEFAULT 'normal',
                    location TEXT DEFAULT '',
                    world_mood TEXT DEFAULT '',
                    status TEXT DEFAULT 'success',
                    elapsed_time REAL DEFAULT 0.0,
                    score REAL,
                    raw_response TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            await db.execute("CREATE INDEX IF NOT EXISTS idx_turn ON events(turn)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_actor ON events(actor_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_action_type ON events(action_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp)")
            
            await db.commit()
    
    async def save(self, event: Event) -> int:
        """保存事件"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    INSERT INTO events (
                        timestamp, turn, day, time_of_day,
                        actor_id, actor_name, target_id, target_name,
                        action, action_type, location, world_mood,
                        status, elapsed_time, score, raw_response
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.timestamp,
                    event.turn,
                    event.day,
                    event.time_of_day,
                    event.actor_id,
                    event.actor_name,
                    event.target_id,
                    event.target_name,
                    event.action,
                    event.action_type,
                    event.location,
                    event.world_mood,
                    event.status,
                    event.elapsed_time,
                    event.score,
                    event.raw_response
                ))
                await db.commit()
                event_id = cursor.lastrowid
        
        # 同时写入JSONL
        if self.jsonl_path:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")
        
        return event_id
    
    async def save_batch(self, events: List[Event]):
        """批量保存事件"""
        for event in events:
            await self.save(event)
    
    async def query(
        self,
        turn_range: Optional[tuple] = None,
        actor_id: Optional[str] = None,
        action_type: Optional[str] = None,
        location: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 1000
    ) -> List[Event]:
        """查询事件"""
        conditions = []
        params = []
        
        if turn_range:
            conditions.append("turn >= ? AND turn <= ?")
            params.extend(turn_range)
        
        if actor_id:
            conditions.append("actor_id = ?")
            params.append(actor_id)
        
        if action_type:
            conditions.append("action_type = ?")
            params.append(action_type)
        
        if location:
            conditions.append("location = ?")
            params.append(location)
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM events WHERE {where_clause} ORDER BY turn, timestamp LIMIT ?",
                [*params, limit]
            )
            rows = await cursor.fetchall()
        
        return [Event.from_dict(dict(row)) for row in rows]
    
    async def get_story_moments(self, min_score: float = 0) -> List[Event]:
        """获取故事时刻"""
        return await self.query(action_type="story_moment", limit=100)
    
    async def get_cross_interactions(self) -> List[Event]:
        """获取跨角色互动"""
        events = await self.query(action_type="interaction", limit=500)
        # 去重（按actor_id + target_id组合）
        seen = set()
        unique = []
        for e in events:
            key = tuple(sorted([e.actor_id or "", e.target_id or ""]))
            if key not in seen and e.target_id:
                seen.add(key)
                unique.append(e)
        return unique
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取统计指标"""
        async with aiosqlite.connect(self.db_path) as db:
            # 基本统计
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN status = 'fallback' THEN 1 ELSE 0 END) as fallback,
                    SUM(CASE WHEN action_type = 'interaction' THEN 1 ELSE 0 END) as interactions,
                    SUM(CASE WHEN action_type = 'story_moment' THEN 1 ELSE 0 END) as story_moments,
                    MAX(turn) as max_turn,
                    AVG(elapsed_time) as avg_time,
                    MAX(elapsed_time) as max_time
                FROM events
            """)
            row = await cursor.fetchone()
            
            return {
                "total_events": row[0] or 0,
                "success_events": row[1] or 0,
                "fallback_events": row[2] or 0,
                "interactions": row[3] or 0,
                "story_moments": row[4] or 0,
                "max_turn": row[5] or 0,
                "avg_elapsed_time": row[6] or 0,
                "max_elapsed_time": row[7] or 0
            }
    
    async def export_to_jsonl(self, output_path: Path):
        """导出到JSONL"""
        events = await self.query(limit=100000)
        with open(output_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(event.to_json() + "\n")
    
    async def clear(self):
        """清空所有事件"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM events")
            await db.commit()
        
        if self.jsonl_path and self.jsonl_path.exists():
            self.jsonl_path.unlink()
