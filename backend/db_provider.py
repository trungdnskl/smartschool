"""
Classroom Engagement System - Database Abstraction Layer
Supports both SQLite (development) and PostgreSQL (production).
"""

import os
import logging
import contextlib
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncIterator

logger = logging.getLogger(__name__)


class DatabaseManager(ABC):
    """Abstract database interface."""

    @abstractmethod
    async def connect(self): ...
    @abstractmethod
    async def close(self): ...
    @abstractmethod
    async def execute(self, query: str, params: tuple = ()) -> Any: ...
    @abstractmethod
    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]: ...
    @abstractmethod
    async def executemany(self, query: str, params_list: list) -> None: ...
    @abstractmethod
    async def init_schema(self) -> None: ...
    @abstractmethod
    def connection(self): ...

    async def stream(self, query: str, params: tuple = ()) -> AsyncIterator[Dict[str, Any]]:
        rows = await self.fetchall(query, params)
        for row in rows:
            yield row

    @property
    @abstractmethod
    def provider_name(self) -> str: ...


class SQLiteProvider(DatabaseManager):
    """SQLite provider using aiosqlite with WAL mode."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._connected = False

    async def connect(self):
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._connected = True
        logger.info(f"[DB/SQLite] Ready — {self._db_path}")

    async def close(self):
        self._connected = False

    @contextlib.asynccontextmanager
    async def _get_conn(self):
        import aiosqlite
        db = await aiosqlite.connect(self._db_path)
        try:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=10000")
            await db.execute("PRAGMA foreign_keys=ON")
            db.row_factory = aiosqlite.Row
            yield db
        finally:
            await db.close()

    def connection(self):
        return self._get_conn()

    async def execute(self, query: str, params: tuple = ()) -> Any:
        async with self._get_conn() as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        async with self._get_conn() as db:
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        async with self._get_conn() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def executemany(self, query: str, params_list: list) -> None:
        async with self._get_conn() as db:
            await db.executemany(query, params_list)
            await db.commit()

    async def init_schema(self) -> None:
        from database import init_db
        await init_db()

    @property
    def provider_name(self) -> str:
        return "sqlite"


class PostgreSQLProvider(DatabaseManager):
    """PostgreSQL provider using asyncpg with connection pooling."""

    def __init__(self, host="localhost", port=5432, database="smartschool",
                 user="postgres", password="", pool_size=10):
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._pool_size = pool_size
        self._pool = None

    async def connect(self):
        import asyncpg
        self._pool = await asyncpg.create_pool(
            host=self._host, port=self._port,
            database=self._database, user=self._user,
            password=self._password,
            min_size=max(2, self._pool_size // 2),
            max_size=self._pool_size,
        )
        logger.info(f"[DB/PostgreSQL] Pool — {self._user}@{self._host}:{self._port}/{self._database}")

    async def close(self):
        if self._pool:
            await self._pool.close()

    def connection(self):
        return self._pool.acquire()

    async def execute(self, query: str, params: tuple = ()) -> Any:
        pg_q = _convert_placeholders(query)
        async with self._pool.acquire() as conn:
            return await conn.execute(pg_q, *params)

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        pg_q = _convert_placeholders(query)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(pg_q, *params)
            return dict(row) if row else None

    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        pg_q = _convert_placeholders(query)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(pg_q, *params)
            return [dict(r) for r in rows]

    async def executemany(self, query: str, params_list: list) -> None:
        pg_q = _convert_placeholders(query)
        async with self._pool.acquire() as conn:
            await conn.executemany(pg_q, params_list)

    async def stream(self, query: str, params: tuple = ()) -> AsyncIterator[Dict[str, Any]]:
        pg_q = _convert_placeholders(query)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                async for record in conn.cursor(pg_q, *params):
                    yield dict(record)

    async def init_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_PG_SCHEMA)
        logger.info("[DB/PostgreSQL] Schema initialized ✓")

    @property
    def provider_name(self) -> str:
        return "postgresql"


_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS teachers (
    id SERIAL PRIMARY KEY, teacher_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    email TEXT DEFAULT '', phone TEXT DEFAULT '', subject_specialty TEXT DEFAULT '',
    avatar_path TEXT DEFAULT '', is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS subjects (
    id SERIAL PRIMARY KEY, subject_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    description TEXT DEFAULT '', grade_level TEXT DEFAULT '', is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS teacher_subjects (
    id SERIAL PRIMARY KEY,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE(teacher_id, subject_id));

CREATE TABLE IF NOT EXISTS classes (
    id SERIAL PRIMARY KEY, class_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    grade TEXT DEFAULT '', academic_year TEXT DEFAULT '', room TEXT DEFAULT '',
    homeroom_teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
    student_count INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY, student_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    class_name TEXT DEFAULT '', class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    has_consent INTEGER DEFAULT 0, face_embedding_path TEXT DEFAULT '',
    parent_phone TEXT DEFAULT '', notes TEXT DEFAULT '',
    enrolled_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS parent_consents (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    parent_name TEXT NOT NULL, parent_phone TEXT DEFAULT '',
    consent_type TEXT DEFAULT 'face_recognition', is_granted INTEGER DEFAULT 1,
    granted_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP,
    document_path TEXT DEFAULT '', notes TEXT DEFAULT '');

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY, session_name TEXT DEFAULT '', class_name TEXT DEFAULT '',
    subject TEXT DEFAULT '', teacher_name TEXT DEFAULT '',
    class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
    subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    start_time TIMESTAMP NOT NULL, end_time TIMESTAMP,
    is_active INTEGER DEFAULT 1, total_students INTEGER DEFAULT 0,
    present_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    student_id TEXT NOT NULL, student_name TEXT DEFAULT '',
    status TEXT DEFAULT 'absent', arrival_time TEXT, leave_time TEXT,
    UNIQUE(session_id, student_id));

CREATE TABLE IF NOT EXISTS engagement_logs (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    timestamp TIMESTAMP NOT NULL, total_faces INTEGER DEFAULT 0,
    avg_engagement REAL DEFAULT 0.0, avg_emotion_score REAL DEFAULT 0.0,
    avg_attention_score REAL DEFAULT 0.0, emotion_distribution TEXT DEFAULT '{}',
    learning_state_distribution TEXT DEFAULT '{}', attention_distribution TEXT DEFAULT '{}');

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY, session_id INTEGER REFERENCES sessions(id),
    timestamp TIMESTAMP NOT NULL, alert_type TEXT NOT NULL,
    message TEXT NOT NULL, severity TEXT DEFAULT 'info',
    is_read INTEGER DEFAULT 0, evidence_path TEXT DEFAULT '');

CREATE TABLE IF NOT EXISTS session_summaries (
    id SERIAL PRIMARY KEY, session_id INTEGER UNIQUE NOT NULL REFERENCES sessions(id),
    duration_minutes REAL DEFAULT 0.0, avg_engagement REAL DEFAULT 0.0,
    peak_engagement REAL DEFAULT 0.0, lowest_engagement REAL DEFAULT 0.0,
    peak_time TEXT, low_time TEXT, total_students INTEGER DEFAULT 0,
    present_count INTEGER DEFAULT 0, late_count INTEGER DEFAULT 0,
    absent_count INTEGER DEFAULT 0, emotion_distribution TEXT DEFAULT '{}',
    engagement_timeline TEXT DEFAULT '[]', alerts_count INTEGER DEFAULT 0,
    recommendations TEXT DEFAULT '[]');

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL, role TEXT DEFAULT 'teacher',
    teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW());

CREATE INDEX IF NOT EXISTS idx_engagement_session_time ON engagement_logs(session_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance(session_id);
CREATE INDEX IF NOT EXISTS idx_alerts_session ON alerts(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time DESC);
"""


