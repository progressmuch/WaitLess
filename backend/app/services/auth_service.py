"""Authentication business logic: credential checks, registration and tokens.

Security notes:
* Login failures never reveal whether the email exists: both cases return the
  same message and both perform a password hash verification, which keeps the
  response time roughly constant.
* Account state (`is_active`) is checked on every authenticated request via
  `app.api.deps.get_current_user`, so deactivating a user invalidates their
  existing tokens immediately.
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import (
    _DUMMY_PASSWORD_HASH,
    create_access_token,
    verify_password,
)
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate, UserManagementCreate
from app.services import user_service

# Same message for unknown email and wrong password (no user enumeration).
INVALID_CREDENTIALS_MESSAGE = "Incorrect email or password"


def authenticate(db: Session, *, email: str, password: str) -> User:
    """Validate credentials and return the matching active user.

    Raises:
        UnauthorizedException: wrong email or wrong password.
        ForbiddenException: the account exists but is deactivated.
    """
    user = user_service.get_user_by_email(db, email)

    if user is None:
        # Spend comparable time hashing so response timing does not leak
        # whether the email address is registered.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        raise UnauthorizedException(INVALID_CREDENTIALS_MESSAGE)

    if not verify_password(password, user.password_hash):
        raise UnauthorizedException(INVALID_CREDENTIALS_MESSAGE)

    # Checked after the password so an attacker cannot probe account state
    # without valid credentials.
    if not user.is_active:
        raise ForbiddenException("User account is deactivated")

    return user


def register_commuter(db: Session, payload: UserCreate) -> User:
    """Public self-registration. The role is always COMMUTER."""
    return user_service.create_user(
        db,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password=payload.password,
        role=UserRole.COMMUTER,
    )


def create_staff_user(db: Session, payload: UserManagementCreate) -> User:
    """Create an OPERATOR/MANAGEMENT account. Management-only operation."""
    return user_service.create_user(
        db,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password=payload.password,
        role=payload.role,
    )


def issue_access_token(user: User) -> TokenResponse:
    """Build the login response for a user."""
    return TokenResponse(
        access_token=create_access_token(user.id),
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )