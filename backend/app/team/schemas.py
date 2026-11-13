from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas import Password

Role = Literal["owner", "admin", "member"]


class MemberOut(BaseModel):
    id: int
    name: str | None
    email: str | None
    username: str | None
    role: Role
    is_me: bool
    created_at: datetime


class RoleChange(BaseModel):
    role: Role


class InvitationIn(BaseModel):
    email: EmailStr = Field(max_length=254)
    role: Role = "member"


class InvitationOut(BaseModel):
    id: int
    email: str
    role: Role
    invited_by: str | None
    created_at: datetime
    expires_at: datetime


class InvitationInfo(BaseModel):
    """What the invite page shows before someone accepts."""

    organization_name: str
    email: str
    role: Role
    invited_by: str | None


class AcceptInvitation(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Password
