"""Operator assignment rules (docs/05-api-specification.md section 6).

Business rules enforced here (docs/02 FR-04 "assign bus to route"):
* only users with role OPERATOR may be assigned to a bus;
* an operator has at most one active assignment;
* a bus has at most one active driver;
* assignments are ended, never deleted - the record stays as history.

The two "at most one active" rules are also partial unique indexes (migration
0d6cf8f316be), so even racing requests cannot both win; the checks here simply
turn each case into a clear 409 first.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictException, NotFoundException
from app.models.bus import Bus
from app.models.operator_assignment import OperatorAssignment
from app.models.user import User, UserRole
from app.schemas.operator_assignment import OperatorAssignmentCreate
from app.services import bus_service, user_service


def get_active_assignment(
    db: Session, operator_id: UUID
) -> OperatorAssignment | None:
    """The operator's running assignment, with bus and route already loaded.

    One `joinedload` for the bus plus one for its route avoids the N+1 queries
    that lazy loading would produce when the response is built.
    """
    return db.execute(
        select(OperatorAssignment)
        .where(OperatorAssignment.operator_id == operator_id)
        .where(OperatorAssignment.is_active.is_(True))
        .options(joinedload(OperatorAssignment.bus).joinedload(Bus.route))
    ).scalar_one_or_none()


def get_active_assignment_or_404(
    db: Session, operator_id: UUID
) -> OperatorAssignment:
    """Return the running assignment or raise a 404."""
    assignment = get_active_assignment(db, operator_id)
    if assignment is None:
        raise NotFoundException("Operator has no active assignment")
    return assignment


def _get_active_driver(db: Session, bus_id: UUID) -> OperatorAssignment | None:
    """The assignment that currently puts someone in this bus, if any."""
    return db.execute(
        select(OperatorAssignment)
        .where(OperatorAssignment.bus_id == bus_id)
        .where(OperatorAssignment.is_active.is_(True))
    ).scalar_one_or_none()


def _ensure_operator_is_free(db: Session, operator_id: UUID) -> None:
    if get_active_assignment(db, operator_id) is not None:
        raise ConflictException("Operator already has an active assignment")


def create_assignment(
    db: Session, operator_id: UUID, payload: OperatorAssignmentCreate
) -> OperatorAssignment:
    """Hand a bus to an operator (MANAGEMENT only).

    Raises:
        NotFoundException: if the operator or the bus does not exist.
        ConflictException: if the target user is not an OPERATOR, if the
            operator already has an active assignment, or if the bus already
            has a driver.
    """
    operator: User = user_service.get_user_or_404(db, operator_id)
    if operator.role != UserRole.OPERATOR:
        raise ConflictException("Only users with role OPERATOR can be assigned")

    bus = bus_service.get_bus_or_404(db, payload.bus_id)

    _ensure_operator_is_free(db, operator_id)
    if _get_active_driver(db, bus.id) is not None:
        raise ConflictException("Bus already has an active operator assignment")

    assignment = OperatorAssignment(
        operator_id=operator.id,
        bus_id=bus.id,
        is_active=True,
    )
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError as exc:
        # A racing request won one of the two partial unique indexes.
        db.rollback()
        raise ConflictException(
            "Operator or bus already has an active assignment"
        ) from exc
    # Re-read it with bus and route loaded, ready for the response schema.
    return get_active_assignment(db, assignment.operator_id)


def end_assignment(db: Session, operator_id: UUID) -> OperatorAssignment:
    """End the operator's active assignment, keeping it as history.

    This is the explicit action that resolves the 409 returned by POST:
    management ends the running assignment first, then assigns a new bus.

    Raises:
        NotFoundException: if the operator has no active assignment.
    """
    assignment = get_active_assignment_or_404(db, operator_id)
    assignment.is_active = False
    assignment.ended_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError as exc:  # pragma: no cover - constraints only relax here
        db.rollback()
        raise ConflictException("Assignment could not be ended") from exc
    db.refresh(assignment)
    return assignment
