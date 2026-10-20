"""Operator assignment endpoints (docs/05-api-specification.md section 6).

| Endpoint                                    | Auth required | Role required |
|---------------------------------------------|---------------|---------------|
| POST   /operators/{operator_email}/assignments | yes        | MANAGEMENT    |
| GET    /operators/me/assignment             | yes           | OPERATOR      |
| DELETE /operators/{operator_email}/assignments | yes        | MANAGEMENT    |

Management identifies the operator by email, not UUID, so an operator can be
assigned or released without first looking up a user id (the backend has no
user-list endpoint, docs/12 GAP-16).

DELETE does not remove anything: it ends the running assignment (`ended_at`
set, `is_active: false`) and keeps the row as history. It exists so the 409
POST answers ("operator already has an active assignment") has an explicit way
out - management ends the old assignment, then assigns a new bus.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import APIResponse
from app.schemas.operator_assignment import (
    OperatorAssignmentCreate,
    OperatorAssignmentRead,
)
from app.services import assignment_service

router = APIRouter(tags=["operators"])

ManagementUser = Annotated[User, Depends(require_roles(UserRole.MANAGEMENT))]
OperatorUser = Annotated[User, Depends(require_roles(UserRole.OPERATOR))]


@router.post(
    "/operators/{operator_email}/assignments",
    response_model=APIResponse[OperatorAssignmentRead],
    status_code=status.HTTP_201_CREATED,
    summary="Assign a bus to an operator by email (MANAGEMENT only)",
)
def create_assignment(
    operator_email: str,
    payload: OperatorAssignmentCreate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[OperatorAssignmentRead]:
    """Hand a bus to an operator, returning the bus and its route.

    The operator is identified by their email address. 404 if the operator or
    the bus is unknown. 409 if the target user is not an OPERATOR, if that
    operator already has an active assignment, or if the bus already has an
    active driver.
    """
    assignment = assignment_service.create_assignment(db, operator_email, payload)
    return APIResponse(
        data=OperatorAssignmentRead.model_validate(assignment),
        message="Bus assigned successfully",
    )


@router.get(
    "/operators/me/assignment",
    response_model=APIResponse[OperatorAssignmentRead],
    summary="Return my active assignment (OPERATOR only)",
)
def get_my_assignment(
    db: Annotated[Session, Depends(get_db)],
    current_user: OperatorUser,
) -> APIResponse[OperatorAssignmentRead]:
    """Return the caller's assignment with its bus and that bus's route.

    404 when the operator has no active assignment.
    """
    assignment = assignment_service.get_active_assignment_or_404(
        db, current_user.id
    )
    return APIResponse(data=OperatorAssignmentRead.model_validate(assignment))


@router.delete(
    "/operators/{operator_email}/assignments",
    response_model=APIResponse[OperatorAssignmentRead],
    summary="End the operator's active assignment by email (MANAGEMENT only)",
)
def end_assignment(
    operator_email: str,
    db: Annotated[Session, Depends(get_db)],
    _current_user: ManagementUser,
) -> APIResponse[OperatorAssignmentRead]:
    """End the running assignment, which stays as history.

    The operator is identified by their email address. 404 if the operator is
    unknown or has no active assignment to end.
    """
    assignment = assignment_service.end_assignment(db, operator_email)
    return APIResponse(
        data=OperatorAssignmentRead.model_validate(assignment),
        message="Operator assignment ended",
    )
