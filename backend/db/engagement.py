"""
db/engagement.py — Engagement logs, attendance, and alert operations.
"""
import aiosqlite
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from db.connection import get_db


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
    query = "SELECT * FROM alerts WHERE session_id = ?"
    params = [session_id]
    if unread_only:
        query += " AND is_read = 0"
    query += " ORDER BY timestamp DESC LIMIT 50"

    async with get_db() as db:
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
