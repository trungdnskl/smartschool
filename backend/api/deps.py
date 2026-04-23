"""
api/deps.py — FastAPI shared dependencies.

AUTH_ENABLED (env): set "true" để bật JWT auth trên tất cả write endpoints.
  - false (default): backward-compatible, mọi endpoint hoạt động không cần token
  - true: phải đăng nhập, token trả về từ POST /api/auth/login

Roles:
  - admin  : toàn quyền (thêm/xóa GV, camera, quản lý user)
  - teacher: quản lý học sinh, session, điểm danh
"""
import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

logger = logging.getLogger(__name__)

AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,  # không raise 401 tự động — để deps xử lý
)

_ANON_ADMIN = {"sub": "anonymous", "role": "admin", "user_id": 0}


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> dict:
    """
    Decode JWT và trả về user payload.
    Nếu AUTH_ENABLED=false: luôn trả về anonymous admin (backward compat).
    """
    if not AUTH_ENABLED:
        return _ANON_ADMIN

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần đăng nhập để thực hiện thao tác này",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        from core.security import decode_token
        return decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_teacher(user: dict = Depends(get_current_user)) -> dict:
    """Require teacher or admin role."""
    if user.get("role") not in ("teacher", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cần quyền giáo viên để thực hiện thao tác này",
        )
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cần quyền quản trị viên",
        )
    return user


async def optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[dict]:
    """Return user payload if token provided, else None (for read-only endpoints)."""
    if not token:
        return None
    try:
        from core.security import decode_token
        return decode_token(token)
    except JWTError:
        return None
