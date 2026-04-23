"""
state.py — Centralized application state (replaces scattered global variables).

Lý do tách ra:
  - Routers cần access state nhưng không nên import main.py
  - Tránh circular imports
  - Dễ test: inject mock state
"""
import asyncio
import io
import json
import logging
import pickle
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


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

        # Session state — protected by session_lock
        self.active_session_id: Optional[int] = None
        self.latest_snapshot: Optional[Dict[str, Any]] = None

        # Async primitives — initialized in init()
        self._session_lock: Optional[asyncio.Lock] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

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
        self._event_loop = asyncio.get_event_loop()
        logger.debug("[State] Async primitives initialized")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast JSON message to all connected WebSocket clients.
        Dead connections are pruned automatically.
        """
        if not self.websocket_connections:
            return

        msg_text = json.dumps(message, ensure_ascii=False, default=str)
        dead: Set[Any] = set()

        for ws in self.websocket_connections:
            try:
                await ws.send_text(msg_text)
            except Exception:
                dead.add(ws)

        self.websocket_connections -= dead
        if dead:
            logger.debug(f"[State] Pruned {len(dead)} dead WebSocket connections")


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
