import logging
import os
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

logger = logging.getLogger(__name__)

# --- Configuration ---
# AUTH_ENABLED: Set to "true" to enforce JWT across all protected endpoints.
AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,
)

# Anonymous user for when AUTH_ENABLED=false
_ANON_ADMIN = {
    "sub": "anonymous_admin",
    "role": "admin",
    "user_id": 0,
    "teacher_id": None,
    "scopes": ["admin", "teacher"]
}


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """
    Decodes and validates JWT token. 
    Returns the user payload (claims).
    """
    if not AUTH_ENABLED:
        return _ANON_ADMIN

    if not token:
        logger.warning("Authentication failed: No token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bạn cần đăng nhập để thực hiện thao tác này",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        from core.security import decode_token
        payload = decode_token(token)
        
        # Validate payload structure
        if not payload.get("sub"):
            raise JWTError("Missing 'sub' claim")
            
        return payload
    except JWTError as e:
        logger.error(f"Authentication failed: Invalid token - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc đã hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_role(allowed_roles: list, user: dict):
    """Internal helper to check roles."""
    if user.get("role") not in allowed_roles:
        logger.warning(f"Access denied: User '{user.get('sub')}' (role={user.get('role')}) attempted restricted action")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tài khoản của bạn không có quyền thực hiện hành động này (Yêu cầu: {', '.join(allowed_roles)})",
        )
    return user


async def require_teacher(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: Require at least Teacher or Admin role."""
    return await require_role(["teacher", "admin"], user)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: Require Admin role."""
    return await require_role(["admin"], user)


async def optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[dict]:
    """
    Returns user payload if valid token is provided, otherwise returns None.
    Useful for endpoints that show more data to logged-in users but are public.
    """
    if not token:
        return None
    try:
        from core.security import decode_token
        return decode_token(token)
    except JWTError:
        return None
