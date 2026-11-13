from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
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
    username = decode_access_token(credentials.credentials)
    if username is None:
        raise unauthorized
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
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
