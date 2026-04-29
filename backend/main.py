"""
Classroom Engagement Analysis System — Main Application
========================================================
main.py chỉ còn chứa:
  1. App factory + lifespan (startup/shutdown)
  2. WebSocket endpoint
  3. Static file serving
  4. Router registration

Business logic đã chuyển vào:
  - api/routes/sessions.py
  - api/routes/students.py
  - api/routes/teachers.py
  - api/routes/cameras.py
  - api/routes/system.py
  - api/routes/auth.py
  - processing.py (frame pipeline)
  - state.py      (global state)
"""

import asyncio
import json
import logging
import os
import sys

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ── Path setup ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Logging (structured JSON in production) ───────────
from core.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# ── State & processing pipeline ───────────────────────
from state import state
from processing import on_frame_detected

# ── Config & infrastructure ───────────────────────────
from config import get_config
from database import init_db, get_dashboard_stats, recover_stuck_sessions, cleanup_expired_data
from db_provider import init_database, get_db_manager
from camera_manager import CameraManager
from classroom_detector import ClassroomDetector

# ── Routers ───────────────────────────────────────────
from api.routes.auth     import router as auth_router
from api.routes.sessions import router as sessions_router
from api.routes.students import router as students_router
from api.routes.teachers import router as teachers_router
from api.routes.cameras  import router as cameras_router
from api.routes.system   import router as system_router


# ══════════════════════════════════════════════════════
# Lifespan — startup / shutdown
# ══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, load AI models, register cameras. Shutdown: stop cameras."""

    # Must be first — capture event loop for thread callbacks
    state.init()

    logger.info("=" * 55)
    logger.info("  Classroom Engagement Analysis System")
    logger.info("  Real-time learning engagement monitoring")
    logger.info("=" * 55)

    # Config
    state.config = get_config()
    cfg = state.config
    logger.info(f"[Config] Classroom : {cfg.classroom.name}")
    logger.info(f"[Config] Cameras   : {len(cfg.cameras)}")

    # Database (creates tables + default admin user if needed)
    await init_db()

    # Initialize database abstraction layer (supports SQLite + PostgreSQL)
    try:
        await init_database(cfg)
        logger.info(f"[Main] DB Provider: {get_db_manager().provider_name}")
    except Exception as e:
        logger.warning(f"[Main] DB Provider init skipped: {e} (using direct SQLite)")

    # Fix DB2: Recover sessions stuck as is_active=1 from previous crash
    recovered = await recover_stuck_sessions()
    if recovered:
        logger.warning(f"[Main] Recovered {recovered} stuck sessions from previous crash")

    # ClassroomDetector — background initialization (non-blocking startup)
    state.detector = ClassroomDetector(
        face_model=cfg.detection.face_model,
        face_confidence=cfg.detection.face_confidence,
        emotion_model=cfg.detection.emotion_model,
        emotion_update_interval=cfg.detection.emotion_update_interval,
        head_pose_enabled=cfg.detection.head_pose_enabled,
        max_faces=cfg.detection.max_faces,
        engagement_weights=cfg.engagement.weights,
        alert_threshold=cfg.engagement.alert_threshold,
        confusion_alert_duration=cfg.engagement.confusion_alert_duration,
        match_threshold=cfg.attendance.match_threshold,
        deep_face_threshold=cfg.attendance.deep_face_threshold,
        attendance_check_interval=cfg.attendance.check_interval,
        late_threshold_minutes=cfg.attendance.late_threshold_minutes,
    )

    # Load AI models in background thread (non-blocking event loop)
    try:
        await asyncio.to_thread(state.detector.initialize)
        logger.info("[Main] AI models loaded ✓")
    except Exception as e:
        logger.warning(f"[Main] AI models failed ({e}) — running in API-only mode")

    # CameraManager
    state.camera_manager = CameraManager(
        on_frame=on_frame_detected,
        frame_skip=cfg.detection.frame_skip,
    )
    for cam_cfg in cfg.cameras:
        state.camera_manager.add_camera(cam_cfg)

    logger.info(f"[Main] Server  : http://{cfg.server.host}:{cfg.server.port}")
    logger.info(f"[Main] Docs    : http://{cfg.server.host}:{cfg.server.port}/docs")
    logger.info(f"[Main] Auth    : AUTH_ENABLED={os.getenv('AUTH_ENABLED', 'false')}")

    # Data retention cleanup (SRS NFR-03.5 / AC-20)
    # Runs once on startup, then every 24 hours
    async def _retention_loop():
        retention_days = cfg.privacy.data_retention_days
        try:
            result = await cleanup_expired_data(retention_days)
            logger.info(f"[Main] Data retention cleanup done (>{retention_days} days): {result}")
        except Exception as e:
            logger.warning(f"[Main] Data retention cleanup failed: {e}")
        while True:
            await asyncio.sleep(24 * 3600)  # every 24h
            try:
                result = await cleanup_expired_data(retention_days)
                logger.info(f"[Main] Scheduled cleanup: {result}")
            except Exception as e:
                logger.warning(f"[Main] Scheduled cleanup failed: {e}")

    cleanup_task = asyncio.create_task(_retention_loop())

    yield  # ← application runs here

    # Shutdown
    logger.info("[Main] Shutting down...")
    cleanup_task.cancel()
    if state.camera_manager:
        state.camera_manager.stop_all()
    logger.info("[Main] Shutdown complete ✓")


