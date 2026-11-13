from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app import accounts
from app.deps import SUSPENDED_MESSAGE, CurrentUser, DbSession
from app.email.sender import send_email
from app.models import ORG_ACTIVE, RESET_PASSWORD, VERIFY_EMAIL, User
from app.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageOut,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID_LINK = "This link is invalid or has expired. Ask for a new one."


def _session(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    user = accounts.find_user_for_login(db, body.email)
    valid = verify_password(body.password, user.password_hash if user else None)
    if not valid or user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if user.organization.status != ORG_ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, SUSPENDED_MESSAGE)
    return _session(user)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: DbSession, background: BackgroundTasks) -> TokenResponse:
    """Creates an organization and its owner, sends the verification email, and signs in."""
    if accounts.email_taken(db, body.email):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists. Sign in instead."
        )
    user = accounts.sign_up(db, body.organization_name, body.name, body.email, body.password)
    token = accounts.create_link(db, user, VERIFY_EMAIL)
    db.commit()
    background.add_task(send_email, accounts.verify_email_message(user, token))
    return _session(user)


@router.post("/verify-email", response_model=MessageOut)
def verify_email(body: VerifyEmailRequest, db: DbSession) -> MessageOut:
    user = accounts.use_link(db, body.token, VERIFY_EMAIL)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_LINK)
    user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
    db.commit()
    return MessageOut(message="Your email address is confirmed.")


@router.post("/resend-verification", response_model=MessageOut)
def resend_verification(user: CurrentUser, db: DbSession, background: BackgroundTasks) -> MessageOut:
    if user.email_verified_at is not None or user.email is None:
        return MessageOut(message="Your email address is already confirmed.")
    token = accounts.create_link(db, user, VERIFY_EMAIL)
    db.commit()
    background.add_task(send_email, accounts.verify_email_message(user, token))
    return MessageOut(message=f"We sent a new link to {user.email}.")


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(body: ForgotPasswordRequest, db: DbSession, background: BackgroundTasks) -> MessageOut:
    # Same answer whether or not the account exists, so this can't be used to
    # find out who has an account.
    user = accounts.find_user_for_login(db, body.email)
    if user is not None and user.email and user.is_active:
        token = accounts.create_link(db, user, RESET_PASSWORD)
        db.commit()
        background.add_task(send_email, accounts.reset_password_message(user, token))
    return MessageOut(message="If an account uses that email, we've sent it a link to reset the password.")


@router.post("/reset-password", response_model=MessageOut)
def reset_password(body: ResetPasswordRequest, db: DbSession) -> MessageOut:
    user = accounts.use_link(db, body.token, RESET_PASSWORD)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_LINK)
    accounts.set_password(db, user, body.password)
    # The link arrived in their inbox, which proves the address too.
    user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
    db.commit()
    return MessageOut(message="Your password is changed. Sign in with the new one.")


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        username=user.username,
        role=user.role,
        is_platform_admin=user.is_platform_admin,
        email_verified=user.email_verified_at is not None,
        organization=user.organization,  # type: ignore[arg-type]
    )
