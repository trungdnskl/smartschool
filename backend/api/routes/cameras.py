"""
api/routes/cameras.py — Camera management endpoints.

Tách từ main.py (~lines 1059-1149).
SEC-02: Validate URL trước khi cho phép kết nối (ngăn SSRF).
"""
import asyncio
import io
import logging
import re
import threading
import time
from typing import Optional
from urllib.parse import urlparse

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import Response, StreamingResponse

from api.deps import require_admin, require_teacher
from state import state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cameras", tags=["Cameras"])

# ── Emotion → colour mapping ───────────────────────────
_EMOTION_COLORS = {
    "happy":    (50,  210,  50),   # green
    "neutral":  (180, 180, 180),   # grey
    "sad":      (80,  130, 220),   # blue
    "angry":    (50,   50, 220),   # red-blue
    "fear":     (200,  80, 200),   # purple
    "surprise": (50,  200, 220),   # cyan
    "disgust":  (50,  180, 100),   # teal
}
_DEFAULT_COLOR = (0, 200, 255)     # orange


# ── Overlay colours ───────────────────────────────────
_CLR_GREEN  = (0, 255, 100)     # Recognised student
_CLR_YELLOW = (0, 230, 255)     # Unknown face
_CLR_RED    = (60, 60, 255)     # Sleeping / head down
_CLR_PERSON = (255, 180, 50)    # Person bbox (cyan-blue)

_STREAM_MAX_W = 960


def _draw_faces_on_frame(frame: np.ndarray) -> np.ndarray:
    """Draw person bboxes (YOLO) + face bboxes (MediaPipe) with HUD."""
    overlay = frame.copy()
    snapshot = state.latest_snapshot
    if not snapshot:
        return overlay

    h, w = overlay.shape[:2]
    sc = max(w / 1280, 0.5)
    font = cv2.FONT_HERSHEY_SIMPLEX

    # ── Person bboxes (YOLOv8 body detection) ──
    persons = snapshot.get("persons", [])
    for p in persons:
        bbox = p.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        x1, y1, x2, y2 = max(0, int(bbox[0])), max(0, int(bbox[1])), min(w-1, int(bbox[2])), min(h-1, int(bbox[3]))

        # Thin person outline
        tk = max(1, int(2 * sc))
        cv2.rectangle(overlay, (x1, y1), (x2, y2), _CLR_PERSON, tk)

        # Person ID label at top
        pid = p.get("person_id", "?")
        label = f"P{pid}"
        fs = 0.35 * sc
        (tw, th_t), _ = cv2.getTextSize(label, font, fs, 1)
        cv2.rectangle(overlay, (x1, y1), (x1 + tw + 6, y1 + th_t + 6), _CLR_PERSON, -1)
        cv2.putText(overlay, label, (x1+3, y1+th_t+3), font, fs, (0,0,0), max(1,int(sc)), cv2.LINE_AA)

    # ── Face bboxes (MediaPipe + engagement) ──
    students = snapshot.get("students", [])
    for s in students:
        bbox = s.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        x1, y1, x2, y2 = max(0, int(bbox[0])), max(0, int(bbox[1])), min(w-1, int(bbox[2])), min(h-1, int(bbox[3]))

        name      = s.get("student_name", "")
        score     = s.get("engagement_score", 0)
        attention = s.get("attention_direction", s.get("attention", ""))

        color = _CLR_RED if attention in ("head_down", "sleeping") else (_CLR_GREEN if name else _CLR_YELLOW)

        # Thick face bbox + corner accents
        tk = max(2, int(3 * sc))
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, tk)
        cl = max(10, int(20 * sc))
        ct = tk + 1
        for (cx, cy, dx, dy) in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
            cv2.line(overlay, (cx, cy), (cx + dx*cl, cy), color, ct)
            cv2.line(overlay, (cx, cy), (cx, cy + dy*cl), color, ct)

        # Label
        label = ("[v] " + name) if name else f"[?] #{s.get('face_id', '?')}"
        fs = 0.45 * sc
        (tw, th_t), _ = cv2.getTextSize(label, font, fs, 1)
        ly = max(y1 - th_t - 8, 0)
        cv2.rectangle(overlay, (x1, ly), (x1 + tw + 8, ly + th_t + 8), color, -1)
        cv2.putText(overlay, label, (x1+4, ly+th_t+4), font, fs, (0,0,0), max(1,int(sc)), cv2.LINE_AA)

        # Engagement %
        cv2.putText(overlay, f"{int(score)}%", (x1+2, y2+int(16*sc)), font, 0.4*sc, color, max(1,int(sc)), cv2.LINE_AA)

    # ── Bottom HUD ──
    hud_h = int(28 * sc)
    cv2.rectangle(overlay, (0, h-hud_h), (w, h), (10,12,20), -1)
    n_persons = snapshot.get("total_persons", 0)
    n_faces = snapshot.get("total_faces", 0)
    eng = snapshot.get("avg_engagement", 0)
    ts = snapshot.get("timestamp", "")
    recog = sum(1 for s in students if s.get("student_name"))
    hud = f"Students: {n_persons} | Faces: {n_faces} | ID: {recog} | Eng: {int(eng)}% | {ts}"
    cv2.putText(overlay, hud, (8, h-int(7*sc)), font, 0.4*sc, (200,220,240), max(1,int(sc)), cv2.LINE_AA)

    return overlay


