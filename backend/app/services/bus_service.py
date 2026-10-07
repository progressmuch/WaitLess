"""Bus data access and fleet rules (docs/05-api-specification.md section 5).

Bus handlers stay thin: they validate input, call this service and map the
result onto a response schema (docs/09-backend-project-structure.md).

Business rules enforced here:
* `registration_number` and `fleet_number` are unique - a clash becomes a 409
  instead of a 500;
* a bus runs at most one route at a time (`buses.route_id`), and that route
  must exist;
* buses are never deleted, they are deactivated.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictException, NotFoundException
from app.models.bus import Bus
from app.models.route import Route
from app.schemas.bus import BusCreate, BusUpdate


def _ensure_identifiers_free(
    db: Session, registration_number: str, fleet_number: str
) -> None:
    """Reject a duplicate plate or fleet number before the insert.

    Checking up front lets the 409 say which number is taken; the unique
    indexes still back the rule if two requests race past this check.
    """
    if db.execute(
        select(Bus.id).where(Bus.registration_number == registration_number)
    ).first():
        raise ConflictException(
            f"Registration number is already in use: {registration_number}"
        )
    if db.execute(select(Bus.id).where(Bus.fleet_number == fleet_number)).first():
        raise ConflictException(f"Fleet number is already in use: {fleet_number}")


def _ensure_route_exists(db: Session, route_id: UUID) -> None:
    """Reject an assignment to a route that does not exist.

    Raises:
        NotFoundException: naming the unknown route, rather than letting the
            foreign key fail with an opaque database error.
    """
    if db.get(Route, route_id) is None:
        raise NotFoundException(f"Route not found: {route_id}")


def list_buses(db: Session, is_active: Optional[bool] = None) -> list[Bus]:
    """Return buses, active ones by default (docs/05 section 5).

    Args:
        is_active: True/False filters explicitly; None (the default) returns
            only the buses still in service.
    """
    statement = select(Bus)
    if is_active is None:
        statement = statement.where(Bus.is_active.is_(True))
    else:
        statement = statement.where(Bus.is_active.is_(is_active))
    return db.execute(statement.order_by(Bus.fleet_number)).scalars().all()


def get_bus_or_404(db: Session, bus_id: UUID) -> Bus:
    """Return the bus with this id or raise a 404 (route not loaded)."""
    bus = db.get(Bus, bus_id)
    if bus is None:
        raise NotFoundException("Bus not found")
    return bus


def create_bus(db: Session, payload: BusCreate) -> Bus:
    """Register a bus, optionally already assigned to a route.

    Raises:
        ConflictException: if the registration or fleet number is taken.
        NotFoundException: if `route_id` points at an unknown route.
    """
    if payload.route_id is not None:
        _ensure_route_exists(db, payload.route_id)
    _ensure_identifiers_free(db, payload.registration_number, payload.fleet_number)

    bus = Bus(
        registration_number=payload.registration_number,
        fleet_number=payload.fleet_number,
        capacity=payload.capacity,
        route_id=payload.route_id,
    )
    db.add(bus)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictException(
            "Registration number or fleet number is already in use"
        ) from exc
    db.refresh(bus)
    return bus


def update_bus(db: Session, bus_id: UUID, payload: BusUpdate) -> Bus:
    """Apply a partial update to a bus.

    `route_id: null` clears the route assignment, `route_id: <uuid>` sets it.

    Raises:
        NotFoundException: if the bus (or the new route) does not exist.
        ConflictException: if the new registration or fleet number is taken.
    """
    bus = get_bus_or_404(db, bus_id)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("route_id") is not None:
        _ensure_route_exists(db, changes["route_id"])

    registration = changes.get("registration_number")
    if registration is not None and registration != bus.registration_number:
        if db.execute(
            select(Bus.id).where(Bus.registration_number == registration)
        ).first():
            raise ConflictException(
                f"Registration number is already in use: {registration}"
            )

    fleet_number = changes.get("fleet_number")
    if fleet_number is not None and fleet_number != bus.fleet_number:
        if db.execute(
            select(Bus.id).where(Bus.fleet_number == fleet_number)
        ).first():
            raise ConflictException(f"Fleet number is already in use: {fleet_number}")

    for field_name, value in changes.items():
        setattr(bus, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictException(
            "Registration number or fleet number is already in use"
        ) from exc
    db.refresh(bus)
    return bus
