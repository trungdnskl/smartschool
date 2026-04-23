"""
Classroom Engagement System - Database Module
Quản lý cơ sở dữ liệu SQLite cho lớp học
Lược đồ quan hệ 3NF: Teachers, Classes, Students, Sessions
"""

import aiosqlite
import os
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from config import get_config

_db_path: Optional[str] = None


def get_db_path() -> str:
    """Get database path from config."""
    global _db_path
    if _db_path is None:
        config = get_config()
        _db_path = config.database.path
    return _db_path


def get_db():
    """Get a database connection with WAL mode and busy timeout.
    
    Usage: async with get_db() as db: ...
    
    WAL mode allows concurrent reads during writes, fixing
    'database is locked' errors in high-throughput scenarios.
    """
    import contextlib

    @contextlib.asynccontextmanager
    async def _connect():
        db = await aiosqlite.connect(get_db_path())
        try:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=10000")
            await db.execute("PRAGMA foreign_keys=ON")
            db.row_factory = aiosqlite.Row
            yield db
        finally:
            await db.close()

    return _connect()


async def init_db():
    """Initialize database and create tables."""
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        # WAL mode: allows concurrent reads during writes (fixes "database is locked")
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=10000")  # 10s retry on lock
        await db.execute("PRAGMA foreign_keys = ON")

        # ===== TEACHERS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                subject_specialty TEXT DEFAULT '',
                avatar_path TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # ===== SUBJECTS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                grade_level TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # ===== TEACHER_SUBJECTS (N:N) =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS teacher_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                UNIQUE(teacher_id, subject_id)
            )
        """)

        # ===== CLASSES =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                grade TEXT DEFAULT '',
                academic_year TEXT DEFAULT '',
                room TEXT DEFAULT '',
                homeroom_teacher_id INTEGER,
                student_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (homeroom_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
            )
        """)

        # ===== STUDENTS (with FK to classes) =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                class_name TEXT DEFAULT '',
                class_id INTEGER,
                has_consent INTEGER DEFAULT 0,
                face_embedding_path TEXT DEFAULT '',
                parent_phone TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                enrolled_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
            )
        """)

        # ===== PARENT CONSENTS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS parent_consents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                parent_name TEXT NOT NULL,
                parent_phone TEXT DEFAULT '',
                consent_type TEXT NOT NULL DEFAULT 'face_recognition',
                is_granted INTEGER DEFAULT 1,
                granted_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                expires_at TEXT,
                document_path TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        """)

        # ===== SESSIONS (with FK to classes, teachers, subjects) =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT DEFAULT '',
                class_name TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                teacher_name TEXT DEFAULT '',
                class_id INTEGER,
                teacher_id INTEGER,
                subject_id INTEGER,
                start_time TEXT NOT NULL,
                end_time TEXT,
                is_active INTEGER DEFAULT 1,
                total_students INTEGER DEFAULT 0,
                present_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL
            )
        """)

        # ===== ATTENDANCE =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                student_name TEXT DEFAULT '',
                status TEXT DEFAULT 'absent',
                arrival_time TEXT,
                leave_time TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                UNIQUE(session_id, student_id)
            )
        """)

        # ===== ENGAGEMENT LOGS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS engagement_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                total_faces INTEGER DEFAULT 0,
                avg_engagement REAL DEFAULT 0.0,
                avg_emotion_score REAL DEFAULT 0.0,
                avg_attention_score REAL DEFAULT 0.0,
                emotion_distribution TEXT DEFAULT '{}',
                learning_state_distribution TEXT DEFAULT '{}',
                attention_distribution TEXT DEFAULT '{}',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # ===== ALERTS =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                is_read INTEGER DEFAULT 0,
                evidence_path TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # Migration: add evidence_path if table already exists without it
        try:
            await db.execute("ALTER TABLE alerts ADD COLUMN evidence_path TEXT DEFAULT ''")
        except Exception:
            pass  # Column already exists

        # ===== SESSION SUMMARIES =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER UNIQUE NOT NULL,
                duration_minutes REAL DEFAULT 0.0,
                avg_engagement REAL DEFAULT 0.0,
                peak_engagement REAL DEFAULT 0.0,
                lowest_engagement REAL DEFAULT 0.0,
                peak_time TEXT,
                low_time TEXT,
                total_students INTEGER DEFAULT 0,
                present_count INTEGER DEFAULT 0,
                late_count INTEGER DEFAULT 0,
                absent_count INTEGER DEFAULT 0,
                emotion_distribution TEXT DEFAULT '{}',
                engagement_timeline TEXT DEFAULT '[]',
                alerts_count INTEGER DEFAULT 0,
                recommendations TEXT DEFAULT '[]',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # ===== INDEXES =====
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_engagement_session
            ON engagement_logs(session_id, timestamp)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_session
            ON attendance(session_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_session
            ON alerts(session_id, timestamp)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_students_class
            ON students(class_id)
        """)

        # ===== USERS (JWT auth) =====
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'teacher',
                teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
        """)

        # ===== MIGRATION =====
        await _migrate_add_columns(db)

        # ===== DEFAULT ADMIN USER =====
        await _ensure_default_admin(db)

        await db.commit()
    print("[DB] Database initialized at " + db_path)