# ── SEC-02: URL Validator ─────────────────────────────

_ALLOWED_SCHEMES = {"rtsp", "rtmp", "http", "https"}
_PRIVATE_RANGES = [
    re.compile(r"^10\."),
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^127\."),
    re.compile(r"^localhost$", re.IGNORECASE),
    re.compile(r"^0\.0\.0\.0$"),
]


def _validate_camera_url(url: str) -> None:
    """
    Validate camera URL để ngăn SSRF.
    Chấp nhận: số (local webcam), rtsp://, rtmp://, http(s)://
    Block: file://, internal IPs (10.x, 192.168.x, v.v.), cloud metadata
    """
    if url.isdigit():
        return  # Local webcam index — OK

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(
            400,
            f"URL scheme không hợp lệ: '{parsed.scheme}'. "
            f"Chấp nhận: {', '.join(_ALLOWED_SCHEMES)}, hoặc số (webcam index).",
        )

    host = parsed.hostname or ""
    # Block cloud metadata servers
    if host in ("169.254.169.254", "metadata.google.internal"):
        raise HTTPException(400, "URL bị chặn vì lý do bảo mật (cloud metadata)")

    # Private IPs are allowed (classroom cameras are usually LAN)
    # Uncomment to block private IPs in production:
    # for pattern in _PRIVATE_RANGES:
    #     if pattern.match(host):
    #         raise HTTPException(400, "Không cho phép kết nối đến IP nội bộ")


# ── Request models ────────────────────────────────────

class AddCameraRequest(BaseModel):
    id: str = Field(..., alias="id", min_length=1)
    name: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    type: str = "rtsp"  # frontend sends this, we just ignore it

    class Config:
        # Accept both 'id' and 'cam_id' from clients
        populate_by_name = True


class TestCameraRequest(BaseModel):
    url: str = Field(..., min_length=1)


# ── Endpoints ─────────────────────────────────────────

@router.get("", summary="Danh sách camera")
async def list_cameras():
    cameras = state.camera_manager.get_all_info() if state.camera_manager else []
    return {"cameras": cameras, "total": len(cameras)}


@router.post("", summary="Thêm camera mới")
async def add_camera(
    request: AddCameraRequest,
    _: dict = Depends(require_admin),
):
    """Thêm camera. URL được validate để ngăn SSRF."""
    from config import CameraConfig

    _validate_camera_url(request.url)

    if not state.camera_manager:
        raise HTTPException(500, "Camera manager chưa khởi tạo")

    cam_config = CameraConfig(id=request.id, name=request.name, url=request.url, enabled=True)
    state.camera_manager.add_camera(cam_config)
    logger.info(f"[Camera] Added camera '{request.id}' url={request.url}")
    return {"status": "ok", "message": f"Đã thêm camera {request.id}"}


@router.post("/{camera_id}/start", summary="Bật camera")
async def start_camera(
    camera_id: str,
    _: dict = Depends(require_teacher),
):
    if not state.camera_manager:
        raise HTTPException(500, "Camera manager chưa khởi tạo")
    cam = state.camera_manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(404, "Không tìm thấy camera")
    state.camera_manager.start_camera(camera_id)
    return {"status": "ok", "camera_id": camera_id}


