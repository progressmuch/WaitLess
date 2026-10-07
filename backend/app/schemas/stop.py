"""Stop request/response schemas (docs/05-api-specification.md section 4).

Latitude/longitude are checked against valid WGS84 ranges here, so an
out-of-range coordinate is rejected with a 422 before it can reach the
database.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.validators import normalize_required_text


class StopCreate(BaseModel):
    """Payload for POST /stops (MANAGEMENT only)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    # WGS84 degrees.
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return normalize_required_text(value, "Stop name")


class StopUpdate(BaseModel):
    """Payload for PATCH /stops/{stop_id}: only the fields sent are changed.

    `None` means "leave unchanged" for fields that were not sent at all; a
    field sent explicitly as `null` is rejected where the column cannot be
    null (name, latitude, longitude). `description`-style nullable columns
    accept `null` as "clear this value".
    """

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: Optional[str]) -> str:
        # Defaults are not validated by pydantic, so this only runs when the
        # client actually sent `name`.
        return normalize_required_text(value, "Stop name")

    @field_validator("latitude", "longitude")
    @classmethod
    def reject_null_coordinates(cls, value: Optional[float]) -> float:
        if value is None:
            raise ValueError("Coordinates cannot be null")
        return value

    @field_validator("is_active")
    @classmethod
    def reject_null_flag(cls, value: Optional[bool]) -> bool:
        if value is None:
            raise ValueError("is_active cannot be null")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self) -> "StopUpdate":
        # An empty PATCH would silently do nothing; make the client say what
        # it wants instead.
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class StopSummary(BaseModel):
    """The stop details embedded in a route's ordered stop list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    latitude: float
    longitude: float
    is_active: bool


class StopRead(BaseModel):
    """Public representation of a stop."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    latitude: float
    longitude: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