async def _ensure_default_admin(db) -> None:
    """Create default admin user if no users exist yet."""
    async with db.execute("SELECT COUNT(*) FROM users") as cur:
        count = (await cur.fetchone())[0]
    if count == 0:
        from core.security import hash_password, DEFAULT_ADMIN_PASSWORD
        hashed = hash_password(DEFAULT_ADMIN_PASSWORD)
        await db.execute(
            "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
            ("admin", hashed, "admin"),
        )
        print("[DB] Default admin user created: admin / changeme123")
        print("[DB] IMPORTANT: Change password after first login!")



async def _migrate_add_columns(db):
    """Add new columns to existing tables (backward compatible)."""
    # Check and add class_id to students
    try:
        await db.execute("SELECT class_id FROM students LIMIT 1")
    except Exception:
        try:
            await db.execute("ALTER TABLE students ADD COLUMN class_id INTEGER REFERENCES classes(id)")
            print("[DB] Migration: Added class_id to students")
        except Exception:
            pass

    # Check and add parent_phone, notes to students
    for col in ["parent_phone", "notes"]:
        try:
            await db.execute(f"SELECT {col} FROM students LIMIT 1")
        except Exception:
            try:
                await db.execute(f"ALTER TABLE students ADD COLUMN {col} TEXT DEFAULT ''")
                print(f"[DB] Migration: Added {col} to students")
            except Exception:
                pass

    # Check and add class_id, teacher_id, subject_id to sessions
    for col in ["class_id", "teacher_id", "subject_id"]:
        try:
            await db.execute(f"SELECT {col} FROM sessions LIMIT 1")
        except Exception:
            try:
                await db.execute(f"ALTER TABLE sessions ADD COLUMN {col} INTEGER")
                print(f"[DB] Migration: Added {col} to sessions")
            except Exception:
                pass


# ==============================================================
# TEACHER OPERATIONS
# ==============================================================

async def create_teacher(data: Dict[str, Any]) -> int:
    """Create a new teacher."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO teachers (teacher_id, name, email, phone, subject_specialty)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(teacher_id) DO UPDATE SET
                name = excluded.name,
                email = excluded.email,
                phone = excluded.phone,
                subject_specialty = excluded.subject_specialty,
                updated_at = datetime('now', 'localtime')
        """, (
            data["teacher_id"],
            data["name"],
            data.get("email", ""),
            data.get("phone", ""),
            data.get("subject_specialty", ""),
        ))
        await db.commit()
        return cursor.lastrowid


