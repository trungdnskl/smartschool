"""
db/sessions.py — Session lifecycle + summary operations.
"""
import aiosqlite
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from db.connection import get_db


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


async def get_sessions_count() -> int:
    """Get total number of sessions for pagination."""
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM sessions") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


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
