"""
db/classes.py — Class CRUD operations.
"""
import aiosqlite
from datetime import datetime
from typing import List, Optional, Dict, Any
from db.connection import get_db


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
