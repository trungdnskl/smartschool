"""
processing.py — Camera frame processing pipeline.

Tách từ main.py để:
  - Không có circular imports
  - main.py chỉ cần import on_frame_detected
  - Dễ test riêng lẻ

Tối ưu v2:
  - Async evidence capture (ThreadPoolExecutor — non-blocking disk I/O)
  - Temporal smoothing cho engagement metrics
  - Selective inference caching
"""
import asyncio
import cv2
import logging
import os
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Thread pool for non-blocking disk I/O (evidence capture)
_io_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="evidence-io")

# ── Evidence capture ──────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_EVIDENCE_DIR = os.path.join(_DATA_DIR, "alert_evidence")
os.makedirs(_EVIDENCE_DIR, exist_ok=True)

# Cache frame mới nhất cho mỗi camera (thread-safe enough cho use case này)
_latest_frames: Dict[str, np.ndarray] = {}


def cleanup_camera_frames(camera_id: str = None) -> None:
    """
    Remove cached frames for a specific camera or all cameras.
    Call when camera stops or session ends to prevent memory leaks.
    """
    if camera_id:
        _latest_frames.pop(camera_id, None)
        logger.debug(f"[Processing] Cleared frame cache for {camera_id}")
    else:
        _latest_frames.clear()
        logger.debug("[Processing] Cleared all frame caches")


def _capture_evidence(
    frame: np.ndarray,
    alert: Dict[str, Any],
    session_id: int,
    snapshot: Dict[str, Any],
) -> Optional[str]:
    """
    Chụp ảnh minh chứng cho cảnh báo.
    Vẽ overlay thông tin lên frame và lưu JPEG.
    Uses PIL for Vietnamese Unicode text rendering.
    Returns: relative path (from data/) or None on failure.
    """
    try:
        ts = datetime.now()
        safe_type = alert.get("alert_type", "alert").replace(" ", "_")
        filename = f"s{session_id}_{ts.strftime('%H%M%S')}_{safe_type}.jpg"
        filepath = os.path.join(_EVIDENCE_DIR, filename)

        # Copy frame to avoid modifying original
        evidence = frame.copy()
        h, w = evidence.shape[:2]

        # ── Draw overlay (shapes with OpenCV) ─────────
        # Semi-transparent dark banner at top
        overlay = evidence.copy()
        cv2.rectangle(overlay, (0, 0), (w, 56), (15, 20, 40), -1)
        cv2.addWeighted(overlay, 0.7, evidence, 0.3, 0, evidence)

        # Severity colors
        severity_colors_bgr = {
            "warning": (0, 165, 245),
            "info": (245, 180, 59),
            "danger": (68, 68, 239),
        }
        sev_color_bgr = severity_colors_bgr.get(alert.get("severity"), (200, 200, 200))
        # PIL uses RGB
        sev_color_rgb = (sev_color_bgr[2], sev_color_bgr[1], sev_color_bgr[0])

        # Severity dot
        cv2.circle(evidence, (20, 28), 8, sev_color_bgr, -1)

        # ── Draw face bboxes (OpenCV shapes) ──────────
        for student in snapshot.get("students", []):
            bbox = student.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            eng = student.get("engagement_score", 0)

            if eng >= 60:
                box_color = (0, 200, 100)
            elif eng >= 40:
                box_color = (0, 180, 245)
            else:
                box_color = (0, 80, 230)

            cv2.rectangle(evidence, (x1, y1), (x2, y2), box_color, 2)

        # ── Alert message banner at bottom (shape) ────
        msg = alert.get("message", "")[:80]
        if msg:
            overlay2 = evidence.copy()
            cv2.rectangle(overlay2, (0, h - 40), (w, h), (15, 20, 40), -1)
            cv2.addWeighted(overlay2, 0.7, evidence, 0.3, 0, evidence)

        # ── Render text with PIL (Unicode support) ────
        evidence = _draw_text_pil(evidence, alert, ts, snapshot, sev_color_rgb, msg)

        # ── Save ──────────────────────────────────────
        cv2.imwrite(filepath, evidence, [cv2.IMWRITE_JPEG_QUALITY, 85])

        rel_path = f"alert_evidence/{filename}"
        logger.info(f"[Evidence] Captured: {filename} ({alert.get('alert_type')})")
        return rel_path

    except Exception as e:
        logger.error(f"[Evidence] Capture failed: {e}")
        return None


# ── PIL text rendering helper ─────────────────────────────

_pil_font_cache: Dict[int, Any] = {}


