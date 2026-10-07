"""Route endpoints (docs/05-api-specification.md section 3).

| Endpoint                      | Auth required | Role required |
|-------------------------------|---------------|---------------|
| GET  /routes                  | no            | -             |
| GET  /routes/{route_id}       | no            | -             |
| POST /routes                  | yes           | MANAGEMENT    |
| PATCH /routes/{route_id}      | yes           | MANAGEMENT    |
| PUT  /routes/{route_id}/stops | yes           | MANAGEMENT    |

Route data is public on purpose: commuters browse routes before they have an
account, and journey searches are allowed to be anonymous (docs/04 section 12
keeps `journey_searches.commuter_id` nullable). Every write stays
management-only.

There is deliberately no DELETE route: routes are deactivated with
`PATCH {"is_active": false}` instead of being deleted (docs/05 section 3), so
a DELETE on these paths answers 405 Method Not Allowed.
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.route import (
    RouteCreate,
    RouteDetailRead,
    RouteRead,
    RouteStopsReplace,
    RouteUpdate,
)
from app.services import route_service

router = APIRouter(tags=["routes"])

# Reusable dependency for the management-only writes.
ManagementUser = Annotated[User, Depends(require_roles(UserRole.MANAGEMENT))]


@router.get(
    "/routes",
    response_model=APIResponse[list[RouteRead]],
    summary="List routes (public)",
)
def list_routes(
    db: Annotated[Session, Depends(get_db)],
    is_active: Annotated[
        Optional[bool],
        Query(description="Filter by state; omit to return active routes only"),
    ] = None,
) -> APIResponse[list[RouteRead]]:
    """Return routes ordered by code.

    Only active routes are returned unless `is_active` is given, which is how
    management inspects deactivated routes.
    """
    routes = route_service.list_routes(db, is_active=is_active)
    return APIResponse(data=[RouteRead.model_validate(route) for route in routes])


@router.get(
    "/routes/{route_id}",
    response_model=APIResponse[RouteDetailRead],
    summary="Return one route with its ordered stops (public)",
)
def get_route(
    route_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> APIResponse[RouteDetailRead]:
    """Return route details and its stops in `stop_sequence` order.

    A deactivated route still returns 200 with `is_active: false`; it is only
    hidden from the list. 404 if the id is unknown.
    """
    route = route_service.get_route_detail(db, route_id)
    return APIResponse(data=RouteDetailRead.model_validate(route))


@router.post(
    "/routes",
    response_model=APIResponse[RouteRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a route (MANAGEMENT only)",
)
def create_route(
    payload: RouteCreate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[RouteRead]:
    """Create a route, optionally together with its ordered stops.

    409 if the code is already in use, 422 if the payload is invalid.
    """
    route = route_service.create_route(db, payload)
    return APIResponse(data=RouteRead.model_validate(route), message="Route created successfully")


@router.patch(
    "/routes/{route_id}",
    response_model=APIResponse[RouteRead],
    summary="Update a route (MANAGEMENT only)",
)
def update_route(
    route_id: UUID,
    payload: RouteUpdate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[RouteRead]:
    """Update the fields that are present in the payload.

    404 if the route is unknown, 409 when activating a route that has fewer
    than two stops or when the new code is taken.
    """
    route = route_service.update_route(db, route_id, payload)
    return APIResponse(data=RouteRead.model_validate(route), message="Route updated successfully")


@router.put(
    "/routes/{route_id}/stops",
    response_model=APIResponse[RouteDetailRead],
    summary="Replace the ordered stop list of a route (MANAGEMENT only)",
)
def replace_route_stops(
    route_id: UUID,
    payload: RouteStopsReplace,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[RouteDetailRead]:
    """Replace every stop of the route in one transaction.

    The returned detail shows the resulting order. 404 if the route or one of
    the stops is unknown, 422 if the list is shorter than two stops, contains
    a duplicate stop or has decreasing timings.
    """
    route = route_service.replace_route_stops(db, route_id, payload)
    return APIResponse(
        data=RouteDetailRead.model_validate(route),
        message="Route stops updated successfully",
    )
