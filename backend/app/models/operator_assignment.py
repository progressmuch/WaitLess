"""OperatorAssignment model.

Field list follows docs/04-database-specification.md section 8. The table has
no created_at/updated_at columns: `assigned_at` records when the assignment
started and `ended_at` when it finished.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class OperatorAssignment(Base):
    """Hands a bus to an operator for a period of time."""

    __tablename__ = "operator_assignments"

    # The API answers 409 when an operator already has an active assignment or
    # when a bus already has an active driver (docs/05 section 6). These
    # partial unique indexes back those rules at the database level, so two
    # racing requests can never both succeed.
    __table_args__ = (
        Index(
            "uq_operator_assignments_active_operator",
            "operator_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "uq_operator_assignments_active_bus",
            "bus_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    # Business entities use UUIDs (docs/04-database-specification.md section 14).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Indexed: `GET /operators/me/assignment` looks the row up by operator.
    operator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    # Indexed: "does this bus already have a driver?" is checked on every
    # assignment request.
    bus_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("buses.id"), nullable=False, index=True
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Set when the assignment ends; null while it is still running.
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    # The bus (and through it, the route) is what the operator needs to see.
    bus: Mapped["Bus"] = relationship("Bus")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<OperatorAssignment operator_id={self.operator_id} "
            f"bus_id={self.bus_id} is_active={self.is_active}>"
        )