# ══════════════════════════════════════════════════════
# FastAPI App
# ══════════════════════════════════════════════════════

app = FastAPI(
    title="Classroom Engagement Analysis System",
    description=(
        "Hệ thống phân tích mức độ tiếp nhận học tập thời gian thực.\n\n"
        "**Auth**: Set `AUTH_ENABLED=true` + `Authorization: Bearer <token>` "
        "để bật bảo mật. Mặc định không cần token (backward compat)."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────
# allow_credentials=True yêu cầu origins cụ thể (không được là "*")
_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,   # True chỉ khi origins không phải "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting (slowapi) — optional ───────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("[Main] Rate limiting: 200 req/min/IP ✓")
except ImportError:
    logger.info("[Main] slowapi not installed — rate limiting disabled")
    logger.info("[Main] Install with: pip install slowapi")

# ── Routers ───────────────────────────────────────────
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(students_router)
app.include_router(teachers_router)
app.include_router(cameras_router)
app.include_router(system_router)


# ══════════════════════════════════════════════════════
# WebSocket
# ══════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Real-time engagement updates + heartbeat."""
    # ── Auth check (I6: protect WS when AUTH_ENABLED=true) ──
    from api.deps import AUTH_ENABLED
    if AUTH_ENABLED:
        token = ws.query_params.get("token")
        if not token:
            await ws.close(code=1008, reason="Authentication required")
            return
        try:
            from core.security import decode_token
            decode_token(token)  # validates exp + signature
        except Exception:
            await ws.close(code=1008, reason="Invalid or expired token")
            return

    await ws.accept()

    # Thread-safe add with lock
    if state._ws_lock:
        async with state._ws_lock:
            state.websocket_connections.add(ws)
    else:
        state.websocket_connections.add(ws)
    logger.info(f"[WS] Client connected (total: {len(state.websocket_connections)})")

    try:
        # Send initial state
        db_stats = await get_dashboard_stats()
        await ws.send_json({
            "type": "init",
            "data": {
                **db_stats,
                "session_active": state.active_session_id is not None,
                "active_session_id": state.active_session_id,
            },
        })

        # Main loop — ping/pong + heartbeat every 30s
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                heartbeat: dict = {
                    "type": "heartbeat",
                    "data": {
                        "session_active": state.active_session_id is not None,
                        "active_cameras": (
                            state.camera_manager.get_active_count()
                            if state.camera_manager else 0
                        ),
                    },
                }
                if state.latest_snapshot:
                    heartbeat["data"]["avg_engagement"] = state.latest_snapshot.get("avg_engagement", 0)
                    heartbeat["data"]["total_faces"]    = state.latest_snapshot.get("total_faces", 0)
                try:
                    await ws.send_json(heartbeat)
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[WS] Unexpected error: {e}")
    finally:
        # Thread-safe remove with lock
        if state._ws_lock:
            async with state._ws_lock:
                state.websocket_connections.discard(ws)
        else:
            state.websocket_connections.discard(ws)
        logger.info(f"[WS] Client disconnected (remaining: {len(state.websocket_connections)})")


# ══════════════════════════════════════════════════════
# Static Files
# ══════════════════════════════════════════════════════

_project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_index = os.path.join(_project_dir, "index.html")

# Mount alert evidence directory for serving captured snapshots
_evidence_dir = os.path.join(_project_dir, "data", "alert_evidence")
os.makedirs(_evidence_dir, exist_ok=True)
app.mount("/api/evidence", StaticFiles(directory=_evidence_dir), name="evidence")

if os.path.exists(_index):
    _images = os.path.join(_project_dir, "images")
    if os.path.exists(_images):
        app.mount("/images", StaticFiles(directory=_images), name="images")

    @app.get("/styles.css", include_in_schema=False)
    async def serve_css():
        return FileResponse(os.path.join(_project_dir, "styles.css"))

    @app.get("/app.js", include_in_schema=False)
    async def serve_js():
        return FileResponse(os.path.join(_project_dir, "app.js"))

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(_index)


# ══════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    cfg = get_config()
    uvicorn.run(
        "main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        reload=False,
        log_level="info",
    )
