"""
auth/middleware.py — FastAPI dependency for JWT-protected endpoints.
"""
from fastapi import Header, HTTPException
from .jwt_handler import verify_token


async def get_current_user(authorization: str = Header(default="")) -> dict:
    """
    Extract and verify JWT from the Authorization header.
    Returns decoded payload with 'sub' (user_id) and 'username'.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split("Bearer ", 1)[1].strip()
    try:
        payload = verify_token(token)
        return payload
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


async def get_current_user_optional(authorization: str = Header(default="")) -> dict | None:
    if not authorization.startswith("Bearer "):
        return None
    try:
        return verify_token(authorization.split("Bearer ", 1)[1].strip())
    except ValueError:
        return None
