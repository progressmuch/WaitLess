"""Trip service logic for Phase 4."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.bus import Bus
from app.models.bus_location import BusLocation
from app.models.operator_assignment import OperatorAssignment
from app.models.route import Route
from app.models.trip import Trip, TripStatus
from app.models.user import User
from app.schemas.trip import LocationUpdateRequest, TripStartRequest


LOCATION_FRESHNESS_TARGET_MINUTES = 20


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_freshness_status(captured_at: datetime, received_at: datetime) -> str:
    # Treat naive as UTC to be safe.
    def to_utc(dt: datetime) -> datetime:
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

    cap = to_utc(captured_at)
    rec = to_utc(received_at)
    delta = (rec - cap).total_seconds()
    if delta < 0:
        delta = 0
    minutes = delta / 60
    target = LOCATION_FRESHNESS_TARGET_MINUTES
    if minutes <= target:
        return "fresh"
    if minutes <= target * 2:
        return "stale"
    return "very_stale"


def get_active_trip_by_id(db: Session, trip_id: UUID) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None or trip.status != TripStatus.ACTIVE:
        raise NotFoundException("Active trip not found")
    return trip


def list_active_trips(db: Session, route_id: Optional[UUID] = None) -> list[Trip]:
    statement = select(Trip).where(Trip.status == TripStatus.ACTIVE)
    if route_id is not None:
        statement = statement.where(Trip.route_id == route_id)
    return db.execute(statement.order_by(Trip.started_at)).scalars().all()


def _get_active_assignment_for_operator(db: Session, operator_id: UUID) -> OperatorAssignment:
    assignment = (
        db.execute(
            select(OperatorAssignment)
            .where(
                OperatorAssignment.operator_id == operator_id,
                OperatorAssignment.is_active.is_(True),
            )
        )
        .scalar_one_or_none()
    )
    if assignment is None:
        raise ConflictException("Operator has no active assignment")
    return assignment


def start_trip(db: Session, operator: User, payload: TripStartRequest) -> Trip:
    bus = db.get(Bus, payload.bus_id)
    if bus is None:
        raise NotFoundException("Bus not found")
    if not bus.is_active:
        raise ConflictException("Bus is not active")
    route = db.get(Route, payload.route_id)
    if route is None:
        raise NotFoundException("Route not found")
    if not route.is_active:
        raise ConflictException("Route is not active")

    assignment = _get_active_assignment_for_operator(db, operator.id)
    if assignment.bus_id != payload.bus_id:
        raise ForbiddenException("Operator is not assigned to this bus")

    # Only one active trip per bus/operator at a time.
    existing_bus_trip = (
        db.execute(
            select(Trip).where(
                Trip.bus_id == payload.bus_id,
                Trip.status == TripStatus.ACTIVE,
            )
        )
        .scalar_one_or_none()
    )
    if existing_bus_trip is not None:
        raise ConflictException("Bus already has an active trip")

    existing_op_trip = (
        db.execute(
            select(Trip).where(
                Trip.operator_id == operator.id,
                Trip.status == TripStatus.ACTIVE,
            )
        )
        .scalar_one_or_none()
    )
    if existing_op_trip is not None:
        raise ConflictException("Operator already has an active trip")

    trip = Trip(
        bus_id=payload.bus_id,
        operator_id=operator.id,
        route_id=payload.route_id,
        status=TripStatus.ACTIVE,
        started_at=utcnow(),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def end_trip(db: Session, operator: User, trip_id: UUID) -> Trip:
    trip = get_active_trip_by_id(db, trip_id)
    if trip.operator_id != operator.id:
        raise ForbiddenException("Operator does not control this trip")
    trip.status = TripStatus.COMPLETED
    trip.ended_at = utcnow()
    db.commit()
    db.refresh(trip)
    return trip


def record_location(db: Session, operator: User, trip_id: UUID, payload: LocationUpdateRequest) -> BusLocation:
    trip = get_active_trip_by_id(db, trip_id)
    if trip.operator_id != operator.id:
        raise ForbiddenException("Operator does not control this trip")
    if trip.bus_id is None:
        pass

    captured_at = payload.captured_at or utcnow()

    loc = BusLocation(
        trip_id=trip.id,
        bus_id=trip.bus_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.speed,
        heading=payload.heading,
        captured_at=captured_at,
        received_at=utcnow(),
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


def get_latest_location(db: Session, trip_id: UUID) -> BusLocation:
    loc = (
        db.execute(
            select(BusLocation)
                .where(BusLocation.trip_id == trip_id)
                .order_by(BusLocation.received_at.desc(), BusLocation.id.desc())
        )
        .scalars()
        .first()
    )
    if loc is None:
        raise NotFoundException("No location recorded for this trip")
    return loc
