"""
JWT authentication for the Loan Default Risk API.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

APP_ENV = os.getenv("APP_ENV", "development").lower()
DEFAULT_DEV_SECRET = "change-me-in-production-use-a-long-random-secret"


def _load_secret_key() -> str:
    secret = os.getenv("SECRET_KEY", DEFAULT_DEV_SECRET)
    if APP_ENV in {"prod", "production"} and secret == DEFAULT_DEV_SECRET:
        raise RuntimeError("SECRET_KEY must be set in production environment")
    return secret


SECRET_KEY = _load_secret_key()
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer()

# ── Demo user store (replace with DB in production) ───────────────────────────
def _load_plain_users() -> dict[str, dict]:
    users: dict[str, dict] = {
        os.getenv("ADMIN_USERNAME", "admin"): {
            "plain_password": os.getenv("ADMIN_PASSWORD", "changeme"),
            "role": "admin",
        }
    }

    enable_demo_officer = os.getenv("ENABLE_DEMO_OFFICER_USER", "true").lower() == "true"
    if enable_demo_officer:
        users[os.getenv("OFFICER_USERNAME", "field_officer")] = {
            "plain_password": os.getenv("OFFICER_PASSWORD", "officer123"),
            "role": "officer",
        }

    return users


_PLAIN_USERS: dict[str, dict] = _load_plain_users()
_HASHED_USERS: dict[str, dict] = {}


def _get_hashed_users() -> dict[str, dict]:
    """Hash passwords once on first call."""
    global _HASHED_USERS
    if not _HASHED_USERS:
        _HASHED_USERS = {
            username: {
                "hashed_password": pwd_context.hash(info["plain_password"]),
                "role": info["role"],
            }
            for username, info in _PLAIN_USERS.items()
        }
    return _HASHED_USERS


class TokenData(BaseModel):
    username: str
    role: str


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> TokenData | None:
    user = _get_hashed_users().get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return TokenData(username=username, role=user["role"])


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenData:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        role: str = payload.get("role", "officer")
        if not username:
            raise credentials_exception
        return TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception


def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
