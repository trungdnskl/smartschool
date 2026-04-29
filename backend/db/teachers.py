"""
db/teachers.py — Teacher + Subject CRUD operations.
"""
import aiosqlite
from datetime import datetime
from typing import List, Optional, Dict, Any
from db.connection import get_db


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
