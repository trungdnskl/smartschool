"""
db/maintenance.py — Recovery, cleanup, and dashboard stats.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from db.connection import get_db

_logger = logging.getLogger(__name__)


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


async def cleanup_expired_data(retention_days: int = 90) -> Dict[str, int]:
    """
    Delete data older than retention_days.
    Called on startup and then every 24h by a background task.
    Returns count of deleted rows per table.
    """
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
