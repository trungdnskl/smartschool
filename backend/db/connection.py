"""
db/connection.py — Database connection, initialization, and migrations.
"""
import aiosqlite
import os
from datetime import datetime
from typing import Optional
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
        import logging as _log
        _log.getLogger(__name__).warning(
            "[DB] Default admin user created (username='admin'). "
            "IMPORTANT: Change password immediately after first login!"
        )


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
