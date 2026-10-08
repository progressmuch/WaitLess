"""Add useful indexes for Phase 8."""
from alembic import op
import sqlalchemy as sa


revision = "d9999999d001"
down_revision = "c0b015690a56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Skip if exists? Try create with if not exists is not directly; just call - but error if exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_journey_searches_searched_at ON journey_searches (searched_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bus_locations_trip_received_at ON bus_locations (trip_id, received_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trips_status ON trips (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_operator_assignments_is_active ON operator_assignments (is_active)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_operator_assignments_is_active")
    op.execute("DROP INDEX IF EXISTS ix_trips_status")
    op.execute("DROP INDEX IF EXISTS ix_bus_locations_trip_received_at")
    op.execute("DROP INDEX IF EXISTS ix_journey_searches_searched_at")
