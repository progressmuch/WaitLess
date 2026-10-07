"""Reusable FastAPI dependencies: authentication and role authorization.

An endpoint declares its access requirements like this:

    from typing import Annotated
    from app.api.deps import CurrentUser, require_roles

    @router.get("/private")
    def private(user: CurrentUser): ...

    @router.post("/management-only")
    def management_only(
        user: Annotated[User, Depends(require_roles(UserRole.MANAGEMENT))],
    ): ...
"""

from typing import Annotated, Callable, Optional
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services import user_service

# HTTPBearer is used (instead of OAuth2PasswordBearer) because login takes a
# JSON body, not form-encoded credentials. Clients still send:
#     Authorization: Bearer <access_token>
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")


def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ] = None,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the bearer token.

    The token only carries the user id; the record is re-read from the
    database so role changes and deactivation apply immediately.

    Raises:
        UnauthorizedException: token missing, invalid, expired, or user gone.
        ForbiddenException: the account is deactivated.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedException("Not authenticated")

    payload = decode_access_token(credentials.credentials)

    subject = payload.get("sub")
    try:
        user_id = UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise UnauthorizedException("Invalid authentication token") from exc

    user = user_service.get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedException("User account no longer exists")

    if not user.is_active:
        raise ForbiddenException("User account is deactivated")

    return user


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
    """Build a dependency that only allows the given roles.

    Roles are checked against the database record, never against a value taken
    from the request body or from the token payload.

    Raises:
        ForbiddenException: the authenticated user has a different role.
    """

    def role_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                "You do not have permission to perform this action"
            )
        return current_user

    return role_dependency


# Convenience annotation for "any authenticated user".
CurrentUser = Annotated[User, Depends(get_current_user)]