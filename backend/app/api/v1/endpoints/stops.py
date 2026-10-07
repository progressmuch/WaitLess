"""Stop endpoints (docs/05-api-specification.md section 4).

| Endpoint                | Auth required | Role required |
|-------------------------|---------------|---------------|
| GET  /stops             | no            | -             |
| POST /stops             | yes           | MANAGEMENT    |
| PATCH /stops/{stop_id}  | yes           | MANAGEMENT    |

The stop list is public for the same reason routes are: commuters need it to
plan a journey before signing in. Writes are management-only.
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.stop import StopCreate, StopRead, StopUpdate
from app.services import stop_service

router = APIRouter(tags=["stops"])

# Reusable dependency for the management-only writes.
ManagementUser = Annotated[User, Depends(require_roles(UserRole.MANAGEMENT))]


@router.get(
    "/stops",
    response_model=APIResponse[list[StopRead]],
    summary="List stops (public)",
)
def list_stops(
    db: Annotated[Session, Depends(get_db)],
    is_active: Annotated[
        Optional[bool],
        Query(description="Filter by state; omit to return active stops only"),
    ] = None,
) -> APIResponse[list[StopRead]]:
    """Return stops ordered by name.

    Only active stops are returned unless `is_active` is given, so a
    deactivated stop disappears from public listings without being deleted.
    """
    stops = stop_service.list_stops(db, is_active=is_active)
    return APIResponse(data=[StopRead.model_validate(stop) for stop in stops])


@router.post(
    "/stops",
    response_model=APIResponse[StopRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a stop (MANAGEMENT only)",
)
def create_stop(
    payload: StopCreate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[StopRead]:
    """Create a stop. 422 if the coordinates fall outside valid ranges."""
    stop = stop_service.create_stop(db, payload)
    return APIResponse(data=StopRead.model_validate(stop), message="Stop created successfully")


@router.patch(
    "/stops/{stop_id}",
    response_model=APIResponse[StopRead],
    summary="Update a stop (MANAGEMENT only)",
)
def update_stop(
    stop_id: UUID,
    payload: StopUpdate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[StopRead]:
    """Update the fields that are present in the payload.

    404 if the stop is unknown; deactivating a stop keeps it in the database
    because routes still reference it.
    """
    stop = stop_service.update_stop(db, stop_id, payload)
    return APIResponse(data=StopRead.model_validate(stop), message="Stop updated successfully")
