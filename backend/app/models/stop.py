"""Stop model: a physical boarding point.

Field list follows docs/04-database-specification.md section 5.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Stop(Base):
    """A named location where passengers get on or off a bus."""

    __tablename__ = "stops"

    # Business entities use UUIDs (docs/04-database-specification.md section 14).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # WGS84 degrees. The schema layer (app/schemas) rejects values outside
    # -90..90 / -180..180 before they ever reach the database.
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)

    # Deactivated stops are kept in the database because route_stops and fares
    # still reference them; they simply disappear from the public stop list.
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

    # Every route position that uses this stop; the ordering lives on RouteStop.
    route_stops: Mapped[list["RouteStop"]] = relationship(
        "RouteStop", back_populates="stop"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Stop id={self.id} name={self.name}>"
