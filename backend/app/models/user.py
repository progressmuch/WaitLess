"""User account model and the three system roles.

Field list follows docs/04-database-specification.md section 3.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserRole(str, Enum):
    """System roles (docs/02-product-requirements.md FR-01).

    Inherits from `str` so the value can be used directly in comparisons and
    serialised as a plain string in JSON responses.
    """

    COMMUTER = "COMMUTER"
    OPERATOR = "OPERATOR"
    MANAGEMENT = "MANAGEMENT"


class User(Base):
    """A system user: commuter, bus operator or management member."""

    __tablename__ = "users"

    # Business entities use UUIDs (docs/04-database-specification.md section 14).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stored lower-cased by the schema layer so uniqueness is case-insensitive.
    email: Mapped[str] = mapped_column(
        String(320), nullable=False, unique=True, index=True
    )
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Argon2id hash, never the plaintext password.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Stored as VARCHAR + CHECK constraint (native_enum=False) so that new
    # roles can be added later without PostgreSQL enum type migrations.
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=False, length=16),
        nullable=False,
        default=UserRole.COMMUTER,
        server_default=UserRole.COMMUTER.value,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User id={self.id} email={self.email} role={self.role}>"