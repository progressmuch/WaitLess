"""BusLocation model: location samples sent by the operator for an active trip.

Field list follows docs/04-database-specification.md section 11.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BusLocation(Base):
    """One GPS location fix for a trip/bus at a point in time."""

    __tablename__ = "bus_locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    trip_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trips.id"), nullable=False, index=True
    )
    bus_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("buses.id"), nullable=False, index=True
    )

    # WGS84 degrees. The schema layer validates ranges before insert.
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)

    speed: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    heading: Mapped[Optional[int]] = mapped_column(Numeric(3, 0), nullable=True)

    # The moment the device captured the fix.
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # The moment the backend received and stored it.
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Latest location per bus/trip queries (Phase 5 and here).
        Index("ix_bus_locations_bus_received_at", "bus_id", "received_at", unique=False),
        Index("ix_bus_locations_trip_received_at", "trip_id", "received_at", unique=False),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<BusLocation trip_id={self.trip_id} bus_id={self.bus_id}>"