@router.post("/{camera_id}/stop", summary="Tắt camera")
async def stop_camera(
    camera_id: str,
    _: dict = Depends(require_teacher),
):
    if not state.camera_manager:
        raise HTTPException(500, "Camera manager chưa khởi tạo")
    cam = state.camera_manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(404, "Không tìm thấy camera")
    state.camera_manager.stop_camera(camera_id)
    return {"status": "ok", "camera_id": camera_id}


@router.delete("/{camera_id}", summary="Xóa camera")
async def delete_camera(
    camera_id: str,
    _: dict = Depends(require_admin),
):
    if not state.camera_manager:
        raise HTTPException(500, "Camera manager chưa khởi tạo")
    cam = state.camera_manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(404, "Không tìm thấy camera")
    state.camera_manager.remove_camera(camera_id)
    return {"status": "ok", "message": f"Đã xóa camera {camera_id}"}


class EditCameraRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None


@router.put("/{camera_id}", summary="Chỉnh sửa camera")
async def edit_camera(
    camera_id: str,
    request: EditCameraRequest,
    _: dict = Depends(require_admin),
):
    """Chỉnh sửa tên hoặc URL camera. Tự động restart nếu đang chạy."""
    from config import CameraConfig

    if not state.camera_manager:
        raise HTTPException(500, "Camera manager chưa khởi tạo")
    cam = state.camera_manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(404, "Không tìm thấy camera")

    if request.url:
        _validate_camera_url(request.url)

    was_running = cam.status == "running"

    # Stop if running
    if was_running:
        state.camera_manager.stop_camera(camera_id)

    # Update config
    if request.name:
        cam.name = request.name
        cam.config.name = request.name
    if request.url:
        cam.url = request.url
        cam.config.url = request.url

    # Restart if was running
    if was_running:
        state.camera_manager.start_camera(camera_id)

    logger.info(f"[Camera] Edited camera '{camera_id}' name={cam.name} url={cam.url}")
    return {"status": "ok", "message": f"Đã cập nhật camera {camera_id}"}


# ── Live Stream (MJPEG) ────────────────────────────────

def _encode_frame_jpeg(frame: np.ndarray, quality: int = 60) -> bytes:
    """Encode numpy frame to JPEG bytes. Lower quality = faster encoding + smaller payload."""
    success, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise ValueError("JPEG encode failed")
    return buf.tobytes()


def _downscale(frame: np.ndarray, max_w: int = _STREAM_MAX_W) -> np.ndarray:
    """Downscale frame if wider than max_w — huge speed win for 1080p+ cameras."""
    h, w = frame.shape[:2]
    if w <= max_w:
        return frame
    scale = max_w / w
    return cv2.resize(frame, (max_w, int(h * scale)), interpolation=cv2.INTER_AREA)


async def _mjpeg_generator(camera_id: str, with_overlay: bool):
    """
    Async generator yielding MJPEG multipart frames.
    Optimised: downscale → overlay → lower-quality JPEG → ~15 fps.
    """
    boundary = b"--frame"
    empty_wait = 0

    while True:
        cam = state.camera_manager.get_camera(camera_id) if state.camera_manager else None
        if cam is None:
            break

        frame = cam.get_latest_frame()
        if frame is None:
            empty_wait += 1
            # Back off gradually: 30ms → 50ms → 100ms
            await asyncio.sleep(0.03 if empty_wait < 5 else 0.05 if empty_wait < 20 else 0.1)
            continue

        empty_wait = 0

        # IMPORTANT: Draw overlay FIRST on original-res frame (bbox coords match),
        # THEN downscale for faster JPEG encoding + lower bandwidth
        if with_overlay:
            frame = _draw_faces_on_frame(frame)

        frame = _downscale(frame)

        try:
            jpg = _encode_frame_jpeg(frame)
        except Exception:
            await asyncio.sleep(0.05)
            continue

        chunk = (
            boundary + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(jpg)).encode() + b"\r\n"
            b"\r\n" + jpg + b"\r\n"
        )
        yield chunk
        await asyncio.sleep(0.067)   # ~15 fps to browser


