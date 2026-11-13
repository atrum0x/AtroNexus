from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./atronexus.db"

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 60

    # Fernet key that encrypts stored IFS credentials. Generate with:
    # uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Changing it makes every saved secret unreadable.
    encryption_key: str = Field(min_length=44)

    # Seconds to wait for IFS before giving up on a write-back.
    ifs_timeout_seconds: float = 20.0

    # Shared secret between the frontend (Vercel) and this API. When set, every
    # request except /api/health must send it in X-Internal-Key, so only the
    # frontend can use the API. Leave unset for local development.
    internal_api_key: str | None = Field(default=None, min_length=32)

    @field_validator("internal_api_key", mode="before")
    @classmethod
    def empty_means_unset(cls, value: object) -> object:
        return None if value == "" else value

    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    # Created on startup if no user with this username exists.
    admin_username: str | None = None
    admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
