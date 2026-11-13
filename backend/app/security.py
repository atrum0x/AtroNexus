import hashlib
import secrets
from dataclasses import dataclass
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


@dataclass(frozen=True)
class AccessToken:
    user_id: int
    issued_at: datetime


def create_access_token(user_id: int) -> tuple[str, int]:
    """The subject is the user's ID (emails and usernames can change)."""
    settings = get_settings()
    expires_in = settings.jwt_exp_minutes * 60
    now = datetime.now(timezone.utc)
    # iat with sub-second precision, so a session started just before a
    # password reset (same second) still counts as older than the reset.
    payload = {"sub": str(user_id), "iat": now.timestamp(), "exp": now + timedelta(seconds=expires_in)}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> AccessToken | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat"]},
        )
        return AccessToken(
            user_id=int(payload["sub"]),
            issued_at=datetime.fromtimestamp(payload["iat"], timezone.utc),
        )
    except (jwt.PyJWTError, ValueError):
        # ValueError: a token from before IDs were the subject ("admin").
        return None


def new_link_token() -> tuple[str, str]:
    """A one-time token for an email link: (token for the link, hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_link_token(token)


def hash_link_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
