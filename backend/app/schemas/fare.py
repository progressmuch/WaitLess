"""Fare request/response schemas (docs/05-api-specification.md section 7).

Money is a `Decimal`, so it serializes as a JSON string ("1.50") exactly the
way docs/10 section 4 asks, never as a binary float.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.validators import normalize_required_text


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Treat a timestamp without an offset as UTC.

    docs/10 section 3 prefers UTC; a client that sends "2026-11-01T00:00:00"
    means local wall time, and interpreting it as UTC keeps every stored
    comparison timezone-aware (PostgreSQL rejects mixed awareness).
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class FareCreate(BaseModel):
    """Payload for POST /fares (MANAGEMENT only).

    A fare names its whole journey context: the route plus both ends of the
    trip (docs/02 business rule 6).
    """

    model_config = ConfigDict(extra="forbid")

    route_id: UUID
    origin_stop_id: UUID
    destination_stop_id: UUID
    # Positive, at most two decimals, at most 8 digits before the point -
    # exactly what Numeric(10, 2) can store.
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    # Omit it and the fare is priced in the default currency. The length check
    # lives in the validator below so that a padded value like "  usd " can be
    # trimmed and folded instead of rejected by a field constraint.
    currency: str = Field(default="USD")
    # Omit it and the fare starts immediately (server time).
    effective_from: Optional[datetime] = None

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        normalized = normalize_required_text(value, "Currency").upper()
        if len(normalized) != 3 or not normalized.isascii() or not normalized.isalpha():
            raise ValueError("Currency must be a 3-letter code such as USD")
        return normalized

    @field_validator("effective_from")
    @classmethod
    def normalize_effective_from(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            raise ValueError("effective_from cannot be null; omit it to start now")
        return as_utc(value)

    @model_validator(mode="after")
    def journey_makes_sense(self) -> "FareCreate":
        if self.origin_stop_id == self.destination_stop_id:
            raise ValueError("Origin and destination stops must be different")
        return self


class FareUpdate(BaseModel):
    """Payload for PATCH /fares/{fare_id}: lifecycle only.

    The price itself is never edited in place - that would destroy history
    (docs/02 business rule 7). To change what a journey costs, management
    POSTs a new fare, which supersedes the current one.

    `effective_to` sent as `null` re-opens the window; any value must be after
    `effective_from`.
    """

    model_config = ConfigDict(extra="forbid")

    is_active: Optional[bool] = None
    effective_to: Optional[datetime] = None

    @field_validator("is_active")
    @classmethod
    def reject_null_flag(cls, value: Optional[bool]) -> bool:
        if value is None:
            raise ValueError("is_active cannot be null")
        return value

    @field_validator("effective_to")
    @classmethod
    def normalize_effective_to(cls, value: Optional[datetime]) -> Optional[datetime]:
        # `null` is meaningful here: it clears the end of the window.
        return as_utc(value)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "FareUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class FareRead(BaseModel):
    """A fare as returned by the list, search, create and update endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    route_id: UUID
    origin_stop_id: UUID
    destination_stop_id: UUID
    amount: Decimal
    currency: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    is_active: bool
    created_at: datetime
