"""Route data access and the ordered-stop rules.

Route handlers stay thin: they validate input, call this service and map the
result onto a response schema (docs/09-backend-project-structure.md).

Business rules enforced here (docs/02-product-requirements.md):
* a route must have ordered stops (rule 5) - it can only become active once
  it has at least two of them;
* `routes.code` is unique - a clash becomes a 409 instead of a 500.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import ConflictException, NotFoundException
from app.models.route import Route
from app.models.route_stop import RouteStop
from app.models.stop import Stop
from app.schemas.route import RouteCreate, RouteStopsReplace, RouteUpdate

# A route that cannot carry passengers is not worth showing, so this is the
# minimum number of stops for publication.
MIN_STOPS_PER_ROUTE = 2


def _count_route_stops(db: Session, route_id: UUID) -> int:
    """How many stops the route currently has."""
    return int(
        db.execute(
            select(func.count(RouteStop.id)).where(RouteStop.route_id == route_id)
        ).scalar_one()
    )


def _ensure_stops_exist(db: Session, stop_ids: list[UUID]) -> None:
    """Reject a payload that references stops which do not exist.

    Raises:
        NotFoundException: naming the first unknown stop, rather than letting
            the foreign key fail with an opaque database error.
    """
    unique_ids = list(dict.fromkeys(stop_ids))
    existing = set(
        db.execute(select(Stop.id).where(Stop.id.in_(unique_ids))).scalars()
    )
    for stop_id in unique_ids:
        if stop_id not in existing:
            raise NotFoundException(f"Stop not found: {stop_id}")


def list_routes(db: Session, is_active: Optional[bool] = None) -> list[Route]:
    """Return routes, active ones by default (docs/05 section 3).

    Args:
        is_active: True/False filters explicitly; None (the default) returns
            only the published routes commuters should see.
    """
    statement = select(Route)
    if is_active is None:
        statement = statement.where(Route.is_active.is_(True))
    else:
        statement = statement.where(Route.is_active.is_(is_active))
    return db.execute(statement.order_by(Route.code)).scalars().all()


def get_route_or_404(db: Session, route_id: UUID) -> Route:
    """Return the route with this id or raise a 404 (stops not loaded)."""
    route = db.get(Route, route_id)
    if route is None:
        raise NotFoundException("Route not found")
    return route


def get_route_detail(db: Session, route_id: UUID) -> Route:
    """Return the route with its ordered stops and their stop data already loaded.

    One `selectinload` for the stops plus a `joinedload` for each stop avoids
    the N+1 queries that lazy loading would produce.
    """
    statement = (
        select(Route)
        .where(Route.id == route_id)
        .options(
            selectinload(Route.route_stops).joinedload(RouteStop.stop),
        )
    )
    route = db.execute(statement).scalar_one_or_none()
    if route is None:
        raise NotFoundException("Route not found")
    return route


def create_route(db: Session, payload: RouteCreate) -> Route:
    """Create a route, together with its stops when they are supplied.

    A route created with stops starts active (it is publishable immediately);
    one created without them starts as a draft and can only be activated later
    once it has at least two stops.

    Raises:
        ConflictException: if the route code is already in use.
        NotFoundException: if a referenced stop does not exist.
    """
    stop_items = payload.stops or []
    if stop_items:
        _ensure_stops_exist(db, [item.stop_id for item in stop_items])

    route = Route(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        is_active=bool(stop_items),
    )
    db.add(route)
    try:
        # Flush first: it assigns route.id for the stops below and surfaces a
        # duplicate code as an IntegrityError here, where the message is known.
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictException("Route code is already in use") from exc

    for position, item in enumerate(stop_items, start=1):
        db.add(
            RouteStop(
                route_id=route.id,
                stop_id=item.stop_id,
                stop_sequence=position,
                estimated_minutes_from_start=item.estimated_minutes_from_start,
            )
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictException("Route could not be saved") from exc
    db.refresh(route)
    return route


def update_route(db: Session, route_id: UUID, payload: RouteUpdate) -> Route:
    """Apply a partial update to a route.

    Raises:
        NotFoundException: if the route does not exist.
        ConflictException: if the route is activated without stops, or if the
            new code is already taken.
    """
    route = get_route_or_404(db, route_id)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("is_active") is True and _count_route_stops(db, route_id) < MIN_STOPS_PER_ROUTE:
        raise ConflictException(
            "Route needs at least two stops before it can be activated"
        )

    for field_name, value in changes.items():
        setattr(route, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictException("Route code is already in use") from exc
    db.refresh(route)
    return route


def replace_route_stops(
    db: Session, route_id: UUID, payload: RouteStopsReplace
) -> Route:
    """Replace the whole ordered stop list of a route in one transaction.

    Replacing (rather than inserting and deleting individual entries) keeps
    `stop_sequence` gap-free by construction and leaves no half-updated state
    behind if something fails.

    Returns:
        The route with its new stops already loaded.

    Raises:
        NotFoundException: if the route or any referenced stop does not exist.
    """
    get_route_or_404(db, route_id)
    _ensure_stops_exist(db, [item.stop_id for item in payload.stops])

    db.execute(delete(RouteStop).where(RouteStop.route_id == route_id))
    for position, item in enumerate(payload.stops, start=1):
        db.add(
            RouteStop(
                route_id=route_id,
                stop_id=item.stop_id,
                stop_sequence=position,
                estimated_minutes_from_start=item.estimated_minutes_from_start,
            )
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictException("Route stops could not be saved") from exc

    return get_route_detail(db, route_id)
