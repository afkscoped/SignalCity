"""
auth/jwt_handler.py — JWT token creation and verification.
"""
import os
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from jose import jwt, JWTError
except ModuleNotFoundError:
    jwt = None

    class JWTError(Exception):
        pass

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET", "signal-city-dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 48


def create_token(user_id: str, username: str) -> str:
    """Create a JWT token for authenticated user."""
    payload = {
        "sub": user_id,
        "username": username,
        "exp": int((datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)).timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    }
    if jwt:
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return _encode_fallback(payload)


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token. Returns payload or raises."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) if jwt else _decode_fallback(token)
        if payload.get("exp", 0) < int(datetime.utcnow().timestamp()):
            raise JWTError("Token expired")
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired token: {e}")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _encode_fallback(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join([
        _b64(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ])
    sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(sig)}"


def _decode_fallback(token: str) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise JWTError("Malformed token") from exc
    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(SECRET_KEY.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64(expected), sig_b64):
        raise JWTError("Bad signature")
    return json.loads(_unb64(payload_b64))
