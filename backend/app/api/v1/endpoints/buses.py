"""Bus endpoints (docs/05-api-specification.md section 5).

| Endpoint             | Auth required | Role required |
|----------------------|---------------|---------------|
| GET  /buses          | yes           | MANAGEMENT    |
| POST /buses          | yes           | MANAGEMENT    |
| PATCH /buses/{bus_id}| yes           | MANAGEMENT    |

The fleet is operational data (plates, capacities, what runs where), so every
bus endpoint is management-only. Buses are deactivated with
`PATCH {"is_active": false}` rather than deleted.
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.bus import BusCreate, BusRead, BusUpdate
from app.schemas.common import APIResponse
from app.services import bus_service

router = APIRouter(tags=["buses"])

# Reusable dependency for the management-only fleet endpoints.
ManagementUser = Annotated[User, Depends(require_roles(UserRole.MANAGEMENT))]


@router.get(
    "/buses",
    response_model=APIResponse[list[BusRead]],
    summary="List buses (MANAGEMENT only)",
)
def list_buses(
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
    is_active: Annotated[
        Optional[bool],
        Query(description="Filter by state; omit to return active buses only"),
    ] = None,
) -> APIResponse[list[BusRead]]:
    """Return buses ordered by fleet number.

    Only buses still in service are returned unless `is_active` is given.
    """
    buses = bus_service.list_buses(db, is_active=is_active)
    return APIResponse(data=[BusRead.model_validate(bus) for bus in buses])


@router.post(
    "/buses",
    response_model=APIResponse[BusRead],
    status_code=status.HTTP_201_CREATED,
    summary="Register a bus (MANAGEMENT only)",
)
def create_bus(
    payload: BusCreate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[BusRead]:
    """Register a bus, optionally already assigned to a route.

    409 if the registration or fleet number is already in use, 404 if
    `route_id` is unknown, 422 if the payload is invalid.
    """
    bus = bus_service.create_bus(db, payload)
    return APIResponse(data=BusRead.model_validate(bus), message="Bus created successfully")


@router.patch(
    "/buses/{bus_id}",
    response_model=APIResponse[BusRead],
    summary="Update a bus (MANAGEMENT only)",
)
def update_bus(
    bus_id: UUID,
    payload: BusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[BusRead]:
    """Update the fields that are present in the payload.

    `route_id` assigns the bus to a route and `route_id: null` clears the
    assignment. 404 if the bus or the route is unknown, 409 if a new
    registration or fleet number is taken.
    """
    bus = bus_service.update_bus(db, bus_id, payload)
    return APIResponse(data=BusRead.model_validate(bus), message="Bus updated successfully")
