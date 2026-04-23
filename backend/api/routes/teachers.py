"""
api/routes/teachers.py — Teachers, Classes, Subjects endpoints.

Tách từ main.py (~lines 881-1056).
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from api.deps import require_teacher, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Teachers & Classes"])


# ── Teachers ──────────────────────────────────────────

@router.get("/api/teachers", summary="Danh sách giáo viên")
async def list_teachers():
    from database import get_teachers
    teachers = await get_teachers()
    return {"teachers": teachers, "total": len(teachers)}


@router.post("/api/teachers", summary="Thêm giáo viên")
async def create_teacher_route(
    teacher_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    subject_specialty: str = Form(""),
    _: dict = Depends(require_admin),
):
    from database import create_teacher
    pk = await create_teacher({
        "teacher_id": teacher_id,
        "name": name,
        "email": email,
        "phone": phone,
        "subject_specialty": subject_specialty,
    })
    return {"status": "ok", "id": pk, "message": f"Đã thêm GV {name}"}


@router.put("/api/teachers/{teacher_pk}", summary="Sửa thông tin giáo viên")
async def update_teacher_route(
    teacher_pk: int,
    name: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    subject_specialty: str = Form(None),
    _: dict = Depends(require_admin),
):
    from database import update_teacher
    data = {}
    if name is not None:               data["name"] = name
    if email is not None:              data["email"] = email
    if phone is not None:              data["phone"] = phone
    if subject_specialty is not None:  data["subject_specialty"] = subject_specialty
    if not data:
        raise HTTPException(400, "Không có gì để cập nhật")
    await update_teacher(teacher_pk, data)
    return {"status": "ok", "message": "Đã cập nhật"}


@router.delete("/api/teachers/{teacher_pk}", summary="Xóa giáo viên")
async def delete_teacher_route(
    teacher_pk: int,
    _: dict = Depends(require_admin),
):
    from database import delete_teacher
    await delete_teacher(teacher_pk)
    return {"status": "ok", "message": "Đã xóa giáo viên"}


# ── Subjects ──────────────────────────────────────────

@router.get("/api/subjects", summary="Danh sách môn học")
async def list_subjects():
    from database import get_subjects
    subjects = await get_subjects()
    return {"subjects": subjects, "total": len(subjects)}


@router.post("/api/subjects", summary="Thêm môn học")
async def create_subject_route(
    subject_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    grade_level: str = Form(""),
    _: dict = Depends(require_teacher),
):
    from database import create_subject
    pk = await create_subject({
        "subject_id": subject_id,
        "name": name,
        "description": description,
        "grade_level": grade_level,
    })
    return {"status": "ok", "id": pk, "message": f"Đã thêm môn {name}"}


@router.delete("/api/subjects/{subject_pk}", summary="Xóa môn học")
async def delete_subject_route(
    subject_pk: int,
    _: dict = Depends(require_teacher),
):
    from database import delete_subject
    await delete_subject(subject_pk)
    return {"status": "ok", "message": "Đã xóa môn học"}


# ── Classes ───────────────────────────────────────────

@router.get("/api/classes", summary="Danh sách lớp học")
async def list_classes():
    from database import get_classes
    classes = await get_classes()
    return {"classes": classes, "total": len(classes)}


@router.post("/api/classes", summary="Thêm lớp học")
async def create_class_route(
    class_id: str = Form(...),
    name: str = Form(...),
    grade: str = Form(""),
    academic_year: str = Form(""),
    room: str = Form(""),
    homeroom_teacher_id: Optional[int] = Form(None),
    _: dict = Depends(require_teacher),
):
    from database import create_class
    pk = await create_class({
        "class_id": class_id,
        "name": name,
        "grade": grade,
        "academic_year": academic_year or str(datetime.now().year),
        "room": room,
        "homeroom_teacher_id": homeroom_teacher_id,
    })
    return {"status": "ok", "id": pk, "message": f"Đã thêm lớp {name}"}


@router.put("/api/classes/{class_pk}", summary="Sửa thông tin lớp")
async def update_class_route(
    class_pk: int,
    name: str = Form(None),
    grade: str = Form(None),
    room: str = Form(None),
    homeroom_teacher_id: Optional[int] = Form(None),
    _: dict = Depends(require_teacher),
):
    from database import update_class
    data = {}
    if name is not None:               data["name"] = name
    if grade is not None:              data["grade"] = grade
    if room is not None:               data["room"] = room
    if homeroom_teacher_id is not None: data["homeroom_teacher_id"] = homeroom_teacher_id
    if not data:
        raise HTTPException(400, "Không có gì để cập nhật")
    await update_class(class_pk, data)
    return {"status": "ok", "message": "Đã cập nhật lớp"}


@router.delete("/api/classes/{class_pk}", summary="Xóa lớp học")
async def delete_class_route(
    class_pk: int,
    _: dict = Depends(require_teacher),
):
    from database import delete_class
    await delete_class(class_pk)
    return {"status": "ok", "message": "Đã xóa lớp"}


@router.get("/api/classes/{class_pk}/students", summary="Học sinh trong lớp")
async def get_class_students_route(class_pk: int):
    from database import get_class_students
    students = await get_class_students(class_pk)
    return {"students": students, "total": len(students)}
