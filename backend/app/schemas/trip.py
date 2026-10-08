"""Trip schemas for Phase 4 (trips and locations)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.bus import BusRead
from app.schemas.route import RouteSummary
from app.schemas.validators import as_utc


class TripStartRequest(BaseModel):
    """Payload for POST /trips/start (OPERATOR only)."""

    model_config = ConfigDict(extra="forbid")

    bus_id: UUID
    route_id: UUID


class TripRead(BaseModel):
    """Representation of a trip."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bus_id: UUID
    operator_id: UUID
    route_id: UUID
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None


class TripWithDetails(TripRead):
    """Trip including its bus and route for convenient responses."""

    model_config = ConfigDict(from_attributes=True)

    bus: Optional[BusRead] = None
    route: Optional[RouteSummary] = None


class LocationUpdateRequest(BaseModel):
    """Payload for POST /trips/{trip_id}/location (OPERATOR only)."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed: Optional[float] = Field(default=None, ge=0, le=200)
    heading: Optional[int] = Field(default=None, ge=0, le=359)
    captured_at: Optional[datetime] = None

    @model_validator(mode="after")
    def normalize_captured_at(self) -> "LocationUpdateRequest":
        # Treat naive timestamps as UTC (docs/10 section 3).
        self.captured_at = as_utc(self.captured_at)
        return self


class LocationRead(BaseModel):
    """Latest location with freshness context."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: UUID
    bus_id: UUID
    latitude: float
    longitude: float
    speed: Optional[float] = None
    heading: Optional[int] = None
    captured_at: datetime
    received_at: datetime
    freshness_status: Optional[str] = None
