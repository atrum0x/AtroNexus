from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import SUSPENDED_MESSAGE, CurrentUser, DbSession
from app.models import ORG_ACTIVE, User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == body.username))
    valid = verify_password(body.password, user.password_hash if user else None)
    if not valid or user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if user.organization.status != ORG_ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, SUSPENDED_MESSAGE)
    token, expires_in = create_access_token(user.username)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser) -> User:
    return user
