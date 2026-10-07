"""Operator assignment request/response schemas (docs/05 section 6).

An assignment hands a bus to an operator, and the route the operator sees is
the route of that bus, so the response nests the bus and its route.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.route import RouteSummary


class BusSummary(BaseModel):
    """Bus as embedded in an assignment, including the route it runs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    registration_number: str
    fleet_number: str
    capacity: int
    is_active: bool
    # Null when the bus has not been assigned a route yet.
    route: Optional[RouteSummary] = None


class OperatorAssignmentCreate(BaseModel):
    """Payload for POST /operators/{operator_id}/assignments (MANAGEMENT only)."""

    model_config = ConfigDict(extra="forbid")

    bus_id: UUID


class OperatorAssignmentRead(BaseModel):
    """An assignment together with the bus (and route) it hands over."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operator_id: UUID
    bus_id: UUID
    assigned_at: datetime
    # Set when the assignment was ended; null while it is running.
    ended_at: Optional[datetime] = None
    is_active: bool
    bus: BusSummary
