"""create routes, stops and route_stops tables

Phase 2 - Transport Network (first half: routes and stops).
Tables described in docs/04-database-specification.md sections 4, 5 and 6.

Design notes:
* `routes.is_active` defaults to false: a route is published only once it has
  its ordered stops (docs/02 business rule 5).
* `route_stops` gets UNIQUE(route_id, stop_sequence). That composite index
  already answers "stops of route X", so route_id needs no extra index; stop_id
  does get one, because "routes through stop X" is a different query.
* `estimated_minutes_from_start` is nullable so a route can be laid out before
  timing data exists.
* Foreign keys are left unnamed so PostgreSQL assigns its default names
  (<table>_<column>_fkey), which is exactly what `Base.metadata.create_all`
  produces for the test database.

Revision ID: 92c12e0e12f2
Revises: 218616e36e34
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92c12e0e12f2'
down_revision: Union[str, None] = '218616e36e34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'routes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        # Short public identifier, e.g. "HR-CHI"; unique across the system.
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        # Inactive until the route has its ordered stops.
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    # Unique index (not a separate constraint) to match the model definition.
    op.create_index(op.f('ix_routes_code'), 'routes', ['code'], unique=True)

    op.create_table(
        'stops',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        # WGS84 degrees; range-checked by the schema layer before insert.
        sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=False),
        # Inactive stops stay in the database (other tables still reference them).
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'route_stops',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('route_id', sa.Uuid(), nullable=False),
        sa.Column('stop_id', sa.Uuid(), nullable=False),
        # 1-based position of the stop along the route.
        sa.Column('stop_sequence', sa.Integer(), nullable=False),
        # Nullable: timing may be filled in after the route is laid out.
        sa.Column('estimated_minutes_from_start', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id']),
        sa.ForeignKeyConstraint(['stop_id'], ['stops.id']),
        sa.PrimaryKeyConstraint('id'),
        # One position per route - the database enforces ordering, not just the API.
        sa.UniqueConstraint(
            'route_id',
            'stop_sequence',
            name='uq_route_stops_route_id_stop_sequence',
        ),
    )
    # Only stop_id is indexed separately; route_id is covered by the unique
    # constraint above (its leftmost column).
    op.create_index(op.f('ix_route_stops_stop_id'), 'route_stops', ['stop_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_route_stops_stop_id'), table_name='route_stops')
    # Drop the link table before the tables it references.
    op.drop_table('route_stops')
    op.drop_table('stops')
    op.drop_index(op.f('ix_routes_code'), table_name='routes')
    op.drop_table('routes')
