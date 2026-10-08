"""Journey search model for analytics (Phase 7)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class JourneySearch(Base):
    __tablename__ = "journey_searches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    commuter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    origin_stop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stops.id"), nullable=False
    )
    destination_stop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stops.id"), nullable=False
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("routes.id"), nullable=True
    )
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