def _convert_placeholders(query: str) -> str:
    """Convert '?' placeholders to PostgreSQL '$1', '$2', etc."""
    result, counter, in_str, qc = [], 0, False, None
    for ch in query:
        if in_str:
            result.append(ch)
            if ch == qc:
                in_str = False
        elif ch in ("'", '"'):
            in_str, qc = True, ch
            result.append(ch)
        elif ch == '?':
            counter += 1
            result.append(f"${counter}")
        else:
            result.append(ch)
    return "".join(result)


# ── Singleton factory ─────────────────────────────────

_db_manager: Optional[DatabaseManager] = None


async def init_database(config) -> DatabaseManager:
    """Initialize DB provider from AppConfig. Returns DatabaseManager."""
    global _db_manager
    db_cfg = config.database
    provider = getattr(db_cfg, "provider", "sqlite")

    if provider == "postgresql":
        _db_manager = PostgreSQLProvider(
            host=getattr(db_cfg, "host", "localhost"),
            port=getattr(db_cfg, "port", 5432),
            database=getattr(db_cfg, "database_name", "smartschool"),
            user=getattr(db_cfg, "user", "postgres"),
            password=getattr(db_cfg, "password", ""),
            pool_size=getattr(db_cfg, "pool_size", 10),
        )
        await _db_manager.connect()
        await _db_manager.init_schema()
    else:
        _db_manager = SQLiteProvider(db_path=db_cfg.path)
        await _db_manager.connect()
        await _db_manager.init_schema()

    logger.info(f"[DB] Provider: {_db_manager.provider_name}")
    return _db_manager


def get_db_manager() -> DatabaseManager:
    """Get the active database manager singleton."""
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_manager
