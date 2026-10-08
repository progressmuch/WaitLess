"""Trip model: an active journey a bus is running on a route.

Field list follows docs/04-database-specification.md section 10.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TripStatus:
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Trip(Base):
    """A journey operated by an operator on a bus along a route."""

    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    bus_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("buses.id"), nullable=False, index=True
    )
    operator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routes.id"), nullable=False, index=True
    )

    # The only states the API ever produces for now are ACTIVE and COMPLETED.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TripStatus.ACTIVE
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # A bus must not have more than one active trip (docs/04 section 10).
        Index(
            "ix_trips_bus_active",
            "bus_id",
            unique=True,
            postgresql_where=(status == TripStatus.ACTIVE),
        ),
        Index(
            "ix_trips_operator_active",
            "operator_id",
            unique=True,
            postgresql_where=(status == TripStatus.ACTIVE),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Trip id={self.id} bus_id={self.bus_id} status={self.status}>"