async def get_teachers(active_only: bool = True) -> List[Dict[str, Any]]:
    """Get all teachers."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM teachers"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_teacher_by_id(teacher_id: int) -> Optional[Dict[str, Any]]:
    """Get teacher by primary key ID."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM teachers WHERE id = ?", (teacher_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_teacher(teacher_pk: int, data: Dict[str, Any]):
    """Update teacher info."""
    async with get_db() as db:
        fields = []
        values = []
        for key in ["name", "email", "phone", "subject_specialty", "is_active"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            fields.append("updated_at = datetime('now', 'localtime')")
            values.append(teacher_pk)
            await db.execute(
                f"UPDATE teachers SET {', '.join(fields)} WHERE id = ?",
                values
            )
            await db.commit()


async def delete_teacher(teacher_pk: int):
    """Delete (deactivate) a teacher."""
    async with get_db() as db:
        await db.execute("UPDATE teachers SET is_active = 0 WHERE id = ?", (teacher_pk,))
        await db.commit()


# ==============================================================
# SUBJECT OPERATIONS
# ==============================================================

async def create_subject(data: Dict[str, Any]) -> int:
    """Create a new subject."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO subjects (subject_id, name, description, grade_level)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(subject_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                grade_level = excluded.grade_level
        """, (
            data["subject_id"],
            data["name"],
            data.get("description", ""),
            data.get("grade_level", ""),
        ))
        await db.commit()
        return cursor.lastrowid


async def get_subjects() -> List[Dict[str, Any]]:
    """Get all subjects."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM subjects WHERE is_active = 1 ORDER BY name") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def delete_subject(subject_pk: int):
    """Delete a subject."""
    async with get_db() as db:
        await db.execute("UPDATE subjects SET is_active = 0 WHERE id = ?", (subject_pk,))
        await db.commit()


# ==============================================================
# CLASS OPERATIONS
# ==============================================================

async def create_class(data: Dict[str, Any]) -> int:
    """Create a new class."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO classes (class_id, name, grade, academic_year, room, homeroom_teacher_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(class_id) DO UPDATE SET
                name = excluded.name,
                grade = excluded.grade,
                academic_year = excluded.academic_year,
                room = excluded.room,
                homeroom_teacher_id = excluded.homeroom_teacher_id,
                updated_at = datetime('now', 'localtime')
        """, (
            data["class_id"],
            data["name"],
            data.get("grade", ""),
            data.get("academic_year", str(datetime.now().year)),
            data.get("room", ""),
            data.get("homeroom_teacher_id"),
        ))
        await db.commit()
        return cursor.lastrowid


async def get_classes(active_only: bool = True) -> List[Dict[str, Any]]:
    """Get all classes with teacher name."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT c.*, t.name as teacher_name
            FROM classes c
            LEFT JOIN teachers t ON c.homeroom_teacher_id = t.id
        """
        if active_only:
            query += " WHERE c.is_active = 1"
        query += " ORDER BY c.grade, c.name"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_class_by_id(class_pk: int) -> Optional[Dict[str, Any]]:
    """Get class by primary key."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT c.*, t.name as teacher_name
            FROM classes c
            LEFT JOIN teachers t ON c.homeroom_teacher_id = t.id
            WHERE c.id = ?
        """, (class_pk,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_class(class_pk: int, data: Dict[str, Any]):
    """Update class info."""
    async with get_db() as db:
        fields = []
        values = []
        for key in ["name", "grade", "academic_year", "room", "homeroom_teacher_id", "is_active"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            fields.append("updated_at = datetime('now', 'localtime')")
            values.append(class_pk)
            await db.execute(
                f"UPDATE classes SET {', '.join(fields)} WHERE id = ?",
                values
            )
            await db.commit()


async def delete_class(class_pk: int):
    """Delete (deactivate) a class."""
    async with get_db() as db:
        await db.execute("UPDATE classes SET is_active = 0 WHERE id = ?", (class_pk,))
        await db.commit()


async def get_class_students(class_pk: int) -> List[Dict[str, Any]]:
    """Get students in a class."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM students WHERE class_id = ? ORDER BY name",
            (class_pk,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_class_student_count(class_pk: int):
    """Recalculate student count for a class."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM students WHERE class_id = ?", (class_pk,)
        ) as cursor:
            count = (await cursor.fetchone())[0]
        await db.execute(
            "UPDATE classes SET student_count = ? WHERE id = ?", (count, class_pk)
        )
        await db.commit()


# ==============================================================
# SESSION OPERATIONS
# ==============================================================

async def create_session(session_data: Dict[str, Any]) -> int:
    """Create a new session. Returns session ID."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO sessions (
                session_name, class_name, subject, teacher_name,
                class_id, teacher_id, subject_id,
                start_time, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            session_data.get("session_name", ""),
            session_data.get("class_name", ""),
            session_data.get("subject", ""),
            session_data.get("teacher_name", ""),
            session_data.get("class_id"),
            session_data.get("teacher_id"),
            session_data.get("subject_id"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        await db.commit()
        return cursor.lastrowid


async def end_session(session_id: int):
    """End an active session."""
    async with get_db() as db:
        await db.execute("""
            UPDATE sessions SET is_active = 0, end_time = ? WHERE id = ?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session_id))
        await db.commit()


async def get_active_session() -> Optional[Dict[str, Any]]:
    """Get the current active session."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_sessions(limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """Get session list with teacher and class names from FK."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT s.*,
                   t.name as fk_teacher_name,
                   c.name as fk_class_name,
                   sub.name as fk_subject_name
            FROM sessions s
            LEFT JOIN teachers t ON s.teacher_id = t.id
            LEFT JOIN classes c ON s.class_id = c.id
            LEFT JOIN subjects sub ON s.subject_id = sub.id
            ORDER BY s.id DESC LIMIT ? OFFSET ?
        """, (limit, offset)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                r = dict(row)
                # Use FK names if available, fallback to text fields
                r["teacher_name"] = r.get("fk_teacher_name") or r.get("teacher_name", "")
                r["class_name"] = r.get("fk_class_name") or r.get("class_name", "")
                r["subject"] = r.get("fk_subject_name") or r.get("subject", "")
                results.append(r)
            return results


async def get_session_by_id(session_id: int) -> Optional[Dict[str, Any]]:
    """Get session by ID."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ==============================================================
# ENGAGEMENT LOG OPERATIONS
# ==============================================================

async def insert_engagement_log(log: Dict[str, Any]):
    """Insert engagement snapshot."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO engagement_logs (
                session_id, timestamp, total_faces,
                avg_engagement, avg_emotion_score, avg_attention_score,
                emotion_distribution, learning_state_distribution, attention_distribution
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log["session_id"],
            log["timestamp"],
            log.get("total_faces", 0),
            log.get("avg_engagement", 0.0),
            log.get("avg_emotion_score", 0.0),
            log.get("avg_attention_score", 0.0),
            json.dumps(log.get("emotion_distribution", {})),
            json.dumps(log.get("learning_state_distribution", {})),
            json.dumps(log.get("attention_distribution", {})),
        ))
        await db.commit()


async def get_engagement_timeline(session_id: int) -> List[Dict[str, Any]]:
    """Get engagement timeline for a session."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM engagement_logs WHERE session_id = ?
            ORDER BY timestamp ASC
        """, (session_id,)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                r = dict(row)
                r["emotion_distribution"] = json.loads(r.get("emotion_distribution", "{}"))
                r["learning_state_distribution"] = json.loads(r.get("learning_state_distribution", "{}"))
                r["attention_distribution"] = json.loads(r.get("attention_distribution", "{}"))
                results.append(r)
            return results


# ==============================================================
# ATTENDANCE OPERATIONS
# ==============================================================

async def upsert_attendance(record: Dict[str, Any]):
    """Insert or update attendance record."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO attendance (session_id, student_id, student_name, status, arrival_time)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id, student_id) DO UPDATE SET
                status = excluded.status,
                arrival_time = COALESCE(attendance.arrival_time, excluded.arrival_time)
        """, (
            record["session_id"],
            record["student_id"],
            record.get("student_name", ""),
            record.get("status", "present"),
            record.get("arrival_time", datetime.now().strftime("%H:%M:%S")),
        ))
        await db.commit()


async def get_attendance(session_id: int) -> List[Dict[str, Any]]:
    """Get attendance for a session."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM attendance WHERE session_id = ? ORDER BY arrival_time",
            (session_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ==============================================================
# ALERT OPERATIONS
# ==============================================================

async def insert_alert(alert: Dict[str, Any]) -> int:
    """Insert a new alert (with optional evidence_path for camera snapshot)."""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO alerts (session_id, timestamp, alert_type, message, severity, evidence_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            alert.get("session_id"),
            alert.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            alert["alert_type"],
            alert["message"],
            alert.get("severity", "info"),
            alert.get("evidence_path", ""),
        ))
        await db.commit()
        return cursor.lastrowid


async def get_alerts(session_id: int, unread_only: bool = False) -> List[Dict[str, Any]]:
    """Get alerts for a session."""
    db_path = get_db_path()
    query = "SELECT * FROM alerts WHERE session_id = ?"
    params = [session_id]
    if unread_only:
        query += " AND is_read = 0"
    query += " ORDER BY timestamp DESC LIMIT 50"

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def mark_alert_read(alert_id: int) -> None:
    """Mark a single alert as read."""
    async with get_db() as db:
        await db.execute(
            "UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,)
        )
        await db.commit()


async def mark_all_alerts_read(session_id: Optional[int] = None) -> int:
    """Mark all alerts as read. Returns count updated."""
    async with get_db() as db:
        if session_id is not None:
            cursor = await db.execute(
                "UPDATE alerts SET is_read = 1 WHERE session_id = ? AND is_read = 0",
                (session_id,)
            )
        else:
            cursor = await db.execute(
                "UPDATE alerts SET is_read = 1 WHERE is_read = 0"
            )
        await db.commit()
        return cursor.rowcount


async def get_student_engagement_history(
    student_id: str,
    session_id: Optional[int] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get attendance + per-session engagement summary for a student."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if session_id is not None:
            query = """
                SELECT a.*, s.session_name, s.subject, s.start_time, s.end_time,
                       ss.avg_engagement, ss.duration_minutes
                FROM attendance a
                JOIN sessions s ON a.session_id = s.id
                LEFT JOIN session_summaries ss ON ss.session_id = s.id
                WHERE a.student_id = ? AND a.session_id = ?
                ORDER BY s.start_time DESC LIMIT ?
            """
            params = (student_id, session_id, limit)
        else:
            query = """
                SELECT a.*, s.session_name, s.subject, s.start_time, s.end_time,
                       ss.avg_engagement, ss.duration_minutes
                FROM attendance a
                JOIN sessions s ON a.session_id = s.id
                LEFT JOIN session_summaries ss ON ss.session_id = s.id
                WHERE a.student_id = ?
                ORDER BY s.start_time DESC LIMIT ?
            """
            params = (student_id, limit)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]




# ==============================================================
# STUDENT OPERATIONS
# ==============================================================

async def enroll_student(student: Dict[str, Any]) -> int:
    """Enroll a new student."""
    async with get_db() as db:
        # Resolve class_id from class_name if needed
        class_id = student.get("class_id")
        class_name = student.get("class_name", "")

        if not class_id and class_name:
            async with db.execute(
                "SELECT id FROM classes WHERE class_id = ? OR name = ?",
                (class_name, class_name)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    class_id = row[0]

        cursor = await db.execute("""
            INSERT INTO students (student_id, name, class_name, class_id, has_consent,
                                  face_embedding_path, parent_phone, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                name = excluded.name,
                class_name = excluded.class_name,
                class_id = COALESCE(excluded.class_id, students.class_id),
                has_consent = CASE WHEN excluded.has_consent > 0 THEN excluded.has_consent ELSE students.has_consent END,
                face_embedding_path = CASE WHEN excluded.face_embedding_path != '' THEN excluded.face_embedding_path ELSE students.face_embedding_path END,
                parent_phone = CASE WHEN excluded.parent_phone != '' THEN excluded.parent_phone ELSE students.parent_phone END,
                updated_at = datetime('now', 'localtime')
        """, (
            student["student_id"],
            student["name"],
            class_name,
            class_id,
            1 if student.get("has_consent", False) else 0,
            student.get("face_embedding_path", ""),
            student.get("parent_phone", ""),
            student.get("notes", ""),
        ))
        await db.commit()

        # Update class student count if class_id
        if class_id:
            await update_class_student_count(class_id)

        return cursor.lastrowid


async def get_students(class_name: str = "", class_id: int = None) -> List[Dict[str, Any]]:
    """Get enrolled students."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if class_id:
            query = """
                SELECT s.*, c.name as fk_class_name
                FROM students s
                LEFT JOIN classes c ON s.class_id = c.id
                WHERE s.class_id = ? ORDER BY s.name
            """
            async with db.execute(query, (class_id,)) as cursor:
                rows = await cursor.fetchall()
        elif class_name:
            query = """
                SELECT s.*, c.name as fk_class_name
                FROM students s
                LEFT JOIN classes c ON s.class_id = c.id
                WHERE s.class_name = ? OR c.class_id = ? OR c.name = ?
                ORDER BY s.name
            """
            async with db.execute(query, (class_name, class_name, class_name)) as cursor:
                rows = await cursor.fetchall()
        else:
            query = """
                SELECT s.*, c.name as fk_class_name
                FROM students s
                LEFT JOIN classes c ON s.class_id = c.id
                ORDER BY s.name
            """
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()

        results = []
        for row in rows:
            r = dict(row)
            r["class_display"] = r.get("fk_class_name") or r.get("class_name", "")
            results.append(r)
        return results


async def delete_student(student_id: str):
    """Delete a student by student_id."""
    async with get_db() as db:
        # Get class_id before deleting (to update count)
        async with db.execute(
            "SELECT class_id FROM students WHERE student_id = ?", (student_id,)
        ) as cursor:
            row = await cursor.fetchone()
            class_id = row[0] if row else None

        await db.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        # BUG-06 fix: GIỮ attendance records cho audit history — không hard delete
        # Dữ liệu điểm danh lịch sử vẫn cần thiết cho báo cáo sau này.

        # DB-02 fix: update class count trong cùng transaction thay vì mở connection mới
        if class_id:
            await db.execute(
                """UPDATE classes
                   SET student_count = (
                       SELECT COUNT(*) FROM students WHERE class_id = ?
                   )
                   WHERE id = ?""",
                (class_id, class_id),
            )

        await db.commit()


async def get_student_by_id(student_id: str) -> Optional[Dict[str, Any]]:
    """Get a single student by student_id."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_student(student_id: str, data: Dict[str, Any]):
    """Update student info."""
    async with get_db() as db:
        fields = []
        values = []
        for key in ["name", "class_id", "class_name", "parent_phone", "notes", "has_consent"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            fields.append("updated_at = datetime('now', 'localtime')")
            values.append(student_id)
            await db.execute(
                f"UPDATE students SET {', '.join(fields)} WHERE student_id = ?",
                values
            )
            await db.commit()


# ==============================================================
# PARENT CONSENT OPERATIONS
# ==============================================================

async def add_parent_consent(data: Dict[str, Any]) -> int:
    """Add parent consent record."""
    async with get_db() as db:
        # Get student internal ID
        async with db.execute(
            "SELECT id FROM students WHERE student_id = ?", (data["student_id"],)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return -1
            student_pk = row[0]

        cursor = await db.execute("""
            INSERT INTO parent_consents (
                student_id, parent_name, parent_phone,
                consent_type, is_granted, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            student_pk,
            data["parent_name"],
            data.get("parent_phone", ""),
            data.get("consent_type", "face_recognition"),
            1 if data.get("is_granted", True) else 0,
            data.get("notes", ""),
        ))

        # Also update has_consent on student
        if data.get("is_granted", True):
            await db.execute(
                "UPDATE students SET has_consent = 1 WHERE id = ?", (student_pk,)
            )

        await db.commit()
        return cursor.lastrowid


async def get_parent_consents(student_id: str) -> List[Dict[str, Any]]:
    """Get consent records for a student."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT pc.* FROM parent_consents pc
            JOIN students s ON pc.student_id = s.id
            WHERE s.student_id = ?
            ORDER BY pc.granted_at DESC
        """, (student_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ==============================================================
# SESSION SUMMARY OPERATIONS
# ==============================================================

async def save_session_summary(summary: Dict[str, Any]):
    """Save session summary."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO session_summaries (
                session_id, duration_minutes, avg_engagement, peak_engagement,
                lowest_engagement, peak_time, low_time, total_students,
                present_count, late_count, absent_count,
                emotion_distribution, engagement_timeline, alerts_count, recommendations
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                duration_minutes = excluded.duration_minutes,
                avg_engagement = excluded.avg_engagement,
                peak_engagement = excluded.peak_engagement,
                lowest_engagement = excluded.lowest_engagement,
                peak_time = excluded.peak_time,
                low_time = excluded.low_time,
                total_students = excluded.total_students,
                present_count = excluded.present_count,
                late_count = excluded.late_count,
                absent_count = excluded.absent_count,
                emotion_distribution = excluded.emotion_distribution,
                engagement_timeline = excluded.engagement_timeline,
                alerts_count = excluded.alerts_count,
                recommendations = excluded.recommendations
        """, (
            summary["session_id"],
            summary.get("duration_minutes", 0),
            summary.get("avg_engagement", 0),
            summary.get("peak_engagement", 0),
            summary.get("lowest_engagement", 0),
            summary.get("peak_time"),
            summary.get("low_time"),
            summary.get("total_students", 0),
            summary.get("present_count", 0),
            summary.get("late_count", 0),
            summary.get("absent_count", 0),
            json.dumps(summary.get("emotion_distribution", {})),
            json.dumps(summary.get("engagement_timeline", [])),
            summary.get("alerts_count", 0),
            json.dumps(summary.get("recommendations", [])),
        ))
        await db.commit()


async def get_session_summary(session_id: int) -> Optional[Dict[str, Any]]:
    """Get session summary."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM session_summaries WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                r = dict(row)
                r["emotion_distribution"] = json.loads(r.get("emotion_distribution", "{}"))
                r["engagement_timeline"] = json.loads(r.get("engagement_timeline", "[]"))
                r["recommendations"] = json.loads(r.get("recommendations", "[]"))
                return r
            return None


# ==============================================================
# SESSION RECOVERY
# ==============================================================

async def recover_stuck_sessions() -> int:
    """Recover sessions stuck as is_active=1 from a previous crash.
    
    Returns the number of sessions recovered.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM sessions WHERE is_active = 1"
        )
        count = (await cursor.fetchone())[0]
        if count > 0:
            await db.execute(
                """UPDATE sessions 
                   SET is_active = 0, 
                       end_time = datetime('now', 'localtime')
                   WHERE is_active = 1"""
            )
            await db.commit()
        return count


# ==============================================================
# STATS
# ==============================================================

async def get_dashboard_stats() -> Dict[str, Any]:
    """Get stats for dashboard."""
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM sessions") as cursor:
            total_sessions = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM students") as cursor:
            total_students = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM teachers WHERE is_active = 1") as cursor:
            total_teachers = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM classes WHERE is_active = 1") as cursor:
            total_classes = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM sessions WHERE is_active = 1") as cursor:
            active_sessions = (await cursor.fetchone())[0]

        today = datetime.now().strftime("%Y-%m-%d")
        async with db.execute(
            "SELECT COUNT(*) FROM sessions WHERE start_time LIKE ?",
            (f"{today}%",)
        ) as cursor:
            today_sessions = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM alerts WHERE is_read = 0") as cursor:
            unread_alerts = (await cursor.fetchone())[0]

    return {
        "total_sessions": total_sessions,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_classes": total_classes,
        "active_sessions": active_sessions,
        "today_sessions": today_sessions,
        "unread_alerts": unread_alerts,
    }


# ==============================================================
# Auth / User Management
# ==============================================================

async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Lookup user by username for login. Returns None if not found."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(
    username: str,
    hashed_password: str,
    role: str = "teacher",
    teacher_id: Optional[int] = None,
) -> int:
    """Create a new user account. Returns new user id."""
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO users (username, hashed_password, role, teacher_id)
               VALUES (?, ?, ?, ?)""",
            (username, hashed_password, role, teacher_id),
        )
        await db.commit()
        return cur.lastrowid


async def update_user_password(user_id: int, new_hashed_password: str) -> None:
    """Update password hash for given user id."""
    async with get_db() as db:
        await db.execute(
            """UPDATE users
               SET hashed_password = ?,
                   updated_at = datetime('now', 'localtime')
               WHERE id = ?""",
            (new_hashed_password, user_id),
        )
        await db.commit()


async def list_users() -> List[Dict[str, Any]]:
    """List all users (admin-only use). Excludes hashed_password."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, username, role, teacher_id, is_active, created_at FROM users ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def deactivate_user(user_id: int) -> None:
    """Soft-delete a user (set is_active = 0)."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET is_active = 0, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (user_id,),
        )
        await db.commit()


# ── Data Retention Cleanup (SRS NFR-03.5 / AC-20) ────

async def cleanup_expired_data(retention_days: int = 90) -> Dict[str, int]:
    """
    Delete data older than retention_days.
    Called on startup and then every 24h by a background task.
    Returns count of deleted rows per table.
    """
    import logging
    _logger = logging.getLogger(__name__)

    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
    deleted = {}

    async with get_db() as db:
        # 1. Get old session IDs
        async with db.execute(
            "SELECT id FROM sessions WHERE start_time < ? AND is_active = 0", (cutoff,)
        ) as cur:
            old_session_ids = [row[0] for row in await cur.fetchall()]

        if not old_session_ids:
            _logger.info(f"[Cleanup] No data older than {retention_days} days to clean up")
            return {"sessions": 0, "engagement_logs": 0, "attendance": 0, "alerts": 0, "session_summaries": 0}

        placeholders = ",".join("?" * len(old_session_ids))

        # 2. Delete child records first (FK safe)
        for table in ["engagement_logs", "attendance", "alerts", "session_summaries"]:
            result = await db.execute(
                f"DELETE FROM {table} WHERE session_id IN ({placeholders})",
                old_session_ids,
            )
            deleted[table] = result.rowcount

        # 3. Delete old sessions
        result = await db.execute(
            f"DELETE FROM sessions WHERE id IN ({placeholders})",
            old_session_ids,
        )
        deleted["sessions"] = result.rowcount

        await db.commit()

    _logger.info(
        f"[Cleanup] Deleted expired data (>{retention_days} days): "
        + ", ".join(f"{k}={v}" for k, v in deleted.items())
    )
    return deleted
