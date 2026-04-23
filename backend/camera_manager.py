"""
Classroom Engagement System - Camera Manager
Quản lý kết nối RTSP đến camera IP trong lớp học
Tái sử dụng và tối ưu từ ANPR Camera Manager
"""

import cv2
import os
import time
import threading
import queue
import logging
from typing import Dict, Optional, Callable, Any
from datetime import datetime
from config import CameraConfig

logger = logging.getLogger(__name__)

# Force RTSP over TCP for Hikvision/Dahua cameras (fixes digest auth + stability)
# Must be set BEFORE cv2.VideoCapture() is called
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|"
    "timeout;10000000|"
    "stimeout;10000000"
)


def _encode_rtsp_url(url: str) -> str:
    """
    Auto URL-encode username/password in RTSP URLs.
    VLC handles special chars (!, %, @, #) automatically but FFmpeg does not.
    Transforms: rtsp://user:P@ss!%@IP:554/path
    Into:       rtsp://user:P%40ss%21%25@IP:554/path
    """
    if not url or not url.startswith("rtsp://"):
        return url
    try:
        from urllib.parse import quote, urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.password:
            # Re-encode password (safe='' encodes everything)
            encoded_pw = quote(parsed.password, safe='')
            encoded_user = quote(parsed.username or '', safe='')
            # Rebuild netloc
            netloc = f"{encoded_user}:{encoded_pw}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            new = parsed._replace(netloc=netloc)
            return urlunparse(new)
    except Exception:
        pass
    return url


class CameraStream:
    """Quản lý một luồng RTSP từ camera IP lớp học."""

    def __init__(
        self,
        config: CameraConfig,
        on_frame: Optional[Callable] = None,
        frame_skip: int = 3,
    ):
        self.config = config
        self.camera_id = config.id
        self.name = config.name
        self.url = config.url
        self.on_frame = on_frame
        self.frame_skip = frame_skip

        self._capture: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._frame_queue: queue.Queue = queue.Queue(maxsize=5)

        # Statistics
        self.frame_count = 0
        self.last_frame_time: Optional[str] = None
        self.status = "stopped"  # running, stopped, error, disconnected
        self.error_message: Optional[str] = None
        self.fps: float = 0.0
        self._fps_counter = 0
        self._fps_timer = time.time()

        # Reconnect settings
        self._reconnect_delay = 5
        self._max_reconnect_attempts = 50

    def start(self):
        """Start camera stream capture in a background thread."""
        if self._running:
            logger.warning(f"[Camera {self.camera_id}] Already running")
            return

        self._running = True
        self.status = "running"
        self.error_message = None
        # Reset capture so reconnect loop starts fresh
        if self._capture and self._capture.isOpened():
            self._capture.release()
        self._capture = None
        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name=f"classroom-cam-{self.camera_id}",
        )
        self._thread.start()
        logger.info(f"[Camera {self.camera_id}] Started: {self.name}")

    def stop(self):
        """Stop camera stream capture."""
        self._running = False
        self.status = "stopped"
        if self._capture and self._capture.isOpened():
            self._capture.release()
            self._capture = None
        logger.info(f"[Camera {self.camera_id}] Stopped: {self.name}")

    def _connect(self) -> bool:
        """
        Connect to video source.
        Supports:
        - Webcam USB: url = "0", "1", "2" (integer index)
        - Video file: url = "path/to/video.mp4"
        - RTSP stream: url = "rtsp://..." (Hikvision, Dahua, v.v.)
        - HTTP MJPEG: url = "http://..."

        RTSP dùng TCP transport + digest auth qua OPENCV_FFMPEG_CAPTURE_OPTIONS.
        """
        try:
            source = self.url.strip() if isinstance(self.url, str) else self.url
            source_type = "RTSP"

            # Detect source type
            if isinstance(source, str) and source.isdigit():
                # Webcam USB
                source = int(source)
                source_type = "Webcam USB"
                logger.info(f"[Camera {self.camera_id}] Connecting to Webcam #{source}")
                self._capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)

            elif isinstance(source, str) and source.startswith("rtsp://"):
                # Camera IP RTSP — TCP transport + digest auth
                source_type = "Camera IP (RTSP/TCP)"
                # Auto URL-encode special chars in password (!, %, @, #)
                source = _encode_rtsp_url(source)
                masked = source.replace(source.split('@')[0].split('//')[1], '***') if '@' in source else source
                logger.info(f"[Camera {self.camera_id}] Connecting to {masked}")

                # CAP_FFMPEG picks up OPENCV_FFMPEG_CAPTURE_OPTIONS env var
                self._capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                # Shorter per-frame timeouts (env var handles connect timeout)
                self._capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 15000)
                self._capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)

            elif isinstance(source, str) and (source.startswith("http://") or source.startswith("https://")):
                # HTTP MJPEG stream
                source_type = "HTTP Stream"
                logger.info(f"[Camera {self.camera_id}] Connecting to {source}")
                self._capture = cv2.VideoCapture(source)

            else:
                # Video file hoặc nguồn khác
                source_type = "Video file"
                logger.info(f"[Camera {self.camera_id}] Opening video: {source}")
                self._capture = cv2.VideoCapture(source)

            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not self._capture.isOpened():
                raise ConnectionError(
                    f"Cannot open {source_type}: {self.url} — "
                    f"Kiểm tra: IP đúng chưa, RTSP đã bật chưa, username/password có đúng không?"
                )

            ret, frame = self._capture.read()
            if not ret or frame is None:
                raise ConnectionError(
                    f"Kết nối được nhưng không đọc được frame từ {source_type}. "
                    f"Thử channel khác (101→102) hoặc kiểm tra encoding."
                )

            logger.info(
                f"[Camera {self.camera_id}] Connected! "
                f"Type: {source_type} | "
                f"Resolution: {frame.shape[1]}x{frame.shape[0]}"
            )
            self.status = "running"
            self.error_message = None
            return True

        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            logger.error(f"[Camera {self.camera_id}] Connection failed: {e}")
            if self._capture:
                self._capture.release()
                self._capture = None
            return False

    def _capture_loop(self):
        """Main loop for capturing frames from RTSP stream."""
        reconnect_attempts = 0
        frame_index = 0

        while self._running:
            if self._capture is None or not self._capture.isOpened():
                if reconnect_attempts >= self._max_reconnect_attempts:
                    self.status = "disconnected"
                    self.error_message = f"Max reconnect attempts reached"
                    logger.error(f"[Camera {self.camera_id}] {self.error_message}")
                    break

                reconnect_attempts += 1
                logger.info(
                    f"[Camera {self.camera_id}] Reconnect {reconnect_attempts}/{self._max_reconnect_attempts}"
                )

                if not self._connect():
                    time.sleep(self._reconnect_delay)
                    continue

                reconnect_attempts = 0

            try:
                ret, frame = self._capture.read()

                if not ret or frame is None:
                    logger.warning(f"[Camera {self.camera_id}] Frame read failed")
                    if self._capture:
                        self._capture.release()
                        self._capture = None
                    time.sleep(1)
                    continue

                frame_index += 1
                self.frame_count += 1
                self.last_frame_time = datetime.now().strftime("%H:%M:%S")

                # FPS calculation
                self._fps_counter += 1
                elapsed = time.time() - self._fps_timer
                if elapsed >= 2.0:
                    self.fps = round(self._fps_counter / elapsed, 1)
                    self._fps_counter = 0
                    self._fps_timer = time.time()

                # Skip frames for performance (CPU optimization)
                if frame_index % self.frame_skip != 0:
                    continue

                # Process frame via callback
                if self.on_frame:
                    try:
                        self.on_frame(self.camera_id, self.name, frame)
                    except Exception as e:
                        logger.error(f"[Camera {self.camera_id}] Processing error: {e}")

                # Queue latest frame
                if not self._frame_queue.full():
                    self._frame_queue.put_nowait(frame)
                else:
                    # Drop oldest frame
                    try:
                        self._frame_queue.get_nowait()
                        self._frame_queue.put_nowait(frame)
                    except queue.Empty:
                        pass

            except Exception as e:
                logger.error(f"[Camera {self.camera_id}] Capture error: {e}")
                self.status = "error"
                self.error_message = str(e)
                if self._capture:
                    self._capture.release()
                    self._capture = None
                time.sleep(2)

        # Cleanup
        if self._capture and self._capture.isOpened():
            self._capture.release()
        self._capture = None

    def get_latest_frame(self) -> Optional[Any]:
        """Get the latest captured frame."""
        try:
            return self._frame_queue.get_nowait()
        except queue.Empty:
            return None

    def get_info(self) -> Dict:
        """Get camera information."""
        return {
            "id": self.camera_id,
            "name": self.name,
            "url": self.url,
            "enabled": self.config.enabled,
            "status": self.status,
            "frame_count": self.frame_count,
            "last_frame_time": self.last_frame_time,
            "fps": self.fps,
            "error_message": self.error_message,
        }


