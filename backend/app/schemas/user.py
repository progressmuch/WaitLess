"""User request/response schemas.

`password_hash` is intentionally absent from every response schema so it can
never leak through the API (docs/05-api-specification.md section 12).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole
from app.schemas.validators import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    normalize_email,
)


class UserFieldsMixin(BaseModel):
    """Shared profile fields with input normalisation."""

    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(max_length=320)
    phone: Optional[str] = Field(default=None, max_length=32)

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("Full name is required")
        return cleaned

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class UserCreate(UserFieldsMixin):
    """Public registration payload.

    There is deliberately no `role` field: a user may never choose their own
    role (docs/08-ai-workflow-rules.md section 8). Extra fields are rejected so
    a client attempting to escalate privileges gets a 422 instead of a silent
    success.
    """

    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class UserManagementCreate(UserFieldsMixin):
    """Payload for MANAGEMENT users creating OPERATOR/MANAGEMENT accounts."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    role: UserRole


class UserRead(BaseModel):
    """Public representation of a user account."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime