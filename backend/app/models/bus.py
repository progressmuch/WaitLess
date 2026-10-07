"""Bus model.

Field list follows docs/04-database-specification.md section 7.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Bus(Base):
    """A physical bus in the fleet."""

    __tablename__ = "buses"

    # Business entities use UUIDs (docs/04-database-specification.md section 14).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Upper-cased by the schema layer; unique so a plate appears only once.
    registration_number: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    fleet_number: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    # Passenger seats; the schema layer requires at least one.
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    # The route this bus currently runs (docs/02 FR-04 "assign bus to route").
    # Null means "not assigned yet". Indexed because Phase 5 looks up the
    # buses serving a route.
    route_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("routes.id"), nullable=True, index=True
    )

    # Deactivated buses stay in the database (assignments and trips reference
    # them) but disappear from the public picture.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # The route the bus runs; loaded explicitly when a response needs it.
    route: Mapped[Optional["Route"]] = relationship("Route")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Bus id={self.id} registration_number={self.registration_number} "
            f"route_id={self.route_id}>"
        )
