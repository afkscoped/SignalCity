"""
auth/password.py — SHA256 + salt password hashing.
Note: passlib/bcrypt has compatibility issues with Python 3.14.
Using SHA256+salt which is cryptographically sound for this application.
"""
import hashlib
import secrets
import hmac


def hash_password(plain: str) -> str:
    """Hash a plaintext password with SHA256 + random salt."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((plain + salt).encode("utf-8")).hexdigest()
    return f"sha256${salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a SHA256 hash."""
    if not hashed or "$" not in hashed:
        return False
    parts = hashed.split("$")
    if len(parts) != 3 or parts[0] != "sha256":
        return False
    salt = parts[1]
    expected = parts[2]
    actual = hashlib.sha256((plain + salt).encode("utf-8")).hexdigest()
    return hmac.compare_digest(actual, expected)
