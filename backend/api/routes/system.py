"""
api/routes/system.py — Health, metrics, stats endpoints.

GET /health              → K8s liveness probe
GET /ready               → K8s readiness probe
GET /metrics             → Prometheus-style text metrics
GET /api/stats           → Dashboard stats
GET /api/engagement/current
GET /api/engagement/timeline
GET /api/attendance/current
POST /api/attendance/manual
"""
import logging
import time

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import PlainTextResponse

from api.deps import require_teacher
from state import state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])
_startup_time = time.time()


# ── Health / Readiness ────────────────────────────────

@router.get("/health", summary="Liveness probe")
async def health():
    """K8s liveness — always 200 if process alive."""
    return {
        "status": "healthy",
        "uptime_seconds": round(time.time() - _startup_time, 1),
    }


@router.get("/ready", summary="Readiness probe")
async def ready():
    """K8s readiness — 503 if DB or AI not initialized."""
    issues = []
    if state.detector is None:
        issues.append("AI detector not initialized")
    if state.camera_manager is None:
        issues.append("Camera manager not initialized")

    if issues:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "issues": issues},
        )
    return {"status": "ready"}


# ── Prometheus Metrics ────────────────────────────────

@router.get("/metrics", response_class=PlainTextResponse, summary="Prometheus metrics")
async def metrics():
    """
    Prometheus-compatible text metrics.
    Scrape với: prometheus.yml → scrape_configs.static_configs.targets
    """
    lines = [
        "# HELP classroom_uptime_seconds Server uptime",
        "# TYPE classroom_uptime_seconds gauge",
        f"classroom_uptime_seconds {round(time.time() - _startup_time, 1)}",
        "",
        "# HELP classroom_session_active 1 if session active",
        "# TYPE classroom_session_active gauge",
        f"classroom_session_active {1 if state.active_session_id else 0}",
        "",
        "# HELP classroom_websocket_clients Connected WebSocket clients",
        "# TYPE classroom_websocket_clients gauge",
        f"classroom_websocket_clients {len(state.websocket_connections)}",
        "",
    ]

    if state.camera_manager:
        lines += [
            "# HELP classroom_cameras_active Active cameras",
            "# TYPE classroom_cameras_active gauge",
            f"classroom_cameras_active {state.camera_manager.get_active_count()}",
            "",
            "# HELP classroom_cameras_total Total configured cameras",
            "# TYPE classroom_cameras_total gauge",
            f"classroom_cameras_total {len(state.camera_manager.cameras)}",
            "",
        ]

    if state.detector:
        perf = state.detector.get_performance_stats()
        avg_ms = perf.get("avg_process_time_ms", 0)
        lines += [
            "# HELP classroom_process_time_ms Average AI processing time per frame",
            "# TYPE classroom_process_time_ms gauge",
            f"classroom_process_time_ms {avg_ms}",
            "",
        ]

    if state.latest_snapshot:
        lines += [
            "# HELP classroom_avg_engagement Current average engagement score",
            "# TYPE classroom_avg_engagement gauge",
            f"classroom_avg_engagement {state.latest_snapshot.get('avg_engagement', 0)}",
            "",
            "# HELP classroom_total_faces Faces detected in last frame",
            "# TYPE classroom_total_faces gauge",
            f"classroom_total_faces {state.latest_snapshot.get('total_faces', 0)}",
            "",
        ]

    return "\n".join(lines)


# ── Dashboard Stats ───────────────────────────────────

@router.get("/api/stats", summary="Thống kê dashboard")
async def get_stats():
    from database import get_dashboard_stats

    db_stats = await get_dashboard_stats()
    perf = state.detector.get_performance_stats() if state.detector else {}
    active_cams = state.camera_manager.get_active_count() if state.camera_manager else 0
    total_cams = len(state.camera_manager.cameras) if state.camera_manager else 0

    return {
        **db_stats,
        "active_cameras": active_cams,
        "total_cameras": total_cams,
        "session_active": state.active_session_id is not None,
        "active_session_id": state.active_session_id,
        **perf,
    }


@router.get("/api/system/config", summary="Cấu hình hệ thống (read-only)")
async def get_system_config():
    """Trả về config.yaml dạng JSON cho Settings page."""
    from dataclasses import asdict
    from config import get_config
    cfg = get_config()
    d = asdict(cfg)
    # Remove sensitive camera URLs
    d.pop("cameras", None)
    d.pop("database", None)
    d.pop("server", None)
    return d


@router.get("/api/config/hot", summary="Get hot-reloadable params")
async def get_hot_config():
    """Trả về các parameters có thể thay đổi runtime."""
    from config import get_hot_params
    return {"params": get_hot_params()}


