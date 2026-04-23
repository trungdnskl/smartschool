"""
api/routes/auth.py — Authentication endpoints.

POST /api/auth/login     → JWT token
POST /api/auth/logout    → (stateless — client discards token)
POST /api/auth/change-password
GET  /api/auth/me        → current user info
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from api.deps import require_teacher, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ── Pydantic models ──────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    expires_in: int  # seconds


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


# ── Endpoints ────────────────────────────────────────
@router.post("/login", response_model=TokenResponse, summary="Đăng nhập")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Đăng nhập bằng username/password.
    Trả về JWT Bearer token (mặc định hết hạn sau 8 giờ).
    """
    from database import get_user_by_username
    from core.security import (
        verify_password,
        create_access_token,
        ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    user = await get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        logger.warning(f"[Auth] Failed login for username='{form_data.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa. Liên hệ quản trị viên.",
        )

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "user_id": user["id"],
        "teacher_id": user.get("teacher_id"),
    })

    logger.info(f"[Auth] Login OK — user='{user['username']}' role={user['role']}")
    return TokenResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", summary="Đăng xuất")
async def logout():
    """
    Đăng xuất (stateless — client tự xóa token).
    Server không lưu blacklist token trong MVP.
    """
    return {"status": "ok", "message": "Đã đăng xuất. Vui lòng xóa token ở client."}


@router.get("/me", summary="Thông tin người dùng hiện tại")
async def get_me(user: dict = Depends(require_teacher)):
    """Trả về thông tin user đang đăng nhập."""
    return {
        "username": user.get("sub"),
        "role": user.get("role"),
        "user_id": user.get("user_id"),
        "teacher_id": user.get("teacher_id"),
    }


@router.post("/change-password", summary="Đổi mật khẩu")
async def change_password(
    request: ChangePasswordRequest,
    user: dict = Depends(require_teacher),
):
    """Đổi mật khẩu tài khoản hiện tại."""
    from database import get_user_by_username, update_user_password
    from core.security import verify_password, hash_password

    db_user = await get_user_by_username(user["sub"])
    if not db_user:
        raise HTTPException(404, "Không tìm thấy tài khoản")

    if not verify_password(request.current_password, db_user["hashed_password"]):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")

    await update_user_password(db_user["id"], hash_password(request.new_password))
    logger.info(f"[Auth] Password changed for user='{user['sub']}'")
    return {"status": "ok", "message": "Đổi mật khẩu thành công"}


# ── User Management (admin only) ─────────────────────

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role: str = Field("teacher", pattern="^(admin|teacher)$")
    teacher_id: Optional[int] = None


@router.get("/users", summary="Danh sách người dùng (admin)")
async def list_users(admin: dict = Depends(require_admin)):
    """Lấy danh sách tài khoản — chỉ admin."""
    from database import list_users as _list_users
    users = await _list_users()
    return {"users": users, "total": len(users)}


@router.post("/users", summary="Tạo tài khoản mới (admin)")
async def create_user(
    request: CreateUserRequest,
    admin: dict = Depends(require_admin),
):
    """Tạo tài khoản người dùng mới — chỉ admin."""
    from database import get_user_by_username, create_user as _create_user
    from core.security import hash_password

    existing = await get_user_by_username(request.username)
    if existing:
        raise HTTPException(409, f"Tên đăng nhập '{request.username}' đã tồn tại")

    hashed = hash_password(request.password)
    user_id = await _create_user(
        username=request.username,
        hashed_password=hashed,
        role=request.role,
        teacher_id=request.teacher_id,
    )
    logger.info(f"[Auth] User created: {request.username} role={request.role} by admin={admin['sub']}")
    return {
        "status": "ok",
        "user_id": user_id,
        "username": request.username,
        "role": request.role,
        "message": f"Đã tạo tài khoản {request.username}",
    }


@router.delete("/users/{user_id}", summary="Vô hiệu hóa tài khoản (admin)")
async def deactivate_user(
    user_id: int,
    admin: dict = Depends(require_admin),
):
    """Vô hiệu hóa tài khoản — chỉ admin. Không hard-delete để giữ audit trail."""
    from database import deactivate_user as _deactivate

    if user_id == admin.get("user_id"):
        raise HTTPException(400, "Không thể vô hiệu hóa tài khoản đang đăng nhập")

    await _deactivate(user_id)
    logger.info(f"[Auth] User {user_id} deactivated by admin={admin['sub']}")
    return {"status": "ok", "message": f"Đã vô hiệu hóa tài khoản #{user_id}"}
