from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Long enough to resist guessing, short enough that argon2 stays fast.
Password = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    # An email address, or a username for users from before email sign-in.
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class SignupRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=254)
    password: str = Password


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    password: str = Password


class MessageOut(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserOut(BaseModel):
    id: int
    email: str | None
    name: str | None
    username: str | None
    role: str
    is_platform_admin: bool
    email_verified: bool
    organization: OrganizationOut
