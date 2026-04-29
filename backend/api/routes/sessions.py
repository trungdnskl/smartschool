"""
api/routes/sessions.py — Session management endpoints.

Tách từ main.py (~lines 304-458).
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import require_teacher
from state import state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


# ── Pydantic schemas ──────────────────────────────────

class StartSessionRequest(BaseModel):
    """Request body for POST /api/sessions/start."""
    session_name: Optional[str] = None
    class_name: Optional[str] = None
    subject: Optional[str] = None
    teacher_name: Optional[str] = None
    class_id: Optional[int] = None
    teacher_id: Optional[int] = None
    subject_id: Optional[int] = None


# ── Endpoints ────────────────────────────────────────

@router.post("/start", summary="Bắt đầu buổi học")
async def start_session(
    body: StartSessionRequest,
    current_user: dict = Depends(require_teacher),
):
    """Bắt đầu một buổi học mới — chỉ 1 session tại một thời điểm."""
    from database import create_session

    cfg = state.config

    # Fix B5: Ưu tiên teacher info từ auth context (JWT payload)
    # Fallback về request body cho backward compat khi AUTH_ENABLED=false
    teacher_name = current_user.get("name") or current_user.get("sub") or body.teacher_name
    teacher_id = current_user.get("user_id") or body.teacher_id

    session_data = {
        "session_name": body.session_name or f"Buổi học {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "class_name": body.class_name or (cfg.classroom.name if cfg else ""),
        "subject": body.subject or (cfg.classroom.subject if cfg else ""),
        "teacher_name": teacher_name,
        "class_id": body.class_id,
        "teacher_id": teacher_id if teacher_id else None,
        "subject_id": body.subject_id,
    }

    async with state.session_lock:
        if state.active_session_id is not None:
            raise HTTPException(400, "Đã có buổi học đang diễn ra. Hãy kết thúc trước.")

        try:
            session_id = await create_session(session_data)
            state.active_session_id = session_id

            if state.detector:
                # Fix D1: Run in executor để tránh block event loop
                # (attendance_tracker.start_session() load embeddings từ disk)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, state.detector.start_session, session_id)
            if state.camera_manager:
                state.camera_manager.start_all()
        except Exception as e:
            # Rollback: reset state nếu bất kỳ bước nào fail
            state.active_session_id = None
            logger.error(f"[Session] Failed to start: {e}")
            raise HTTPException(500, f"Lỗi khởi tạo buổi học: {e}")

    # Broadcast ngoài lock (đã có session_id hợp lệ)
    logger.info(f"[Session] #{session_id} started")
    await state.broadcast({
        "type": "session_status",
        "data": {"status": "started", "session_id": session_id, **session_data},
    })
    return {"status": "ok", "session_id": session_id, "message": "Buổi học đã bắt đầu"}


@router.post("/stop", summary="Kết thúc buổi học")
async def stop_session(_: dict = Depends(require_teacher)):
    """Kết thúc buổi học hiện tại — lưu tóm tắt vào DB."""
    from database import (
        end_session, get_session_by_id, get_attendance,
        get_engagement_timeline, get_alerts, save_session_summary,
    )

    async with state.session_lock:
        if state.active_session_id is None:
            raise HTTPException(400, "Không có buổi học nào đang diễn ra.")

        session_id = state.active_session_id

        # Stop cameras + AI + cleanup frame cache (I4: prevent memory leak)
        if state.camera_manager:
            state.camera_manager.stop_all()
        from processing import cleanup_camera_frames
        cleanup_camera_frames()  # Clear all cached frames

        summary: dict = {}
        if state.detector:
            summary = state.detector.stop_session() or {}
        summary["session_id"] = session_id

        # Attendance counts
        attendance = await get_attendance(session_id)
        summary["present_count"] = sum(1 for a in attendance if a.get("status") == "present")
        summary["late_count"]    = sum(1 for a in attendance if a.get("status") == "late")
        summary["absent_count"]  = sum(1 for a in attendance if a.get("status") == "absent")
        summary["total_students"] = len(attendance)

        # Actual duration from DB start_time
        session_info = await get_session_by_id(session_id)
        if session_info and session_info.get("start_time"):
            try:
                start_dt = datetime.strptime(session_info["start_time"], "%Y-%m-%d %H:%M:%S")
                summary["duration_minutes"] = round(
                    (datetime.now() - start_dt).total_seconds() / 60, 1
                )
            except ValueError:
                summary["duration_minutes"] = 0.0
        else:
            summary["duration_minutes"] = 0.0

        # Engagement timeline
        engagement_data = await get_engagement_timeline(session_id)
        if engagement_data:
            summary["engagement_timeline"] = [
                {"timestamp": e["timestamp"], "avg_engagement": e["avg_engagement"]}
                for e in engagement_data
            ]

        # Alerts count
        alerts = await get_alerts(session_id)
        summary["alerts_count"] = len(alerts)

        # Recommendations
        avg_eng = summary.get("avg_engagement", 0)
        if avg_eng < 40:
            recs = ["⚠️ Mức độ tập trung thấp — thay đổi phương pháp giảng dạy"]
        elif avg_eng < 60:
            recs = ["📌 Engagement trung bình — nên tăng tương tác với học sinh"]
        else:
            recs = ["✅ Lớp học tích cực — tiếp tục duy trì phương pháp hiện tại"]
        summary["recommendations"] = recs

        # Persist
        await save_session_summary(summary)
        await end_session(session_id)

        state.active_session_id = None
        state.latest_snapshot = None

    await state.broadcast({
        "type": "session_status",
        "data": {"status": "stopped", "session_id": session_id},
    })

    logger.info(f"[Session] #{session_id} ended ✓ ({summary['duration_minutes']}min)")
    return {"status": "ok", "session_id": session_id, "summary": summary}


@router.get("", summary="Danh sách buổi học")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    from database import get_sessions, get_sessions_count
    sessions = await get_sessions(limit=limit, offset=offset)
    total = await get_sessions_count()
    return {"sessions": sessions, "total": total, "limit": limit, "offset": offset}


@router.get("/active", summary="Buổi học đang hoạt động")
async def get_active_session():
    from database import get_session_by_id
    if state.active_session_id:
        session = await get_session_by_id(state.active_session_id)
        return {"active": True, "session": session}
    return {"active": False, "session": None}


@router.get("/{session_id}", summary="Chi tiết buổi học")
async def get_session(session_id: int):
    from database import get_session_by_id
    session = await get_session_by_id(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy buổi học")
    return session


@router.get("/{session_id}/summary", summary="Tóm tắt buổi học")
async def get_session_summary(session_id: int):
    from database import get_session_summary as _get_summary
    summary = await _get_summary(session_id)
    if not summary:
        raise HTTPException(404, "Chưa có tóm tắt cho buổi học này")
    return summary


@router.get("/{session_id}/engagement", summary="Timeline engagement")
async def get_session_engagement(session_id: int):
    from database import get_engagement_timeline
    timeline = await get_engagement_timeline(session_id)
    return {"session_id": session_id, "timeline": timeline}


@router.get("/{session_id}/attendance", summary="Danh sách điểm danh")
async def get_session_attendance(session_id: int):
    from database import get_attendance
    records = await get_attendance(session_id)
    return {"session_id": session_id, "records": records}


@router.get("/{session_id}/alerts", summary="Danh sách cảnh báo")
async def get_session_alerts(session_id: int):
    from database import get_alerts
    alerts = await get_alerts(session_id)
    return {"session_id": session_id, "alerts": alerts}


@router.get("/{session_id}/report", summary="Báo cáo tổng hợp buổi học")
async def get_session_report(session_id: int):
    """Báo cáo tổng hợp: session info + summary + engagement timeline + attendance."""
    from database import (
        get_session_by_id, get_session_summary as _get_summary,
        get_attendance, get_engagement_timeline, get_alerts,
    )

    session = await get_session_by_id(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy buổi học")

    summary = await _get_summary(session_id)
    attendance = await get_attendance(session_id)
    timeline = await get_engagement_timeline(session_id)
    alerts = await get_alerts(session_id)

    # Build report
    report = {
        "session_id": session_id,
        "session_name": session.get("session_name", ""),
        "class_name": session.get("class_name", ""),
        "subject": session.get("subject", ""),
        "teacher_name": session.get("teacher_name", ""),
        "start_time": session.get("start_time"),
        "end_time": session.get("end_time"),
    }

    if summary:
        report.update({
            "avg_engagement": summary.get("avg_engagement", 0),
            "peak_engagement": summary.get("peak_engagement", 0),
            "lowest_engagement": summary.get("lowest_engagement", 0),
            "duration_seconds": (summary.get("duration_minutes", 0) or 0) * 60,
            "present_students": summary.get("present_count", 0),
            "total_students": summary.get("total_students", 0),
            "frames_processed": 0,
            "alert_count": summary.get("alerts_count", 0),
            "emotion_summary": summary.get("emotion_distribution", {}),
            "engagement_timeline": summary.get("engagement_timeline", []),
            "recommendations": summary.get("recommendations", []),
        })
    else:
        # Build from raw data if no summary saved yet
        engagement_values = [e.get("avg_engagement", 0) for e in timeline] if timeline else []
        avg_eng = sum(engagement_values) / len(engagement_values) if engagement_values else 0

        # Calculate duration
        duration_seconds = 0
        if session.get("start_time") and session.get("end_time"):
            try:
                from datetime import datetime as dt
                st = dt.strptime(session["start_time"], "%Y-%m-%d %H:%M:%S")
                et = dt.strptime(session["end_time"], "%Y-%m-%d %H:%M:%S")
                duration_seconds = (et - st).total_seconds()
            except ValueError:
                pass

        # Attention rate from latest attention distribution
        attention_rate = 0
        if timeline:
            last = timeline[-1]
            att_dist = last.get("attention_distribution", {})
            if isinstance(att_dist, str):
                import json
                att_dist = json.loads(att_dist)
            total_att = sum(att_dist.values()) if att_dist else 0
            if total_att > 0:
                attention_rate = round(att_dist.get("attentive", 0) / total_att * 100)

        present_count = sum(1 for a in attendance if a.get("status") == "present")

        report.update({
            "avg_engagement": round(avg_eng, 1),
            "attention_rate": attention_rate,
            "duration_seconds": duration_seconds,
            "present_students": present_count,
            "total_students": len(attendance),
            "frames_processed": len(timeline),
            "alert_count": len(alerts),
            "emotion_summary": {},
            "engagement_timeline": [e.get("avg_engagement", 0) for e in timeline],
            "recommendations": [],
        })

    return report


@router.get("/{session_id}/export", summary="Xuất CSV buổi học")
async def export_session(
    session_id: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
):
    """Xuất dữ liệu điểm danh + engagement của buổi học dưới dạng CSV hoặc JSON."""
    import io
    import csv as csv_module
    from fastapi.responses import StreamingResponse, JSONResponse
    from database import get_session_by_id, get_attendance, get_engagement_timeline

    session = await get_session_by_id(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy buổi học")

    attendance = await get_attendance(session_id)
    timeline  = await get_engagement_timeline(session_id)

    if format == "json":
        return JSONResponse({
            "session": session,
            "attendance": attendance,
            "engagement_timeline": timeline,
        })

    # CSV export
    output = io.StringIO()
    writer = csv_module.writer(output)

    # Header info
    writer.writerow(["Buổi học", session.get("session_name", "")])
    writer.writerow(["Lớp", session.get("class_name", "")])
    writer.writerow(["Môn học", session.get("subject", "")])
    writer.writerow(["Giáo viên", session.get("teacher_name", "")])
    writer.writerow(["Bắt đầu", session.get("start_time", "")])
    writer.writerow(["Kết thúc", session.get("end_time", "")])
    writer.writerow([])

    # Attendance table
    writer.writerow(["Mã học sinh", "Tên", "Trạng thái", "Giờ đến", "Giờ về"])
    for a in attendance:
        writer.writerow([
            a.get("student_id", ""),
            a.get("student_name", ""),
            a.get("status", ""),
            a.get("arrival_time", ""),
            a.get("leave_time", ""),
        ])

    output.seek(0)
    filename = f"session_{session_id}_{session.get('start_time', 'export')[:10]}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
