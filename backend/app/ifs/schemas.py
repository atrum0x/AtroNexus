from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, HttpUrl, model_validator

AuthType = Literal["oauth2", "basic"]


class IfsConnectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: HttpUrl
    auth_type: AuthType = "oauth2"
    token_url: HttpUrl | None = None
    client_id: str | None = Field(default=None, max_length=200)
    username: str | None = Field(default=None, max_length=200)
    # Client secret or password. Required when creating. On update, leave it
    # empty to keep the saved one.
    secret: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_auth_fields(self) -> Self:
        if self.auth_type == "oauth2" and (not self.token_url or not self.client_id):
            raise ValueError("OAuth2 needs a token URL and a client ID.")
        if self.auth_type == "basic" and not self.username:
            raise ValueError("Basic auth needs a username.")
        return self


class IfsConnectionOut(BaseModel):
    id: int
    name: str
    base_url: str
    auth_type: AuthType
    token_url: str | None
    client_id: str | None
    username: str | None
    created_at: datetime
    updated_at: datetime


class CheckResult(BaseModel):
    ok: bool
    message: str