class CameraManager:
    """Quản lý nhiều camera lớp học cùng lúc."""

    def __init__(
        self,
        on_frame: Optional[Callable] = None,
        frame_skip: int = 3,
    ):
        self.cameras: Dict[str, CameraStream] = {}
        self.on_frame = on_frame
        self.frame_skip = frame_skip

    def add_camera(self, config: CameraConfig) -> CameraStream:
        """Add a new camera."""
        if config.id in self.cameras:
            logger.warning(f"Camera {config.id} exists, replacing")
            self.cameras[config.id].stop()

        stream = CameraStream(
            config=config,
            on_frame=self.on_frame,
            frame_skip=self.frame_skip,
        )
        self.cameras[config.id] = stream
        logger.info(f"[CameraManager] Added: {config.id} ({config.name})")
        return stream

    def remove_camera(self, camera_id: str):
        if camera_id in self.cameras:
            self.cameras[camera_id].stop()
            del self.cameras[camera_id]

    def start_camera(self, camera_id: str):
        if camera_id in self.cameras:
            self.cameras[camera_id].start()

    def stop_camera(self, camera_id: str):
        if camera_id in self.cameras:
            self.cameras[camera_id].stop()

    def start_all(self):
        for cam_id, stream in self.cameras.items():
            if stream.config.enabled:
                stream.start()
                time.sleep(0.5)

    def stop_all(self):
        for cam_id, stream in self.cameras.items():
            stream.stop()

    def get_camera(self, camera_id: str) -> Optional[CameraStream]:
        return self.cameras.get(camera_id)

    def get_all_info(self) -> list:
        return [stream.get_info() for stream in self.cameras.values()]

    def get_active_count(self) -> int:
        return sum(1 for s in self.cameras.values() if s.status == "running")
