from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ORG_ACTIVE, User
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]

SUSPENDED_MESSAGE = "This organization is suspended. Contact AtroNexus support."


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    token = decode_access_token(credentials.credentials)
    if token is None:
        raise unauthorized
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise unauthorized
    # A password reset ends every session that started before it.
    if user.password_changed_at and token.issued_at < user.password_changed_at:
        raise unauthorized
    if user.organization.status != ORG_ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, SUSPENDED_MESSAGE)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_org_id(user: CurrentUser) -> int:
    """The organization every admin request works in.

    Routers filter every query by it, and load single rows through a helper
    that answers 404 for another organization's rows (never 403, so IDs from
    other customers can't be probed).
    """
    return user.organization_id


OrgId = Annotated[int, Depends(get_current_org_id)]


def require_verified_email(user: CurrentUser) -> None:
    """For actions that reach outside AtroNexus (saving or testing IFS connections).

    A self-service account can sign in and look around right away, but must
    prove its email address before it can make the server call other systems.
    """
    if user.email_verified_at is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Verify your email address first. We sent you a link when you signed up."
        )


VerifiedEmail = Depends(require_verified_email)


MANAGER_ROLES = ("owner", "admin")


def require_manager(user: CurrentUser) -> None:
    """Owners and admins change settings; members can only look."""
    if user.role not in MANAGER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can do this.")


ManagerOnly = Depends(require_manager)