@router.get(
    "/{camera_id}/stream",
    summary="Live MJPEG stream (với AI overlay)",
    response_class=StreamingResponse,
    responses={200: {"content": {"multipart/x-mixed-replace": {}}}},
)
async def stream_camera(camera_id: str, overlay: bool = True):
    """
    MJPEG stream từ camera.
    Dán URL vào thẻ <img> trong browser:
      <img src="/api/cameras/cam_front/stream">

    Query param:
      overlay=true  (mặc định) — vẽ bounding boxes AI lên frame
      overlay=false — raw video không overlay
    """
    import asyncio  # local import to avoid circular at module level

    if not state.camera_manager:
        raise HTTPException(500, "Camera manager chưa khởi tạo")
    cam = state.camera_manager.get_camera(camera_id)
    if cam is None:
        raise HTTPException(404, f"Không tìm thấy camera: {camera_id}")
    if cam.status != "running":
        raise HTTPException(409, f"Camera chưa chạy (status: {cam.status}). Hãy bật camera trước.")

    return StreamingResponse(
        _mjpeg_generator(camera_id, with_overlay=overlay),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Connection": "close",
        },
    )


@router.get(
    "/{camera_id}/snapshot",
    summary="Chụp một frame JPEG (với AI overlay)",
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def snapshot_camera(camera_id: str, overlay: bool = True):
    """Trả về một ảnh JPEG đơn từ camera — dùng để preview thumbnail."""
    if not state.camera_manager:
        raise HTTPException(500, "Camera manager chưa khởi tạo")
    cam = state.camera_manager.get_camera(camera_id)
    if cam is None:
        raise HTTPException(404, f"Không tìm thấy camera: {camera_id}")

    frame = cam.get_latest_frame()
    if frame is None:
        raise HTTPException(503, "Chưa có frame từ camera")

    if overlay:
        frame = _draw_faces_on_frame(frame)

    try:
        jpg = _encode_frame_jpeg(frame, quality=85)
    except Exception as e:
        raise HTTPException(500, f"Encode lỗi: {e}")

    return Response(content=jpg, media_type="image/jpeg")


@router.post("/test", summary="Kiểm tra kết nối camera")
async def test_camera(
    request: TestCameraRequest,
    _: dict = Depends(require_teacher),
):
    """
    Kiểm tra kết nối URL camera (timeout 20s cho RTSP/TCP).
    RTSP dùng TCP transport qua OPENCV_FFMPEG_CAPTURE_OPTIONS.
    URL được validate trước khi thực hiện kết nối.
    """
    url = request.url
    _validate_camera_url(url)

    result: dict = {"success": False, "message": "", "resolution": ""}

    def _test() -> None:
        import os
        # Đảm bảo TCP transport được set (cùng logic với camera_manager.py)
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            "rtsp_transport;tcp|timeout;15000000|stimeout;15000000",
        )
        try:
            if isinstance(url, str) and url.isdigit():
                cap = cv2.VideoCapture(int(url), cv2.CAP_DSHOW)
            elif isinstance(url, str) and url.startswith("rtsp://"):
                # RTSP/TCP — digest auth handled by FFmpeg
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 15000)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
            else:
                cap = cv2.VideoCapture(url)

            if not cap.isOpened():
                result["message"] = (
                    "Không thể mở nguồn video. "
                    "Kiểm tra: IP/port đúng chưa, RTSP đã bật trên camera chưa, "
                    "username/password có đúng không?"
                )
                return

            ret, frame = cap.read()
            cap.release()

            if ret and frame is not None:
                result["success"] = True
                h, w = frame.shape[:2]
                result["resolution"] = f"{w}x{h}"
                result["message"] = f"Kết nối thành công! Độ phân giải: {w}x{h}"
            else:
                result["message"] = (
                    "Kết nối được nhưng không đọc được frame. "
                    "Thử channel 102 (sub-stream) thay vì 101."
                )

        except Exception as e:
            logger.warning(f"[Camera Test] {url}: {e}")
            result["message"] = f"Lỗi kết nối: {e}"

    t = threading.Thread(target=_test, daemon=True)
    t.start()
    t.join(timeout=20)  # 20s cho RTSP/TCP

    if t.is_alive():
        result["message"] = (
            "Hết thời gian chờ (20s). "
            "Camera không phản hồi — kiểm tra RTSP đã được bật và Save trên camera chưa."
        )

    return result
