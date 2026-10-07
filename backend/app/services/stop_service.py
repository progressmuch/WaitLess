"""Stop data access and update rules.

Route handlers stay thin: they validate input, call this service and map the
result onto a response schema (docs/09-backend-project-structure.md).
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.stop import Stop
from app.schemas.stop import StopCreate, StopUpdate


def _to_decimal(value: float) -> Decimal:
    """Convert a validated float into the exact decimal the column expects.

    `Decimal(str(...))` keeps the value the client typed (17.8252 stays
    17.8252) instead of carrying the binary float artefacts of `Decimal(17.8252)`.
    """
    return Decimal(str(value))


def list_stops(db: Session, is_active: Optional[bool] = None) -> list[Stop]:
    """Return stops, active ones by default (docs/05 section 4).

    Args:
        is_active: True/False filters explicitly; None (the default) returns
            only active stops, which is what commuters should see.
    """
    statement = select(Stop)
    if is_active is None:
        statement = statement.where(Stop.is_active.is_(True))
    else:
        statement = statement.where(Stop.is_active.is_(is_active))
    return db.execute(statement.order_by(Stop.name)).scalars().all()


def get_stop_or_404(db: Session, stop_id: UUID) -> Stop:
    """Return the stop with this id or raise a 404."""
    stop = db.get(Stop, stop_id)
    if stop is None:
        raise NotFoundException("Stop not found")
    return stop


def create_stop(db: Session, payload: StopCreate) -> Stop:
    """Create and persist a stop.

    Stops have no unique columns, so unlike routes or users there is no
    conflict case to translate into a 409.
    """
    stop = Stop(
        name=payload.name,
        latitude=_to_decimal(payload.latitude),
        longitude=_to_decimal(payload.longitude),
        is_active=True,
    )
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return stop


def update_stop(db: Session, stop_id: UUID, payload: StopUpdate) -> Stop:
    """Apply a partial update to a stop.

    Raises:
        NotFoundException: if the stop does not exist.
    """
    stop = get_stop_or_404(db, stop_id)

    # Only the fields the client actually sent are applied, so a PATCH with
    # `{"is_active": false}` leaves every other column untouched.
    changes = payload.model_dump(exclude_unset=True)
    for coordinate in ("latitude", "longitude"):
        if coordinate in changes:
            changes[coordinate] = _to_decimal(changes[coordinate])

    for field_name, value in changes.items():
        setattr(stop, field_name, value)

    db.commit()
    db.refresh(stop)
    return stop
