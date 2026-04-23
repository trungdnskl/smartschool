"""
api/routes/students.py — Student CRUD + face enrollment endpoints.

Tách từ main.py (~lines 487–878).
"""
import base64
import io
import logging
import os
import pickle
import tempfile
import zipfile
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from api.deps import require_teacher
from state import state, safe_pickle_loads

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/students", tags=["Students"])


# ── Helper ────────────────────────────────────────────

def _detect_largest_face(frame: np.ndarray, detector):
    """Detect và crop khuôn mặt lớn nhất trong frame. Return crop hoặc None."""
    faces = detector.face_detector.detect_faces(frame)
    if not faces:
        return None
    largest = max(
        faces,
        key=lambda f: (f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1]),
    )
    return detector.face_detector.crop_face(frame, largest["bbox"], margin=0.2)


# ── List ──────────────────────────────────────────────

@router.get("", summary="Danh sách học sinh")
async def list_students(
    class_name: str = Query(""),
    class_id: int = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Danh sách học sinh đã đăng ký, kèm thông tin ML (sample count)."""
    from database import get_students

    students = await get_students(class_name=class_name, class_id=class_id)

    if state.detector:
        enrolled_info = {
            s["student_id"]: s
            for s in state.detector.attendance_tracker.get_enrolled_students_info()
        }
        for s in students:
            info = enrolled_info.get(s["student_id"], {})
            s["sample_count"] = info.get("sample_count", 0)
            s["lbph_samples"] = info.get("lbph_samples", 0)        # P2-6
            s["deep_embeddings"] = info.get("deep_embeddings", 0)  # P2-6
            s["has_photo"] = info.get("has_photo", False)

    total = len(students)
    paginated = students[offset: offset + limit]
    return {"students": paginated, "total": total, "limit": limit, "offset": offset}


# ── Enroll via uploaded photo ─────────────────────────

@router.post("/enroll", summary="Đăng ký học sinh (ảnh upload)")
async def enroll_student(
    student_id: str = Form(...),
    name: str = Form(...),
    class_name: str = Form(""),
    photo: Optional[UploadFile] = File(None),
    _: dict = Depends(require_teacher),
):
    """Đăng ký học sinh. Nếu có ảnh thì enrollment khuôn mặt luôn."""
    from database import enroll_student as db_enroll_student

    if photo:
        contents = await photo.read()
        nparr = np.frombuffer(contents, np.uint8)
        face_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if face_img is None:
            raise HTTPException(400, "Ảnh không hợp lệ hoặc bị lỗi")

        if state.detector is None:
            raise HTTPException(500, "AI detector chưa khởi tạo")

        face_crop = _detect_largest_face(face_img, state.detector)
        if face_crop is None:
            raise HTTPException(400, "Không phát hiện khuôn mặt trong ảnh")

        success = state.detector.enroll_student(student_id, name, face_crop, class_name)
        if not success:
            raise HTTPException(400, "Đăng ký khuôn mặt thất bại — thử lại với ảnh rõ hơn")

        samples = len(
            state.detector.attendance_tracker._enrolled_faces
            .get(student_id, {})
            .get("samples", [])
        )
        await db_enroll_student({
            "student_id": student_id,
            "name": name,
            "class_name": class_name,
            "has_consent": True,
            "face_embedding_path": f"data/face_embeddings/{student_id}",
        })
        return {
            "status": "ok",
            "message": f"Đã đăng ký {name} ({samples} mẫu khuôn mặt)",
            "sample_count": samples,
        }

    # Không có ảnh — chỉ lưu thông tin
    await db_enroll_student({"student_id": student_id, "name": name, "class_name": class_name})
    return {"status": "ok", "message": f"Đã đăng ký {name} (chưa có ảnh khuôn mặt)"}


# ── Add extra photo ────────────────────────────────────

@router.post("/{student_id}/add-photo", summary="Thêm ảnh khuôn mặt")
async def add_student_photo(
    student_id: str,
    photo: UploadFile = File(...),
    _: dict = Depends(require_teacher),
):
    """Thêm thêm ảnh mặt để tăng accuracy (multi-sample enrollment)."""
    from database import get_students

    if not state.detector:
        raise HTTPException(500, "AI chưa khởi tạo")

    contents = await photo.read()
    nparr = np.frombuffer(contents, np.uint8)
    face_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if face_img is None:
        raise HTTPException(400, "Ảnh không hợp lệ")

    face_crop = _detect_largest_face(face_img, state.detector)
    if face_crop is None:
        raise HTTPException(400, "Không phát hiện khuôn mặt trong ảnh")

    # Lấy tên học sinh
    info = state.detector.attendance_tracker._enrolled_faces.get(student_id)
    if info:
        name, class_name = info["name"], info.get("class_name", "")
    else:
        students = await get_students()
        found = [s for s in students if s["student_id"] == student_id]
        if not found:
            raise HTTPException(404, f"Không tìm thấy học sinh {student_id}")
        name, class_name = found[0]["name"], found[0].get("class_name", "")

    success = state.detector.enroll_student(student_id, name, face_crop, class_name)
    if not success:
        raise HTTPException(400, "Không thể thêm ảnh — thử lại")

    samples = len(
        state.detector.attendance_tracker._enrolled_faces
        .get(student_id, {})
        .get("samples", [])
    )
    return {
        "status": "ok",
        "message": f"Đã thêm ảnh cho {name} (tổng: {samples} mẫu)",
        "sample_count": samples,
    }


# ── Enroll from camera ─────────────────────────────────

@router.post("/enroll-camera", summary="Đăng ký từ camera")
async def enroll_from_camera(
    student_id: str = Form(...),
    name: str = Form(...),
    class_name: str = Form(""),
    camera_id: str = Form("cam_front"),
    _: dict = Depends(require_teacher),
):
    """Đăng ký khuôn mặt trực tiếp từ camera đang chạy."""
    from database import enroll_student as db_enroll_student

    if not state.camera_manager:
        raise HTTPException(500, "Camera manager chưa khởi tạo")

    cam = state.camera_manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(404, f"Không tìm thấy camera {camera_id}")

    frame = cam.get_latest_frame()
    if frame is None:
        raise HTTPException(400, "Không lấy được hình ảnh. Hãy bật camera trước.")

    if not state.detector:
        raise HTTPException(500, "AI detector chưa khởi tạo")

    face_crop = _detect_largest_face(frame, state.detector)
    if face_crop is None:
        raise HTTPException(400, "Không phát hiện khuôn mặt. Đảm bảo HS đứng trước camera.")

    success = state.detector.enroll_student(student_id, name, face_crop, class_name)
    if not success:
        raise HTTPException(400, "Đăng ký khuôn mặt thất bại")

    samples = len(
        state.detector.attendance_tracker._enrolled_faces
        .get(student_id, {})
        .get("samples", [])
    )
    await db_enroll_student({
        "student_id": student_id,
        "name": name,
        "class_name": class_name,
        "has_consent": True,
        "face_embedding_path": f"data/face_embeddings/{student_id}",
    })

    _, buffer = cv2.imencode(".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
    preview = base64.b64encode(buffer).decode("utf-8")
    return {
        "status": "ok",
        "message": f"Đã đăng ký {name} từ camera ({samples} mẫu)",
        "sample_count": samples,
        "preview": preview,
    }


# ── Delete ─────────────────────────────────────────────

@router.delete("/{student_id}", summary="Xóa học sinh")
async def delete_student(
    student_id: str,
    _: dict = Depends(require_teacher),
):
    """Xóa học sinh khỏi ML tracker + DB (giữ lại lịch sử attendance)."""
    from database import delete_student as db_delete_student

    if state.detector:
        state.detector.attendance_tracker.delete_student(student_id)

    await db_delete_student(student_id)
    return {"status": "ok", "message": f"Đã xóa học sinh {student_id}"}


# ── P2-6: Sync names ──────────────────────────────────

@router.post("/sync", summary="Đồng bộ tên LBPH ↔ ArcFace ↔ DB")
async def sync_student_names(
    _: dict = Depends(require_teacher),
):
    """Trigger đồng bộ tên giữa các engine nhận diện."""
    if not state.detector:
        raise HTTPException(500, "AI detector chưa khởi tạo")

    tracker = state.detector.attendance_tracker
    tracker._sync_student_names()
    return {
        "status": "ok",
        "message": "Đã đồng bộ tên giữa LBPH ↔ ArcFace ↔ disk",
    }


# ── Update ─────────────────────────────────────────────

@router.put("/{student_id}", summary="Cập nhật thông tin học sinh")
async def update_student_info(
    student_id: str,
    name: str = Form(None),
    class_name: str = Form(None),
    _: dict = Depends(require_teacher),
):
    from database import update_student

    data = {}
    if name is not None:       data["name"] = name
    if class_name is not None: data["class_name"] = class_name
    if not data:
        raise HTTPException(400, "Không có thông tin nào để cập nhật")

    await update_student(student_id, data)
    return {"status": "ok", "message": "Đã cập nhật thông tin học sinh"}

# ── Export photos for Colab training ───────────────────

@router.get("/export-photos", summary="Export ảnh khuôn mặt (ZIP)")
async def export_photos():
    """
    Đóng gói toàn bộ ảnh khuôn mặt đã thu thập thành file ZIP
    để upload lên Google Colab / HuggingFace training.
    
    Cấu trúc ZIP:
      face_photos/
        HS001/
          metadata.json
          sample_000.png
          sample_001.png
        HS002/
          ...
    """
    from pathlib import Path
    
    embeddings_dir = Path(__file__).parent.parent.parent / "data" / "face_embeddings"
    if not embeddings_dir.exists():
        raise HTTPException(404, "Chưa có dữ liệu ảnh khuôn mặt")
    
    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    student_count = 0
    photo_count = 0
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for student_dir in sorted(embeddings_dir.iterdir()):
            if not student_dir.is_dir():
                continue
            
            student_id = student_dir.name
            has_photos = False
            
            # Add metadata.json
            meta_file = student_dir / "metadata.json"
            if meta_file.exists():
                zf.write(meta_file, f"face_photos/{student_id}/metadata.json")
            
            # Add all sample images
            for img_file in sorted(student_dir.glob("sample_*.png")):
                zf.write(img_file, f"face_photos/{student_id}/{img_file.name}")
                photo_count += 1
                has_photos = True
            
            # Also check for .jpg samples
            for img_file in sorted(student_dir.glob("sample_*.jpg")):
                zf.write(img_file, f"face_photos/{student_id}/{img_file.name}")
                photo_count += 1
                has_photos = True
            
            if has_photos:
                student_count += 1
    
    if student_count == 0:
        raise HTTPException(404, "Không tìm thấy ảnh khuôn mặt nào")
    
    zip_buffer.seek(0)
    
    logger.info(f"[Export] ZIP created: {student_count} students, {photo_count} photos")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="face_photos_{student_count}students.zip"',
            "X-Student-Count": str(student_count),
            "X-Photo-Count": str(photo_count),
        },
    )


# ── Photo ──────────────────────────────────────────────

@router.get("/{student_id}/photo", summary="Ảnh thumbnail học sinh")
async def get_student_photo(student_id: str):
    if state.detector:
        thumb = state.detector.attendance_tracker.get_thumbnail_path(student_id)
        if thumb:
            return FileResponse(thumb, media_type="image/jpeg")
    raise HTTPException(404, "Chưa có ảnh")


@router.get("/{student_id}/thumbnail", summary="Ảnh thumbnail (alias)")
async def get_student_thumbnail(student_id: str):
    """Alias for /photo — used by frontend."""
    return await get_student_photo(student_id)


# ── Import CSV ─────────────────────────────────────────

@router.post("/import-csv", summary="Import danh sách từ CSV")
async def import_csv(
    file: UploadFile = File(...),
    _: dict = Depends(require_teacher),
):
    """Import học sinh từ CSV: student_id, name, class_name (có header)."""
    from database import enroll_student as db_enroll_student

    contents = await file.read()
    text = contents.decode("utf-8-sig")
    lines = text.strip().split("\n")

    if len(lines) < 2:
        raise HTTPException(400, "File CSV cần ít nhất 2 dòng (header + data)")

    imported, errors = 0, []
    for i, line in enumerate(lines[1:], start=2):
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) < 2:
            errors.append(f"Dòng {i}: thiếu dữ liệu")
            continue
        student_id, name = parts[0], parts[1]
        class_name = parts[2] if len(parts) > 2 else ""
        if not student_id or not name:
            errors.append(f"Dòng {i}: thiếu mã HS hoặc tên")
            continue
        try:
            await db_enroll_student({"student_id": student_id, "name": name, "class_name": class_name})
            imported += 1
        except Exception as e:
            logger.warning(f"[CSV] Dòng {i} lỗi: {e}")
            errors.append(f"Dòng {i}: Lỗi khi lưu dữ liệu học sinh")

    return {
        "status": "ok",
        "imported": imported,
        "errors": errors,
        "message": f"Đã import {imported} học sinh" + (f", {len(errors)} lỗi" if errors else ""),
    }


# ── Import Colab Embeddings ────────────────────────────

@router.post("/import-embeddings", summary="Import embeddings từ Google Colab")
async def import_embeddings(
    file: UploadFile = File(...),
    _: dict = Depends(require_teacher),
):
    """Upload file deep_embeddings.pkl từ Google Colab để kích hoạt ArcFace engine."""
    from deep_face_recognizer import import_colab_embeddings

    if not file.filename.endswith(".pkl"):
        raise HTTPException(400, "File phải có định dạng .pkl (từ Google Colab)")

    contents = await file.read()

    # Safe deserialization — block RCE
    try:
        data = safe_pickle_loads(contents)
        if not isinstance(data, dict):
            raise HTTPException(400, "File .pkl không đúng định dạng")
        students = data.get("students", data)
        if not students:
            raise HTTPException(400, "File không chứa dữ liệu embedding nào")
        student_count = len(students)
        model_name = data.get("model", "unknown")
    except pickle.UnpicklingError as e:
        logger.warning(f"[API] Blocked malicious .pkl: {e}")
        raise HTTPException(400, "File .pkl bị chặn vì lý do bảo mật")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "File .pkl không hợp lệ hoặc bị hỏng")

    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        success, message, total = import_colab_embeddings(tmp_path)
        if not success:
            raise HTTPException(500, message)

        # Reload whatever deep recognizer is wired up
        engine_switched = "LBPH (fallback)"
        if state.detector and state.detector.attendance_tracker._deep_recognizer:
            deep = state.detector.attendance_tracker._deep_recognizer
            deep.reload_embeddings()
            if deep.is_available:
                state.detector.attendance_tracker._use_deep = True
                engine_name = deep.get_stats().get("engine", "deepface")
                engine_switched = f"{engine_name} (active)"
                logger.info(f"[API] Switched to {engine_name} after import ✓")

        return {
            "status": "ok",
            "message": message,
            "imported_students": student_count,
            "total_students": total,
            "model": model_name,
            "engine_switched": engine_switched,
            "next_steps": "Khoi dong buoi hoc de bat dau diem danh voi ArcFace",
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/deep-embeddings/info", summary="Thông tin file embeddings")
async def get_embeddings_info():
    from deep_face_recognizer import get_embedding_stats

    stats = get_embedding_stats()
    if not stats.get("file_exists"):
        return {
            "exists": False,
            "message": "Chưa có file deep_embeddings.pkl. Chạy Google Colab notebook để tạo.",
        }
    return {"exists": True, **stats}


@router.get("/ml-stats", summary="Thống kê ML engines")
async def get_ml_stats():
    from deep_face_recognizer import get_embedding_stats

    if not state.detector:
        return {"enrolled": 0, "total_samples": 0, "recognizer_trained": False}

    tracker = state.detector.attendance_tracker
    total_samples = sum(
        len(d.get("samples", [])) for d in tracker._enrolled_faces.values()
    )
    deep_stats = tracker._deep_recognizer.get_stats() if tracker._deep_recognizer else {}
    engine_name = deep_stats.get("engine", "lbph") if tracker._use_deep else "lbph"
    emb_stats = get_embedding_stats()

    return {
        "engine_active": engine_name,
        "deep_engine": {
            "available":          deep_stats.get("model_available", False),
            "enrolled_students":  deep_stats.get("enrolled_students", 0),
            "total_embeddings":   deep_stats.get("total_embeddings", 0),
            "model":              deep_stats.get("model", "not_loaded"),
            "engine":             deep_stats.get("engine", "none"),
            "threshold":          deep_stats.get("threshold", 0.45),
            "db_file_exists":     emb_stats.get("file_exists", False),
            "db_file_size_kb":    emb_stats.get("file_size_kb", 0),
        },
        "lbph": {
            "enrolled":            tracker.get_enrolled_count(),
            "total_samples":       total_samples,
            "recognizer_trained":  tracker._recognizer_trained,
        },
        "face_model": state.detector.face_detector.model_type,
    }


# ── Consents ───────────────────────────────────────────

@router.post("/{student_id}/consent", summary="Thêm đồng ý PHHS")
async def add_consent(
    student_id: str,
    parent_name: str = Form(...),
    parent_phone: str = Form(""),
    consent_type: str = Form("face_recognition"),
    is_granted: bool = Form(True),
    notes: str = Form(""),
    _: dict = Depends(require_teacher),
):
    from database import add_parent_consent

    pk = await add_parent_consent({
        "student_id": student_id,
        "parent_name": parent_name,
        "parent_phone": parent_phone,
        "consent_type": consent_type,
        "is_granted": is_granted,
        "notes": notes,
    })
    if pk == -1:
        raise HTTPException(404, "Không tìm thấy học sinh")
    return {"status": "ok", "id": pk, "message": "Đã ghi nhận đồng ý PHHS"}


@router.get("/{student_id}/consents", summary="Danh sách đồng ý PHHS")
async def get_consents(student_id: str):
    from database import get_parent_consents

    consents = await get_parent_consents(student_id)
    return {"consents": consents, "total": len(consents)}


# ── Student detail ─────────────────────────────────────

@router.get("/{student_id}", summary="Chi tiết học sinh")
async def get_student_detail(student_id: str):
    """Lấy thông tin chi tiết một học sinh theo student_id."""
    from database import get_student_by_id

    student = await get_student_by_id(student_id)
    if not student:
        raise HTTPException(404, f"Không tìm thấy học sinh {student_id}")

    # Bổ sung thông tin ML nếu detector đang chạy
    if state.detector:
        enrolled_info = {
            s["student_id"]: s
            for s in state.detector.attendance_tracker.get_enrolled_students_info()
        }
        info = enrolled_info.get(student_id, {})
        student["sample_count"] = info.get("sample_count", 0)
        student["has_photo"] = info.get("has_photo", False)
    return student


@router.get("/{student_id}/engagement", summary="Lịch sử engagement học sinh")
async def get_student_engagement(
    student_id: str,
    session_id: int = Query(None, description="Lọc theo session cụ thể"),
    limit: int = Query(50, ge=1, le=200),
):
    """Lấy lịch sử điểm danh và engagement của một học sinh."""
    from database import get_student_engagement_history

    history = await get_student_engagement_history(student_id, session_id=session_id, limit=limit)
    return {
        "student_id": student_id,
        "records": history,
        "total": len(history),
    }