@router.patch("/api/config/hot", summary="Update hot-reloadable params")
async def update_hot_config(
    updates: dict,
    _: dict = Depends(require_teacher),
):
    """
    Cập nhật threshold/tuning params mà KHÔNG cần restart.

    Body example:
    ```json
    {
        "detection": {"face_confidence": 0.6, "frame_skip": 4},
        "engagement": {"alert_threshold": 35}
    }
    ```
    """
    from config import update_hot_params
    changes = update_hot_params(updates)
    if changes:
        logger.info(f"[Config] Hot-reload applied: {changes}")
    return {"status": "ok", "changes": changes}


@router.post("/api/config/reload", summary="Reload config from file")
async def reload_config_file(_: dict = Depends(require_teacher)):
    """Re-read config.yaml và áp dụng hot-reloadable changes."""
    from config import reload_config_from_file
    result = reload_config_from_file()
    logger.info(f"[Config] File reload result: {result}")
    return {"status": "ok", "result": result}


@router.get("/api/system/stats", summary="Thông tin hệ thống & tài nguyên")
async def get_system_stats():
    """Trả về system stats (CPU, RAM, DB counts, cameras) cho Settings page."""
    import psutil
    from database import get_dashboard_stats

    db_stats = await get_dashboard_stats()
    active_cams = state.camera_manager.get_active_count() if state.camera_manager else 0
    total_cams = len(state.camera_manager.cameras) if state.camera_manager else 0

    return {
        "total_sessions": db_stats.get("total_sessions", 0),
        "total_students": db_stats.get("total_students", 0),
        "total_teachers": db_stats.get("total_teachers", 0),
        "total_classes": db_stats.get("total_classes", 0),
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "memory_percent": psutil.virtual_memory().percent,
        "uptime_seconds": round(time.time() - _startup_time, 1),
        "cameras": {
            "total": total_cams,
            "running": active_cams,
        },
    }



# ── Real-time engagement ──────────────────────────────

@router.get("/api/engagement/current", summary="Engagement hiện tại")
async def get_current_engagement():
    if state.latest_snapshot:
        return state.latest_snapshot
    return {"total_faces": 0, "avg_engagement": 0, "students": []}


@router.get("/api/engagement/timeline", summary="Timeline engagement live")
async def get_live_timeline():
    if state.detector:
        return {"timeline": state.detector.get_engagement_timeline()}
    return {"timeline": []}


# ── Real-time attendance ──────────────────────────────

@router.get("/api/attendance/current", summary="Điểm danh hiện tại")
async def get_current_attendance():
    if state.detector:
        return state.detector.get_attendance()
    return {"total": 0, "present": 0, "late": 0, "absent": 0, "records": []}


@router.post("/api/attendance/manual", summary="Điểm danh thủ công")
async def manual_attendance(
    student_id: str = Form(...),
    status: str = Form("present"),
    _: dict = Depends(require_teacher),
):
    """Giáo viên điểm danh thủ công cho học sinh cụ thể."""
    from database import upsert_attendance

    if not state.detector:
        raise HTTPException(500, "Hệ thống chưa khởi tạo")
    if state.active_session_id is None:
        raise HTTPException(400, "Chưa có buổi học đang diễn ra")

    success = state.detector.attendance_tracker.mark_attendance_manual(student_id, status)
    if not success:
        raise HTTPException(404, f"Không tìm thấy học sinh {student_id} trong session")

    record = state.detector.attendance_tracker._attendance.get(student_id, {})
    await upsert_attendance({
        "session_id": state.active_session_id,
        "student_id": student_id,
        "student_name": record.get("student_name", ""),
        "status": status,
        "arrival_time": record.get("arrival_time"),
    })
    return {"status": "ok", "message": f"Đã điểm danh {student_id}: {status}"}


# ── Alerts management ───────────────────────────────

@router.post("/api/alerts/{alert_id}/read", summary="Đánh dấu cảnh báo đã đọc")
async def mark_alert_read(alert_id: int, _: dict = Depends(require_teacher)):
    from database import mark_alert_read as _mark_read
    await _mark_read(alert_id)
    return {"status": "ok", "alert_id": alert_id}


@router.post("/api/alerts/read-all", summary="Đánh dấu tất cả cảnh báo đã đọc")
async def mark_all_alerts_read(
    session_id: int = Form(None),
    _: dict = Depends(require_teacher),
):
    from database import mark_all_alerts_read as _mark_all
    count = await _mark_all(session_id)
    return {"status": "ok", "marked_count": count}
