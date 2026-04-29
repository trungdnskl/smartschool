"""
db/auth.py — User/auth CRUD operations.
"""
import aiosqlite
from typing import List, Optional, Dict, Any
from db.connection import get_db


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
