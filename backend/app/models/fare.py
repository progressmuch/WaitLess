"""Fare model: the price of a journey between two stops on one route.

Field list follows docs/04-database-specification.md section 9.

A fare row is a price for a *period*, not a mutable price tag: when the price
changes, `POST /fares` inserts a new row and closes the old one by setting its
`effective_to`, so historical fares stay in the table untouched
(docs/02-product-requirements.md business rule 7).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Fare(Base):
    """One price for one (route, origin, destination) journey."""

    __tablename__ = "fares"

    # Business entities use UUIDs (docs/04-database-specification.md section 14).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # The journey context (docs/02 business rule 6): a fare always belongs to
    # one route and names both ends of the trip.
    route_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routes.id"), nullable=False, index=True
    )
    origin_stop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stops.id"), nullable=False
    )
    destination_stop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stops.id"), nullable=False
    )

    # Money is decimal, never floating point (docs/04 section 14).
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # ISO 4217 code, stored upper-cased ("USD"); the schema layer normalizes it.
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD", server_default=text("'USD'")
    )

    # The validity window: [effective_from, effective_to). `effective_to` is
    # NULL for the current, open-ended fare of a journey.
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Deactivated fares are kept as history; they simply stop applying.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    # docs/04 section 9 lists only created_at for fares: a fare row is written
    # once and never re-priced, so it has no updated_at column.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # A window that ends before it starts can never be applicable.
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_fares_effective_window",
        ),
        # GET /fares/search filters on the stop pair, so both columns are
        # indexed together (the origin alone can still use this index).
        Index("ix_fares_origin_destination", "origin_stop_id", "destination_stop_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Fare id={self.id} route_id={self.route_id} "
            f"amount={self.amount} {self.currency}>"
        )
