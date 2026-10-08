"""Fare data access and the fare rules.

Route handlers stay thin: they validate input, call this service and map the
result onto a response schema (docs/09-backend-project-structure.md).

Business rules enforced here (docs/02-product-requirements.md):
* rule 6 - a fare always applies to a defined journey: its route must exist
  and both of its stops must actually belong to that route, and the two ends
  must differ (the last one is checked by the schema layer);
* rule 7 - historical fares are never destroyed or edited. A price change is
  a *new* fare that supersedes the old one: the old row keeps its amount and
  gets `effective_to` set to the moment the new price starts.

Applicability
-------------
A fare applies right now when `is_active` is true and `now` falls inside its
window `[effective_from, effective_to)` (`effective_to` NULL = open ended).
The list and search endpoints return exactly those fares unless the caller
asks for the history.

Windows of one journey never overlap: `create_fare` closes the fare it
supersedes, and `update_fare` refuses a change that would make two active
fares cover the same moment.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, CustomException, NotFoundException
from app.models.fare import Fare
from app.models.route import Route
from app.models.route_stop import RouteStop
from app.models.stop import Stop
from app.schemas.fare import FareCreate, FareUpdate


def utcnow() -> datetime:
    """Current UTC time - every stored fare timestamp is timezone-aware."""
    return datetime.now(timezone.utc)


def _applicable_now(clause_time: datetime):
    """SQL clause: the fare applies at `clause_time`."""
    return (
        Fare.is_active.is_(True),
        Fare.effective_from <= clause_time,
        or_(Fare.effective_to.is_(None), Fare.effective_to > clause_time),
    )


def _context_clause(route_id: UUID, origin_stop_id: UUID, destination_stop_id: UUID):
    """SQL clause: fares for one journey (rule 6's route/stop triple)."""
    return (
        Fare.route_id == route_id,
        Fare.origin_stop_id == origin_stop_id,
        Fare.destination_stop_id == destination_stop_id,
    )


def _ensure_stops_exist(db: Session, *stop_ids: UUID) -> None:
    """Reject unknown stop ids with a 404 instead of an opaque database error."""
    wanted = list(dict.fromkeys(stop_ids))
    existing = set(db.execute(select(Stop.id).where(Stop.id.in_(wanted))).scalars())
    for stop_id in wanted:
        if stop_id not in existing:
            raise NotFoundException(f"Stop not found: {stop_id}")


def _ensure_journey_context(
    db: Session, route_id: UUID, origin_stop_id: UUID, destination_stop_id: UUID
) -> None:
    """Check that the payload describes a journey that really exists.

    Raises:
        NotFoundException: the route or one of the stops does not exist.
        CustomException (422): both stops exist but not on this route - the
            payload is well formed yet impossible, which is what 422 is for.
    """
    route = db.get(Route, route_id)
    if route is None:
        raise NotFoundException("Route not found")

    _ensure_stops_exist(db, origin_stop_id, destination_stop_id)

    route_stops = set(
        db.execute(
            select(RouteStop.stop_id).where(RouteStop.route_id == route_id)
        ).scalars()
    )
    if origin_stop_id not in route_stops:
        raise CustomException(
            f"Origin stop is not on route {route.code}",
            status_code=422,
        )
    if destination_stop_id not in route_stops:
        raise CustomException(
            f"Destination stop is not on route {route.code}",
            status_code=422,
        )


def list_fares(
    db: Session,
    *,
    route_id: Optional[UUID] = None,
    origin_stop_id: Optional[UUID] = None,
    destination_stop_id: Optional[UUID] = None,
    include_history: bool = False,
) -> list[Fare]:
    """Return fares, the applicable ones by default (docs/05 section 7).

    Args:
        route_id: keep only fares of this route.
        origin_stop_id: keep only fares starting at this stop.
        destination_stop_id: keep only fares ending at this stop.
        include_history: True returns every fare, including superseded,
            expired and deactivated ones - this is how management reads the
            fare history (docs/02 FR-08). False (the default) returns only
            the fares that apply right now, which is what a commuter wants.
    """
    statement = select(Fare)
    if route_id is not None:
        statement = statement.where(Fare.route_id == route_id)
    if origin_stop_id is not None:
        statement = statement.where(Fare.origin_stop_id == origin_stop_id)
    if destination_stop_id is not None:
        statement = statement.where(Fare.destination_stop_id == destination_stop_id)

    if not include_history:
        statement = statement.where(*_applicable_now(utcnow()))

    # Newest price first; `created_at` breaks ties so the newest row of a
    # superseding pair comes before the one it replaced.
    return (
        db.execute(statement.order_by(Fare.effective_from.desc(), Fare.created_at.desc()))
        .scalars()
        .all()
    )


def get_fare_or_404(db: Session, fare_id: UUID) -> Fare:
    """Return the fare with this id or raise a 404."""
    fare = db.get(Fare, fare_id)
    if fare is None:
        raise NotFoundException("Fare not found")
    return fare


def search_fares(
    db: Session,
    *,
    origin_stop_id: UUID,
    destination_stop_id: UUID,
    route_id: Optional[UUID] = None,
) -> list[Fare]:
    """Return the fares that apply to one origin/destination pair right now.

    Used by the commuter before picking a journey (docs/05 section 7). An
    empty list simply means no fare is configured yet for that pair - not an
    error, because the stops themselves may be perfectly valid.

    Raises:
        CustomException (422): origin and destination are the same stop, so
            there is no journey to price.
        NotFoundException: an unknown stop id (or route id, when given) is a
            mistyped query, not "no fares".
    """
    if origin_stop_id == destination_stop_id:
        raise CustomException(
            "Origin and destination stops must be different", status_code=422
        )
    _ensure_stops_exist(db, origin_stop_id, destination_stop_id)
    if route_id is not None and db.get(Route, route_id) is None:
        raise NotFoundException("Route not found")

    statement = select(Fare).where(
        Fare.origin_stop_id == origin_stop_id,
        Fare.destination_stop_id == destination_stop_id,
        *_applicable_now(utcnow()),
    )
    if route_id is not None:
        statement = statement.where(Fare.route_id == route_id)

    return (
        db.execute(statement.order_by(Fare.effective_from.desc(), Fare.created_at.desc()))
        .scalars()
        .all()
    )


def create_fare(db: Session, payload: FareCreate) -> Fare:
    """Add the fare that will be in effect from `effective_from` onwards.

    When the journey already has an active fare, the new one *supersedes* it
    instead of overwriting it (docs/02 rule 7):

    * the fare whose window still covers the start of the new one is closed
      there - it becomes history with `effective_to = effective_from` of the
      new fare;
    * a fare already scheduled to start later caps the new one, so the new
      price stops applying the moment the later one begins.

    Both directions keep the windows of a journey disjoint, so "the current
    fare" is always a single row.

    Raises:
        NotFoundException: unknown route or stop.
        CustomException (422): the stops are not on the route.
        ConflictException: another active fare of the same journey already
            starts at exactly the same moment.
    """
    _ensure_journey_context(
        db, payload.route_id, payload.origin_stop_id, payload.destination_stop_id
    )

    effective_from = payload.effective_from or utcnow()

    active = (
        db.execute(
            select(Fare)
            .where(
                *_context_clause(
                    payload.route_id,
                    payload.origin_stop_id,
                    payload.destination_stop_id,
                ),
                Fare.is_active.is_(True),
            )
            .order_by(Fare.effective_from)
        )
        .scalars()
        .all()
    )

    effective_to = None
    for existing in active:
        if existing.effective_from == effective_from:
            raise ConflictException(
                "A fare for this journey already starts at that time"
            )

        # Still in force when the new fare starts -> close it right there.
        covers_new_start = existing.effective_from < effective_from and (
            existing.effective_to is None or existing.effective_to > effective_from
        )
        if covers_new_start:
            existing.effective_to = effective_from

        # Starting later -> the new fare must not run past it.
        if existing.effective_from > effective_from and (
            effective_to is None or existing.effective_from < effective_to
        ):
            effective_to = existing.effective_from

    fare = Fare(
        route_id=payload.route_id,
        origin_stop_id=payload.origin_stop_id,
        destination_stop_id=payload.destination_stop_id,
        amount=payload.amount,
        currency=payload.currency,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    db.add(fare)
    db.commit()
    db.refresh(fare)
    return fare


def _assert_window_free(db: Session, fare: Fare, effective_to: Optional[datetime]) -> None:
    """Refuse to let `fare` cover a moment another active fare already covers.

    Args:
        effective_to: the window end the fare would have after the update
            (None = open ended).

    Raises:
        ConflictException: another active fare of the same journey overlaps
            the window `[fare.effective_from, effective_to)`.
    """
    others = (
        db.execute(
            select(Fare)
            .where(
                *_context_clause(fare.route_id, fare.origin_stop_id, fare.destination_stop_id),
                Fare.is_active.is_(True),
                Fare.id != fare.id,
            )
            .order_by(Fare.effective_from)
        )
        .scalars()
        .all()
    )
    for other in others:
        new_starts_before_other_ends = (
            other.effective_to is None or fare.effective_from < other.effective_to
        )
        other_starts_before_new_ends = (
            effective_to is None or other.effective_from < effective_to
        )
        if new_starts_before_other_ends and other_starts_before_new_ends:
            raise ConflictException(
                "Another fare for this journey already covers that period"
            )


def update_fare(db: Session, fare_id: UUID, payload: FareUpdate) -> Fare:
    """Apply a lifecycle change to a fare.

    Only `is_active` and `effective_to` may change: the amount and currency
    belong to the moment the fare was configured and are never rewritten
    (docs/02 rule 7). The price itself changes through `create_fare`.

    Raises:
        NotFoundException: if the fare does not exist.
        CustomException (422): `effective_to` is not after `effective_from`.
        ConflictException: re-activating or re-opening the fare would make it
            overlap another active fare of the same journey.
    """
    fare = get_fare_or_404(db, fare_id)
    changes = payload.model_dump(exclude_unset=True)

    if "effective_to" in changes:
        new_end = changes["effective_to"]
        if new_end is not None and new_end <= fare.effective_from:
            raise CustomException(
                "effective_to must be after effective_from", status_code=422
            )
    else:
        new_end = fare.effective_to

    will_be_active = changes.get("is_active", fare.is_active)
    if will_be_active:
        _assert_window_free(db, fare, new_end)

    for field_name, value in changes.items():
        setattr(fare, field_name, value)

    db.commit()
    db.refresh(fare)
    return fare