def _get_font(size: int):
    """Load a TrueType font that supports Vietnamese, with caching."""
    if size in _pil_font_cache:
        return _pil_font_cache[size]

    from PIL import ImageFont
    import platform

    font = None
    # Try common fonts that support Vietnamese
    font_candidates = []
    if platform.system() == "Windows":
        font_candidates = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    else:
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    for fp in font_candidates:
        try:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, size)
                break
        except Exception:
            continue

    if font is None:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            font = ImageFont.load_default()

    _pil_font_cache[size] = font
    return font


def _draw_text_pil(
    frame: np.ndarray,
    alert: Dict[str, Any],
    ts: datetime,
    snapshot: Dict[str, Any],
    sev_color_rgb: tuple,
    msg: str,
) -> np.ndarray:
    """Draw all text overlays using PIL for full Unicode support."""
    try:
        from PIL import Image, ImageDraw

        h, w = frame.shape[:2]
        # Convert BGR → RGB → PIL Image
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        font_title = _get_font(18)
        font_sub = _get_font(14)
        font_small = _get_font(13)

        # Alert type (top-left)
        alert_text = alert.get("alert_type", "Alert").replace("_", " ").upper()
        draw.text((36, 8), alert_text, font=font_title, fill=(255, 255, 255))

        # Timestamp (below title)
        time_text = ts.strftime("%H:%M:%S  %d/%m/%Y")
        draw.text((36, 30), time_text, font=font_sub, fill=(180, 180, 200))

        # Engagement + faces (top-right)
        eng_text = f"Eng: {snapshot.get('avg_engagement', 0):.0f}%"
        faces_text = f"Faces: {snapshot.get('total_faces', 0)}"
        draw.text((w - 160, 8), eng_text, font=font_title, fill=(0, 255, 200))
        draw.text((w - 160, 30), faces_text, font=font_sub, fill=(180, 180, 200))

        # Face labels
        for student in snapshot.get("students", []):
            bbox = student.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            name = student.get("student_name", "")
            eng = student.get("engagement_score", 0)
            attention = student.get("attention_direction", "")

            if eng >= 60:
                lbl_color = (0, 200, 100)
            elif eng >= 40:
                lbl_color = (245, 180, 0)
            else:
                lbl_color = (230, 80, 0)

            label = name or "Face"
            if attention in ("looking_away", "head_down", "looking_down"):
                attn_vi = {
                    "looking_away": "nhìn chỗ khác",
                    "head_down": "gục đầu",
                    "looking_down": "cúi đầu",
                }.get(attention, attention)
                label += f" ({attn_vi})"

            label_y = max(y1 - 18, 2)
            draw.text((x1, label_y), label, font=font_small, fill=lbl_color)

        # Bottom message banner
        if msg:
            draw.text((12, h - 30), msg, font=font_sub, fill=sev_color_rgb)

        # Convert back to BGR numpy array
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    except ImportError:
        logger.warning("[Evidence] Pillow not installed — text may show ????")
        # Fallback: cv2.putText (no Vietnamese support)
        alert_text = alert.get("alert_type", "Alert").replace("_", " ").upper()
        cv2.putText(frame, alert_text, (36, 24),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        return frame


# ── Store & Broadcast ─────────────────────────────────────

async def _store_and_broadcast(snapshot: Dict[str, Any], raw_frame: Optional[np.ndarray] = None) -> None:
    """Store engagement snapshot → DB, broadcast → WebSocket clients."""
    from state import state
    from database import insert_engagement_log, upsert_attendance, insert_alert

    session_id = state.active_session_id

    # Sanitize students for WS (strip raw numpy arrays)
    students_data = [
        {
            "face_id": s.get("face_id"),
            "emotion": s.get("emotion"),
            "emotion_vi": s.get("emotion_vi"),
            "learning_state": s.get("learning_state"),
            "learning_state_vi": s.get("learning_state_vi"),
            "attention_direction": s.get("attention_direction"),
            "attention_direction_vi": s.get("attention_direction_vi"),
            "engagement_score": s.get("engagement_score"),
            "student_name": s.get("student_name"),
            "student_id": s.get("student_id"),
            "bbox": s.get("bbox"),
            "match_engine": s.get("match_engine"),          # P2-5: arcface/lbph
            "match_confidence": s.get("match_confidence"),  # P2-5: 0.0-1.0
        }
        for s in snapshot.get("students", [])
    ]

    try:
        # Always broadcast to WebSocket (even without active session)
        # Apply temporal smoothing for smoother UI updates
        smoothed_engagement = state.smoother.smooth(
            "avg_engagement", snapshot.get("avg_engagement", 0)
        )
        smoothed_faces = state.smoother.smooth(
            "total_faces", snapshot.get("total_faces", 0)
        )

        await state.broadcast({
            "type": "engagement_update",
            "data": {
                "timestamp": snapshot.get("timestamp", ""),
                "total_faces": round(smoothed_faces),
                "total_faces_raw": snapshot.get("total_faces", 0),
                "avg_engagement": round(smoothed_engagement, 1),
                "avg_engagement_raw": snapshot.get("avg_engagement", 0),
                "emotion_distribution": snapshot.get("emotion_distribution", {}),
                "learning_state_distribution": snapshot.get("learning_state_distribution", {}),
                "attention_distribution": snapshot.get("attention_distribution", {}),
                "students": students_data,
                "process_time_ms": snapshot.get("process_time_ms", 0),
                "session_active": session_id is not None,
                # ── Headcount & Attendance ──
                "headcount": snapshot.get("headcount", 0),
                "identified_count": snapshot.get("identified_count", 0),
                "unidentified_count": snapshot.get("unidentified_count", 0),
                "total_persons": snapshot.get("total_persons", 0),
                "teacher_detected": snapshot.get("teacher_detected", False),
                "teacher_name": snapshot.get("teacher_name"),
            },
        })
    except Exception as e:
        logger.error(f"[Processing] broadcast error: {e}")

    # DB writes only when session is active
    if session_id is None:
        return

    try:
        # 1. Engagement log
        await insert_engagement_log({
            "session_id": session_id,
            "timestamp": snapshot.get("timestamp", ""),
            "total_faces": snapshot.get("total_faces", 0),
            "avg_engagement": snapshot.get("avg_engagement", 0),
            "avg_emotion_score": snapshot.get("avg_emotion_score", 0),
            "avg_attention_score": snapshot.get("avg_attention_score", 0),
            "emotion_distribution": snapshot.get("emotion_distribution", {}),
            "learning_state_distribution": snapshot.get("learning_state_distribution", {}),
            "attention_distribution": snapshot.get("attention_distribution", {}),
        })

        # 2. Attendance updates
        if state.detector:
            attendance = state.detector.get_attendance()
            for record in attendance.get("records", []):
                if record.get("status") != "absent":
                    await upsert_attendance({
                        "session_id": session_id,
                        "student_id": record.get("student_id", ""),
                        "student_name": record.get("student_name", ""),
                        "status": record.get("status", "present"),
                        "arrival_time": record.get("arrival_time"),
                    })

        # 3. Alerts + Evidence capture (async disk I/O)
        for alert in snapshot.get("alerts", []):
            alert_copy = dict(alert)
            alert_copy["session_id"] = session_id

            # Capture evidence frame via ThreadPoolExecutor (non-blocking)
            if raw_frame is not None:
                loop = asyncio.get_event_loop()
                evidence_path = await loop.run_in_executor(
                    _io_executor,
                    _capture_evidence, raw_frame, alert, session_id, snapshot
                )
                if evidence_path:
                    alert_copy["evidence_path"] = evidence_path

            await insert_alert(alert_copy)

        # 4. Broadcast alerts individually (with evidence path)
        for alert in snapshot.get("alerts", []):
            await state.broadcast({"type": "alert", "data": alert})

    except Exception as e:
        logger.error(f"[Processing] DB write error: {e}")


def on_frame_detected(camera_id: str, camera_name: str, frame) -> None:
    """
    Callback được gọi bởi CameraManager mỗi khi có frame mới.
    Chạy trong camera thread — phải thread-safe.
    """
    from state import state

    # Process frames even without an active session (for live preview stats)
    # DB writes are guarded inside _store_and_broadcast
    if state.detector is None:
        return

    try:
        # Cache latest frame for evidence capture
        _latest_frames[camera_id] = frame.copy()

        result = state.detector.process_frame(camera_id, camera_name, frame)
        if result is None:
            return

        state.latest_snapshot = result

        # Dispatch coroutine sang event loop của main thread (thread-safe)
        if state._event_loop is not None and not state._event_loop.is_closed():
            # Pass raw frame for evidence capture (only when alerts exist)
            raw = frame if result.get("alerts") else None
            asyncio.run_coroutine_threadsafe(
                _store_and_broadcast(result, raw_frame=raw),
                state._event_loop,
            )

    except Exception as e:
        logger.error(f"[Processing] Frame error: {e}")

