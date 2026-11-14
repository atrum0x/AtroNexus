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

    # Lets IFS connections point at localhost and private networks, for local
    # development against a fake IFS. Off in production: customers type these
    # addresses, and internal ones would let them reach our network (SSRF).
    allow_private_ifs_urls: bool = False

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
    # Given to that admin user on startup if they have no email yet, so they
    # can sign in with it and receive password resets.
    admin_email: str | None = None

    # The frontend's public address. Links in emails (verify, reset password)
    # point here.
    app_url: str = "http://localhost:3000"

    # "console" writes emails to the log (local development, or until a sending
    # domain is set up). "resend" sends them through Resend (resend.com).
    email_backend: str = "console"
    resend_api_key: str | None = None
    # Must be an address on a domain verified in Resend.
    email_from: str = "AtroNexus <no-reply@example.com>"

    # WhatsApp (Meta's WhatsApp Cloud API), for the messaging hub. For now one
    # shared AtroNexus number sends for every organization; customers' own
    # numbers come later. While unset, messages and templates can't be sent.
    whatsapp_business_account_id: str | None = None  # WABA ID: templates live here
    whatsapp_phone_number_id: str | None = None  # the sending number's ID (not the number)
    whatsapp_access_token: str | None = None  # a system user token with whatsapp_business_messaging/management
    whatsapp_display_number: str | None = None  # shown to customers, e.g. "+94 77 123 4567"
    # From the Meta app: signs webhook calls (X-Hub-Signature-256).
    meta_app_secret: str | None = None
    # Any string; typed into the Meta app's webhook settings, which echo it back once to verify.
    meta_webhook_verify_token: str | None = None
    meta_graph_url: str = "https://graph.facebook.com/v23.0"

    @field_validator(
        "admin_email",
        "resend_api_key",
        "whatsapp_business_account_id",
        "whatsapp_phone_number_id",
        "whatsapp_access_token",
        "whatsapp_display_number",
        "meta_app_secret",
        "meta_webhook_verify_token",
        mode="before",
    )
    @classmethod
    def empty_is_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
