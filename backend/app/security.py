from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

password_hash = PasswordHash.recommended()

# Checked when the username doesn't exist, so a failed login takes about the
# same time whether or not the user is real.
_DUMMY_HASH = password_hash.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if hashed is None:
        password_hash.verify(password, _DUMMY_HASH)
        return False
    return password_hash.verify(password, hashed)


def create_access_token(subject: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.jwt_exp_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError:
        return None
    return payload["sub"]
