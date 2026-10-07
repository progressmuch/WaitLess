"""Authentication endpoints (docs/05-api-specification.md section 2).

Access rules for every endpoint in this module:

| Endpoint          | Auth required | Role required |
|-------------------|---------------|---------------|
| POST /auth/register | no            | -             |
| POST /auth/login    | no            | -             |
| GET  /auth/me       | yes           | any           |
| POST /auth/users    | yes           | MANAGEMENT    |

Note on roles: public registration always creates a COMMUTER. OPERATOR and
MANAGEMENT accounts are created through `POST /auth/users`, which is
management-only, so a role can never be self-assigned.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import APIResponse
from app.schemas.user import UserCreate, UserManagementCreate, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=APIResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
    summary="Register a commuter account",
)
def register(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> APIResponse[UserRead]:
    """Create a new COMMUTER account.

    409 if the email is already registered, 422 if the payload is invalid.
    """
    user = auth_service.register_commuter(db, payload)
    return APIResponse(data=UserRead.model_validate(user), message="Registration successful")


@router.post(
    "/login",
    response_model=APIResponse[TokenResponse],
    summary="Exchange credentials for an access token",
)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> APIResponse[TokenResponse]:
    """Authenticate and return a JWT access token.

    401 for wrong email or password, 403 for a deactivated account.
    """
    user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    return APIResponse(data=auth_service.issue_access_token(user), message="Login successful")


@router.get(
    "/me",
    response_model=APIResponse[UserRead],
    summary="Return the authenticated user's profile",
)
def read_current_user(current_user: CurrentUser) -> APIResponse[UserRead]:
    """Return the profile of the account that owns the bearer token."""
    return APIResponse(data=UserRead.model_validate(current_user))


@router.post(
    "/users",
    response_model=APIResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create an OPERATOR or MANAGEMENT account (MANAGEMENT only)",
)
def create_staff_user(
    payload: UserManagementCreate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(require_roles(UserRole.MANAGEMENT))],
) -> APIResponse[UserRead]:
    """Create a staff account with an explicit role.

    This is the only supported way to obtain an OPERATOR or MANAGEMENT user.
    """
    user = auth_service.create_staff_user(db, payload)
    return APIResponse(data=UserRead.model_validate(user), message="User created successfully")