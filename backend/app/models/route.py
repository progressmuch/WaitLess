"""Route model: a named, ordered sequence of stops.

Field list follows docs/04-database-specification.md section 4.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Route(Base):
    """A named transport route, for example "Harare - Chitungwiza"."""

    __tablename__ = "routes"

    # Business entities use UUIDs (docs/04-database-specification.md section 14).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Short machine-friendly identifier, stored upper-cased by the schema layer
    # so that "r1" and "R1" cannot both exist.
    code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # A route is only useful once it has its ordered stops (docs/02 business
    # rule 5), so it starts inactive. The service activates it when stops are
    # supplied, and re-activation through PATCH is refused while stops are
    # missing.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
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

    # Stops in stop_sequence order. Kept lazy: the list endpoint does not
    # return stops, so loading them for every listed route would be wasted
    # work; the detail endpoint loads them explicitly through selectinload.
    route_stops: Mapped[list["RouteStop"]] = relationship(
        "RouteStop", back_populates="route", order_by="RouteStop.stop_sequence"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Route id={self.id} code={self.code} is_active={self.is_active}>"
