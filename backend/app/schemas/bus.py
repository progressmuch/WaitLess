"""Bus request/response schemas (docs/05-api-specification.md section 5).

Registration plates and fleet numbers are upper-cased identifiers, normalized
the same way route codes are.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.validators import normalize_identifier


class BusCreate(BaseModel):
    """Payload for POST /buses (MANAGEMENT only)."""

    model_config = ConfigDict(extra="forbid")

    registration_number: str = Field(min_length=1, max_length=32)
    fleet_number: str = Field(min_length=1, max_length=32)
    # Passenger seats. The upper bound is a sanity limit: no bus seats 1000.
    capacity: int = Field(ge=1, le=1000)
    # Optional: a bus may join the fleet before anyone picks its route.
    route_id: Optional[UUID] = None

    @field_validator("registration_number")
    @classmethod
    def clean_registration_number(cls, value: str) -> str:
        return normalize_identifier(value, "Registration number")

    @field_validator("fleet_number")
    @classmethod
    def clean_fleet_number(cls, value: str) -> str:
        return normalize_identifier(value, "Fleet number")


class BusUpdate(BaseModel):
    """Payload for PATCH /buses/{bus_id}: only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    registration_number: Optional[str] = Field(default=None, max_length=32)
    fleet_number: Optional[str] = Field(default=None, max_length=32)
    capacity: Optional[int] = Field(default=None, ge=1, le=1000)
    # `null` clears the route assignment; omitting the field leaves it alone.
    route_id: Optional[UUID] = None
    is_active: Optional[bool] = None

    @field_validator("registration_number")
    @classmethod
    def clean_registration_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            raise ValueError("Registration number cannot be null")
        return normalize_identifier(value, "Registration number")

    @field_validator("fleet_number")
    @classmethod
    def clean_fleet_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            raise ValueError("Fleet number cannot be null")
        return normalize_identifier(value, "Fleet number")

    @field_validator("capacity")
    @classmethod
    def reject_null_capacity(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            raise ValueError("capacity cannot be null")
        return value

    @field_validator("is_active")
    @classmethod
    def reject_null_flag(cls, value: Optional[bool]) -> Optional[bool]:
        if value is None:
            raise ValueError("is_active cannot be null")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self) -> "BusUpdate":
        # An empty PATCH would silently do nothing.
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class BusRead(BaseModel):
    """Bus without its route details - `route_id` shows the assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    registration_number: str
    fleet_number: str
    capacity: int
    # Null when the bus is not assigned to a route.
    route_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
