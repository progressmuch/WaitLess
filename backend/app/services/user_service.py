"""User data access and creation rules.

Route handlers stay thin: they validate input, call this service and map the
result onto a response schema (docs/09-backend-project-structure.md).
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import hash_password
from app.models.user import User, UserRole


def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    """Return the user with this id, or None."""
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Return the user with this (already normalised) email, or None."""
    return db.execute(select(User).where(User.email == email.strip().lower())).scalar_one_or_none()


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    role: UserRole = UserRole.COMMUTER,
    phone: Optional[str] = None,
) -> User:
    """Create and persist a user account.

    The password is hashed here so that no caller can accidentally store a
    plaintext value.

    Raises:
        ConflictException: if the email address is already registered.
    """
    user = User(
        full_name=full_name,
        email=email.strip().lower(),
        phone=phone,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Unique violation on users.email -> friendly 409 instead of a 500.
        db.rollback()
        raise ConflictException("Email address is already registered") from exc
    db.refresh(user)
    return user


def get_user_or_404(db: Session, user_id: UUID) -> User:
    """Return the user with this id or raise a 404."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundException("User not found")
    return user