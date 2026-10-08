"""Fare endpoints (docs/05-api-specification.md section 7).

| Endpoint          | Auth required | Role required |
|-------------------|---------------|---------------|
| GET  /fares       | no            | -             |
| GET  /fares/search| no            | -             |
| POST /fares       | yes           | MANAGEMENT    |
| PATCH /fares/{id} | yes           | MANAGEMENT    |

Fares are public reads, like routes and stops: a commuter must see the price
of a journey before deciding to travel, and journey searches may be anonymous
(docs/04 section 12). Configuring a price stays management-only.

`GET /fares` returns the fares that apply right now; add `include_history=true`
to read the preserved history as well (docs/02 FR-08). The price itself is
only ever set through POST - a new fare supersedes the previous one instead of
overwriting it (docs/02 business rule 7).
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.fare import FareCreate, FareRead, FareUpdate
from app.services import fare_service

router = APIRouter(tags=["fares"])

# Reusable dependency for the management-only writes.
ManagementUser = Annotated[User, Depends(require_roles(UserRole.MANAGEMENT))]


@router.get(
    "/fares",
    response_model=APIResponse[list[FareRead]],
    summary="List fares (public)",
)
def list_fares(
    db: Annotated[Session, Depends(get_db)],
    route_id: Annotated[Optional[UUID], Query(description="Only fares of this route")] = None,
    origin_stop_id: Annotated[
        Optional[UUID], Query(description="Only fares starting at this stop")
    ] = None,
    destination_stop_id: Annotated[
        Optional[UUID], Query(description="Only fares ending at this stop")
    ] = None,
    include_history: Annotated[
        bool,
        Query(
            description=(
                "Also return superseded, expired and deactivated fares "
                "(the fare history)"
            )
        ),
    ] = False,
) -> APIResponse[list[FareRead]]:
    """Return fares, newest first.

    Without parameters this is the commuter view: every fare that applies
    right now. `include_history=true` additionally returns the preserved
    history, which is how management audits what a journey used to cost.
    """
    fares = fare_service.list_fares(
        db,
        route_id=route_id,
        origin_stop_id=origin_stop_id,
        destination_stop_id=destination_stop_id,
        include_history=include_history,
    )
    return APIResponse(data=[FareRead.model_validate(fare) for fare in fares])


@router.get(
    "/fares/search",
    response_model=APIResponse[list[FareRead]],
    summary="Find the fares for an origin/destination pair (public)",
)
def search_fares(
    db: Annotated[Session, Depends(get_db)],
    origin_stop_id: Annotated[UUID, Query(description="Where the journey starts")],
    destination_stop_id: Annotated[UUID, Query(description="Where the journey ends")],
    route_id: Annotated[
        Optional[UUID], Query(description="Restrict the search to one route")
    ] = None,
) -> APIResponse[list[FareRead]]:
    """Return the fares that apply to this pair of stops right now.

    200 with an empty list when no fare is configured for the pair yet;
    404 when a stop (or route) id is unknown; 422 when origin and
    destination are the same stop.
    """
    fares = fare_service.search_fares(
        db,
        origin_stop_id=origin_stop_id,
        destination_stop_id=destination_stop_id,
        route_id=route_id,
    )
    return APIResponse(data=[FareRead.model_validate(fare) for fare in fares])


@router.post(
    "/fares",
    response_model=APIResponse[FareRead],
    status_code=status.HTTP_201_CREATED,
    summary="Configure a fare (MANAGEMENT only)",
)
def create_fare(
    payload: FareCreate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[FareRead]:
    """Configure the fare for a journey from `effective_from` onwards.

    404 if the route or a stop is unknown, 422 if the stops are not both on
    the route (or are the same stop), 409 if another active fare of the same
    journey starts at exactly the same moment. Any fare it replaces is kept
    as history, closed at the moment the new price starts.
    """
    fare = fare_service.create_fare(db, payload)
    return APIResponse(data=FareRead.model_validate(fare), message="Fare created successfully")


@router.patch(
    "/fares/{fare_id}",
    response_model=APIResponse[FareRead],
    summary="Adjust the lifecycle of a fare (MANAGEMENT only)",
)
def update_fare(
    fare_id: UUID,
    payload: FareUpdate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[FareRead]:
    """Deactivate/reactivate a fare or move the end of its validity window.

    The amount is deliberately not editable - send a new POST /fares instead,
    so the previous price stays in the history (docs/02 business rule 7), so
    a payload containing `amount` answers 422.

    404 if the fare is unknown, 422 if `effective_to` is not after
    `effective_from`, 409 if the change would overlap another active fare of
    the same journey.
    """
    fare = fare_service.update_fare(db, fare_id, payload)
    return APIResponse(data=FareRead.model_validate(fare), message="Fare updated successfully")
