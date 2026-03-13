"""Authentication endpoints — demo login with hardcoded users.

Endpoints:
    POST /api/auth/login  — validate credentials, return JWT + user
    GET  /api/auth/me     — return current user from token
    POST /api/auth/logout — client-side token removal (no-op server-side)
"""

import hashlib
import hmac
import logging
import os
import time
from typing import Literal

import jwt
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth")

# ---------------------------------------------------------------------------
# JWT Configuration
# ---------------------------------------------------------------------------

JWT_SECRET = os.getenv("JWT_SECRET", "beacon-gom-demo-secret-2026-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours


# ---------------------------------------------------------------------------
# Demo Users — hardcoded, no database needed
# ---------------------------------------------------------------------------

DEMO_USERS: dict[str, dict] = {
    "admin@beacongom.ai": {
        "email": "admin@beacongom.ai",
        "password_hash": hashlib.sha256(b"BeaconDemo2026!").hexdigest(),
        "name": "Admin User",
        "role": "admin",
    },
    "demo@beacongom.ai": {
        "email": "demo@beacongom.ai",
        "password_hash": hashlib.sha256(b"GoMSafety2026!").hexdigest(),
        "name": "Demo User",
        "role": "viewer",
    },
}


def _verify_password(plain: str, stored_hash: str) -> bool:
    """Constant-time comparison of password hash."""
    candidate = hashlib.sha256(plain.encode()).hexdigest()
    return hmac.compare_digest(candidate, stored_hash)


def _create_token(email: str, role: str) -> str:
    """Create a JWT token with email and role claims."""
    payload = {
        "sub": email,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises on invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"error": "Session expired. Please sign in again."})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={"error": "Invalid session. Please sign in again."})


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class UserResponse(BaseModel):
    email: str
    name: str
    role: Literal["admin", "viewer"]


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(req: LoginRequest):
    """Authenticate with email + password, return JWT token."""
    user = DEMO_USERS.get(req.email.lower())

    if not user or not _verify_password(req.password, user["password_hash"]):
        logger.warning("Failed login attempt for: %s", req.email[:50])
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid email or password."},
        )

    token = _create_token(user["email"], user["role"])

    logger.info("Successful login: %s (%s)", user["email"], user["role"])

    return {
        "data": {
            "token": token,
            "user": {
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }
    }


@router.get("/me")
async def get_current_user_info(request: Request):
    """Return the current authenticated user from their JWT token."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required."},
        )

    token = auth_header.split("Bearer ", 1)[1]
    payload = decode_token(token)
    email = payload.get("sub")

    user = DEMO_USERS.get(email)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "User not found. Please sign in again."},
        )

    return {
        "data": {
            "user": {
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }
    }


@router.post("/logout")
async def logout():
    """Logout — client removes token. Server-side is a no-op for demo."""
    return {"data": {"message": "Signed out successfully."}}
