"""Authentication request/response schemas (docs/05-api-specification.md section 2)."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validators import (
    MAX_PASSWORD_LENGTH,
    normalize_email,
)


class LoginRequest(BaseModel):
    """JSON login payload: `{"email": "...", "password": "..."}`."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return normalize_email(value)


class TokenResponse(BaseModel):
    """Access token issued on successful login."""

    access_token: str
    token_type: str = "bearer"
    # Token lifetime in seconds, so clients can refresh before expiry.
    expires_in: int