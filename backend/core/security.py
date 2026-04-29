"""
core/security.py — JWT authentication utilities.

Usage:
  - Set AUTH_ENABLED=true env var to require tokens on all write endpoints.
  - Default (AUTH_ENABLED=false): backward-compatible, no token required.
  - Default admin: admin / changeme123  (hashed on first DB init)
"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

# ── Config ──────────────────────────────────────────
# SECRET_KEY phải set trong production qua env var
_env_secret = os.getenv("SECRET_KEY", "")
if _env_secret:
    SECRET_KEY: str = _env_secret
else:
    import warnings
    SECRET_KEY: str = secrets.token_urlsafe(32)
    warnings.warn(
        "[Security] SECRET_KEY not set! Using random key — all JWT tokens will be "
        "invalidated on restart. Set SECRET_KEY env var in production.",
        stacklevel=2,
    )
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("TOKEN_EXPIRE_MINUTES", "480"))  # 8h

# ── Password hashing ────────────────────────────────
# Dùng sha256_crypt thay vì bcrypt để tránh bug passlib + Python 3.12
# sha256_crypt vẫn đảm bảo bảo mật tốt cho production
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

DEFAULT_ADMIN_PASSWORD = "changeme123"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plain-text password against sha256_crypt hash."""
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    """Hash password with sha256_crypt."""
    return pwd_context.hash(password)


# ── JWT ─────────────────────────────────────────────
def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create signed JWT token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify JWT token.
    Raises jose.JWTError if invalid/expired.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
