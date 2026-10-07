"""Route request/response schemas (docs/05-api-specification.md section 3).

`GET /routes/{route_id}` promises "route details and ordered stops", so the
detail response nests the stops under a `stops` key (mapped from the ORM's
`route_stops` relationship).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.stop import StopSummary
from app.schemas.validators import normalize_required_text, normalize_route_code


class RouteStopInput(BaseModel):
    """One stop of the route being written.

    List order becomes `stop_sequence`, so clients describe a route the same
    way a passenger reads it: first stop first.
    """

    model_config = ConfigDict(extra="forbid")

    stop_id: UUID
    # Optional timing: a route can be laid out before ETA data exists.
    estimated_minutes_from_start: Optional[int] = Field(default=None, ge=0, le=1440)


def check_stop_list(stops: list[RouteStopInput]) -> list[RouteStopInput]:
    """Validate the ordered `stops` payload of a route.

    Shared by POST /routes and PUT /routes/{route_id}/stops so both endpoints
    enforce the same rules (docs/02 business rule 5: ordered stops).

    Raises:
        ValueError: mapped by FastAPI to a 422 response.
    """
    if len(stops) < 2:
        raise ValueError("A route needs at least two stops")

    seen: set[UUID] = set()
    for item in stops:
        if item.stop_id in seen:
            raise ValueError(f"Stop {item.stop_id} appears more than once")
        seen.add(item.stop_id)

    # Timing must never go backwards along the route. Entries without timing
    # are skipped, so a route can be laid out before every ETA is known.
    minutes = [
        item.estimated_minutes_from_start
        for item in stops
        if item.estimated_minutes_from_start is not None
    ]
    if any(later < earlier for earlier, later in zip(minutes, minutes[1:])):
        raise ValueError(
            "estimated_minutes_from_start must not decrease along the route"
        )
    return stops


class RouteCreate(BaseModel):
    """Payload for POST /routes (MANAGEMENT only)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=2, max_length=64)
    description: Optional[str] = Field(default=None, max_length=500)
    # Omitting `stops` creates a draft route; supplying them publishes it.
    stops: Optional[list[RouteStopInput]] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return normalize_required_text(value, "Route name")

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        return normalize_route_code(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: Optional[str]) -> Optional[str]:
        # A blank description is the same as no description.
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_stops(self) -> "RouteCreate":
        if self.stops is not None:
            check_stop_list(self.stops)
        return self


class RouteUpdate(BaseModel):
    """Payload for PATCH /routes/{route_id}: only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, max_length=255)
    code: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: Optional[str]) -> str:
        return normalize_required_text(value, "Route name")

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: Optional[str]) -> str:
        if value is None:
            raise ValueError("Route code cannot be null")
        return normalize_route_code(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: Optional[str]) -> Optional[str]:
        # The column is nullable, so `null` (or a blank string) clears it.
        if value is None:
            return None
        return value.strip() or None

    @field_validator("is_active")
    @classmethod
    def reject_null_flag(cls, value: Optional[bool]) -> bool:
        if value is None:
            raise ValueError("is_active cannot be null")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self) -> "RouteUpdate":
        # An empty PATCH would silently do nothing.
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class RouteStopsReplace(BaseModel):
    """Payload for PUT /routes/{route_id}/stops: the complete new stop list."""

    model_config = ConfigDict(extra="forbid")

    stops: list[RouteStopInput]

    @model_validator(mode="after")
    def validate_stops(self) -> "RouteStopsReplace":
        check_stop_list(self.stops)
        return self


class RouteStopRead(BaseModel):
    """One ordered stop of a route, as returned in the route detail."""

    model_config = ConfigDict(from_attributes=True)

    stop_sequence: int
    stop_id: UUID
    estimated_minutes_from_start: Optional[int] = None
    stop: StopSummary


class RouteSummary(BaseModel):
    """Compact route as embedded in another resource.

    Used by buses and operator assignments, which need the code and name of a
    route without its stop list.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    is_active: bool


class RouteRead(BaseModel):
    """Route without its stops - used by the list, create and update endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RouteDetailRead(RouteRead):
    """Route plus its ordered stops (docs/05 section 3).

    `validation_alias` maps the ORM's `route_stops` relationship onto the
    `stops` key the API contract promises.
    """

    stops: list[RouteStopRead] = Field(validation_alias="route_stops")
