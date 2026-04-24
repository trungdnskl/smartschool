"""
state.py — Centralized application state (replaces scattered global variables).

Lý do tách ra:
  - Routers cần access state nhưng không nên import main.py
  - Tránh circular imports
  - Dễ test: inject mock state

Tối ưu v2:
  - Concurrent WebSocket broadcast (asyncio.gather thay vì sequential loop)
  - asyncio.Lock bảo vệ mutable state
  - Temporal smoothing cho engagement metrics
"""
import asyncio
import collections
import io
import json
import logging
import pickle
import time
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class TemporalSmoother:
    """
    Moving average smoother cho engagement metrics.
    Giảm nhảy số liên tục trên UI bằng cách lấy trung bình N mẫu gần nhất.
    """

    def __init__(self, window_size: int = 5):
        self._window_size = window_size
        self._buffers: Dict[str, collections.deque] = {}

    def smooth(self, key: str, value: float) -> float:
        """Thêm giá trị mới và trả về moving average."""
        if key not in self._buffers:
            self._buffers[key] = collections.deque(maxlen=self._window_size)
        self._buffers[key].append(value)
        return sum(self._buffers[key]) / len(self._buffers[key])

    def smooth_dict(self, data: Dict[str, float]) -> Dict[str, float]:
        """Smooth tất cả giá trị trong dict."""
        return {k: self.smooth(k, v) for k, v in data.items()}

    def reset(self):
        """Reset tất cả buffers."""
        self._buffers.clear()


class AppState:
    """
    Singleton app state.
    Tất cả global variables trước đây trong main.py đều chuyển vào đây.

    Fix S1: Mutable attributes được khởi tạo trong __init__ thay vì class-level
            để tránh shared state giữa các instances (quan trọng khi test).
    """

    def __init__(self):
        self.config: Optional[Any] = None           # AppConfig
        self.camera_manager: Optional[Any] = None   # CameraManager
        self.detector: Optional[Any] = None         # ClassroomDetector

        # WebSocket clients — instance-level (fix S1)
        self.websocket_connections: Set[Any] = set()
        self._ws_lock: Optional[asyncio.Lock] = None  # Protects WS set

        # Session state — protected by session_lock
        self.active_session_id: Optional[int] = None
        self.latest_snapshot: Optional[Dict[str, Any]] = None

        # Temporal smoother for engagement metrics (tối ưu #6)
        self.smoother = TemporalSmoother(window_size=5)

        # Async primitives — initialized in init()
        self._session_lock: Optional[asyncio.Lock] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Performance metrics
        self._broadcast_count: int = 0
        self._broadcast_errors: int = 0

    @property
    def session_lock(self) -> asyncio.Lock:
        """
        Fix S2: Safe accessor — raises clear error nếu init() chưa được gọi.
        """
        if self._session_lock is None:
            raise RuntimeError(
                "[State] session_lock chưa khởi tạo. "
                "Gọi state.init() trong lifespan startup trước."
            )
        return self._session_lock

    def init(self) -> None:
        """
        Initialize async primitives.
        MUST be called from inside async context (lifespan startup).
        """
        self._session_lock = asyncio.Lock()
        self._ws_lock = asyncio.Lock()
        self._event_loop = asyncio.get_event_loop()
        logger.debug("[State] Async primitives initialized")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast JSON message to all connected WebSocket clients.
        Tối ưu: dùng asyncio.gather cho concurrent sends + lock bảo vệ set.
        Dead connections are pruned automatically.
        """
        if not self.websocket_connections:
            return

        msg_text = json.dumps(message, ensure_ascii=False, default=str)
        self._broadcast_count += 1

        # Snapshot current connections (thread-safe copy)
        if self._ws_lock:
            async with self._ws_lock:
                clients = list(self.websocket_connections)
        else:
            clients = list(self.websocket_connections)

        if not clients:
            return

        # Concurrent send to all clients
        async def _safe_send(ws):
            try:
                await ws.send_text(msg_text)
                return None  # success
            except Exception:
                return ws  # failed — mark for removal

        results = await asyncio.gather(*[_safe_send(ws) for ws in clients])
        dead = {ws for ws in results if ws is not None}

        if dead:
            if self._ws_lock:
                async with self._ws_lock:
                    self.websocket_connections -= dead
            else:
                self.websocket_connections -= dead
            self._broadcast_errors += len(dead)
            logger.debug(f"[State] Pruned {len(dead)} dead WebSocket connections")

    def get_broadcast_stats(self) -> Dict[str, int]:
        """Get broadcast performance metrics."""
        return {
            "total_broadcasts": self._broadcast_count,
            "total_errors": self._broadcast_errors,
            "active_connections": len(self.websocket_connections),
        }


# Module-level singleton — import this everywhere
state = AppState()


# ── Safe Pickle Deserializer ─────────────────────────────────────────────────
class _SafeUnpickler(pickle.Unpickler):
    """
    Sandbox cho pickle.loads() — chỉ cho phép numpy/builtin types.
    Ngăn RCE khi user upload file .pkl độc hại.
    """
    _ALLOWED: Set[tuple] = {
        ("numpy", "ndarray"),
        ("numpy.core.multiarray", "_reconstruct"),
        ("numpy.core.multiarray", "scalar"),
        ("numpy", "dtype"),
        ("numpy", "float32"), ("numpy", "float64"),
        ("numpy", "int32"),   ("numpy", "int64"),
        ("builtins", "dict"),  ("builtins", "list"),
        ("builtins", "str"),   ("builtins", "int"),
        ("builtins", "float"), ("builtins", "bool"),
        ("builtins", "bytes"), ("builtins", "set"),
        ("builtins", "tuple"),
    }

    def find_class(self, module: str, name: str):
        if (module, name) in self._ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"[Security] Blocked unsafe class: {module}.{name}"
        )


def safe_pickle_loads(data: bytes) -> Any:
    """Safe alternative to pickle.loads() — only allows numpy/builtin types."""
    return _SafeUnpickler(io.BytesIO(data)).load()
