"""
Pre-Sprint: 数据持久化层
SQLite存储 worlds/books/users，与 event_store 一致的 aiosqlite 模式
"""
import aiosqlite
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class Database:
    """异步SQLite数据库管理器"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = asyncio.Lock()

    async def initialize(self):
        """初始化数据库表"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript("""
                    CREATE TABLE IF NOT EXISTS worlds (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        template TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        user_id TEXT,
                        created_at TEXT NOT NULL,
                        status TEXT DEFAULT 'created',
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS books (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        genre TEXT DEFAULT '',
                        target_audience TEXT DEFAULT '',
                        user_id TEXT,
                        world_id TEXT,
                        created_at TEXT NOT NULL,
                        status TEXT DEFAULT 'draft',
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_login TEXT
                    );
                """)
                await db.commit()

    # ── World CRUD ──────────────────────────────────────────

    async def save_world(self, world: dict) -> str:
        """保存或更新世界"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO worlds (id, name, template, description, user_id, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name, description=excluded.description,
                        status=excluded.status, updated_at=CURRENT_TIMESTAMP
                """, (
                    world["id"], world["name"], world["template"],
                    world.get("description", ""), world.get("user_id"),
                    world.get("created_at", datetime.now().isoformat()),
                    world.get("status", "created"),
                ))
                await db.commit()
        return world["id"]

    async def get_world(self, world_id: str) -> Optional[dict]:
        """获取单个世界"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM worlds WHERE id=?", (world_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_worlds(self, user_id: Optional[str] = None) -> List[dict]:
        """获取世界列表，可筛选用户"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if user_id:
                cursor = await db.execute("SELECT * FROM worlds WHERE user_id=? ORDER BY created_at DESC", (user_id,))
            else:
                cursor = await db.execute("SELECT * FROM worlds ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def update_world_status(self, world_id: str, status: str):
        """更新世界状态"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE worlds SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status, world_id)
                )
                await db.commit()

    async def delete_world(self, world_id: str):
        """删除世界"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM worlds WHERE id=?", (world_id,))
                await db.commit()

    # ── Book CRUD ───────────────────────────────────────────

    async def save_book(self, book: dict) -> str:
        """保存或更新小说"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO books (id, title, description, genre, target_audience, user_id, world_id, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title, description=excluded.description,
                        genre=excluded.genre, target_audience=excluded.target_audience,
                        status=excluded.status, updated_at=CURRENT_TIMESTAMP
                """, (
                    book["id"], book["title"], book.get("description", ""),
                    book.get("genre", ""), book.get("target_audience", ""),
                    book.get("user_id"), book.get("world_id"),
                    book.get("created_at", datetime.now().isoformat()),
                    book.get("status", "draft"),
                ))
                await db.commit()
        return book["id"]

    async def get_book(self, book_id: str) -> Optional[dict]:
        """获取单本小说"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM books WHERE id=?", (book_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_books(self, user_id: Optional[str] = None) -> List[dict]:
        """获取小说列表"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if user_id:
                cursor = await db.execute("SELECT * FROM books WHERE user_id=? ORDER BY created_at DESC", (user_id,))
            else:
                cursor = await db.execute("SELECT * FROM books ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_book(self, book_id: str):
        """删除小说"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM books WHERE id=?", (book_id,))
                await db.commit()

    # ── User CRUD ───────────────────────────────────────────

    async def save_user(self, user: dict) -> str:
        """创建用户"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO users (id, username, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user["id"], user["username"], user["email"],
                    user["password_hash"], user.get("created_at", datetime.now().isoformat()),
                ))
                await db.commit()
        return user["id"]

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """通过ID获取用户"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """通过用户名获取用户"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE username=?", (username,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """通过邮箱获取用户"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE email=?", (email,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_user_login(self, user_id: str):
        """更新用户最后登录时间"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET last_login=? WHERE id=?",
                    (datetime.now().isoformat(), user_id)
                )
                await db.commit()
