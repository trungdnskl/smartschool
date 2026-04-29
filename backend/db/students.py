"""
db/students.py — Student CRUD + parent consent operations.
"""
import aiosqlite
from datetime import datetime
from typing import List, Optional, Dict, Any
from db.connection import get_db


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
            from db.classes import update_class_student_count
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
