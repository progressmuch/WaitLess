"""RouteStop model: one stop of one route, at a specific position.

Field list and constraint follow docs/04-database-specification.md section 6.
"""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RouteStop(Base):
    """Ordered link between a route and a stop (the many-to-many with order)."""

    __tablename__ = "route_stops"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Deliberately not indexed: the unique constraint below starts with
    # route_id, so PostgreSQL already has an index covering route lookups.
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("routes.id"), nullable=False)
    # "Which routes run through this stop?" is queried often (Phase 5 search),
    # so this side does get its own index.
    stop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stops.id"), nullable=False, index=True
    )

    # 1-based position along the route (docs/02 FR-03: ordered stops).
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    # Minutes from the first stop. Optional: a route can be laid out before
    # timing data exists; Phase 6 (ETA) reads it when it is present.
    estimated_minutes_from_start: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    __table_args__ = (
        # One position per route - enforced by the database as well as by the
        # API, so two requests can never claim the same slot.
        UniqueConstraint(
            "route_id",
            "stop_sequence",
            name="uq_route_stops_route_id_stop_sequence",
        ),
    )

    route: Mapped["Route"] = relationship("Route", back_populates="route_stops")
    stop: Mapped["Stop"] = relationship("Stop", back_populates="route_stops")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<RouteStop route_id={self.route_id} stop_id={self.stop_id} "
            f"seq={self.stop_sequence}>"
        )
