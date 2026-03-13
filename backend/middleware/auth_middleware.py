"""Authentication middleware — JWT token validation for protected routes.

Provides a FastAPI dependency `get_current_user` that extracts and validates
the Bearer token from the Authorization header.

For demo purposes, this is a simple JWT check against hardcoded users.
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from routers.auth import decode_token, DEMO_USERS

logger = logging.getLogger(__name__)

# HTTPBearer extracts the token from "Authorization: Bearer <token>"
# auto_error=False means it returns None instead of 403 if header is missing
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ] = None,
) -> dict:
    """Validate JWT and return the user dict.

    Returns:
        dict with keys: email, name, role

    Raises:
        HTTPException 401 if token is missing, invalid, or expired
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required."},
        )

    payload = decode_token(credentials.credentials)
    email = payload.get("sub")

    if not email:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid session. Please sign in again."},
        )

    user = DEMO_USERS.get(email)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "User not found. Please sign in again."},
        )

    return {
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
    }


async def require_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require admin role for an endpoint."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail={"error": "Access restricted to administrators."},
        )
    return current_user
