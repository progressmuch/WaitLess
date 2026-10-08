"""Trip and location endpoints (docs/05-api-specification.md sections 8 and 9)."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.trip import (
    LocationRead,
    LocationUpdateRequest,
    TripRead,
    TripStartRequest,
    TripWithDetails,
)
from app.services import trip_service

router = APIRouter(tags=["trips"])

OperatorUser = Annotated[User, Depends(require_roles(UserRole.OPERATOR))]


@router.get(
    "/trips/active",
    response_model=APIResponse[list[TripRead]],
    summary="List active trips",
)
def list_active_trips(
    db: Annotated[Session, Depends(get_db)],
    route_id: Annotated[Optional[UUID], Query(description="Filter by route")] = None,
) -> APIResponse[list[TripRead]]:
    trips = trip_service.list_active_trips(db, route_id=route_id)
    return APIResponse(data=[TripRead.model_validate(t) for t in trips])


@router.post(
    "/trips/start",
    response_model=APIResponse[TripRead],
    status_code=status.HTTP_201_CREATED,
    summary="Start a trip (OPERATOR only)",
)
def start_trip(
    payload: TripStartRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: OperatorUser,
) -> APIResponse[TripRead]:
    trip = trip_service.start_trip(db, current_user, payload)
    return APIResponse(data=TripRead.model_validate(trip), message="Trip started")


@router.post(
    "/trips/{trip_id}/end",
    response_model=APIResponse[TripRead],
    summary="End a trip (OPERATOR only)",
)
def end_trip(
    trip_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: OperatorUser,
) -> APIResponse[TripRead]:
    trip = trip_service.end_trip(db, current_user, trip_id)
    return APIResponse(data=TripRead.model_validate(trip), message="Trip ended")


@router.post(
    "/trips/{trip_id}/location",
    response_model=APIResponse[LocationRead],
    status_code=status.HTTP_201_CREATED,
    summary="Post a location update (OPERATOR only)",
)
def post_location(
    trip_id: UUID,
    payload: LocationUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: OperatorUser,
) -> APIResponse[LocationRead]:
    loc = trip_service.record_location(db, current_user, trip_id, payload)
    return APIResponse(data=LocationRead.model_validate(loc), message="Location recorded")


@router.get(
    "/trips/{trip_id}/location/latest",
    response_model=APIResponse[LocationRead],
    summary="Get latest location for a trip",
)
def latest_location(
    trip_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> APIResponse[LocationRead]:
    loc = trip_service.get_latest_location(db, trip_id)
    freshness = trip_service.get_freshness_status(loc.captured_at, loc.received_at)
    data = LocationRead.model_validate(loc)
    data.freshness_status = freshness
    return APIResponse(data=data)
