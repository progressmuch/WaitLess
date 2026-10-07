"""create buses and operator_assignments tables

Phase 2 - Transport Network (second half: buses and operator assignments).
Tables described in docs/04-database-specification.md sections 7 and 8.

Design notes:
* `buses.route_id` is the deviation agreed for this phase (docs/04 section 7):
  a bus carries the route it currently runs, so an operator's route is read
  from their assigned bus and is stored in exactly one place. It is nullable -
  a bus exists before anyone assigns it a route - and indexed, because Phase 5
  looks up the buses serving a route.
* registration_number and fleet_number are unique via unique indexes, matching
  "UNIQUE" in docs/04 section 7.
* `operator_assignments` has no created_at/updated_at columns: `assigned_at`
  starts the record and `ended_at` ends it (docs/04 section 8).
* Two partial unique indexes make the assignment rules race-proof: one active
  assignment per operator and one active driver per bus. The API checks the
  same conditions to return a friendly 409 before it ever reaches PostgreSQL.
* Foreign keys are left unnamed so PostgreSQL assigns its default names
  (<table>_<column>_fkey), which is exactly what `Base.metadata.create_all`
  produces for the test database.

Revision ID: 0d6cf8f316be
Revises: 92c12e0e12f2
Create Date: 2026-10-07 13:51:35.374503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d6cf8f316be'
down_revision: Union[str, None] = '92c12e0e12f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'buses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('registration_number', sa.String(length=32), nullable=False),
        sa.Column('fleet_number', sa.String(length=32), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('route_id', sa.Uuid(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_buses_fleet_number'), 'buses', ['fleet_number'], unique=True)
    op.create_index(op.f('ix_buses_registration_number'), 'buses', ['registration_number'], unique=True)
    op.create_index(op.f('ix_buses_route_id'), 'buses', ['route_id'], unique=False)

    op.create_table(
        'operator_assignments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('operator_id', sa.Uuid(), nullable=False),
        sa.Column('bus_id', sa.Uuid(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['bus_id'], ['buses.id']),
        sa.ForeignKeyConstraint(['operator_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_operator_assignments_operator_id'), 'operator_assignments', ['operator_id'], unique=False)
    op.create_index(op.f('ix_operator_assignments_bus_id'), 'operator_assignments', ['bus_id'], unique=False)
    op.create_index(
        'uq_operator_assignments_active_operator',
        'operator_assignments',
        ['operator_id'],
        unique=True,
        postgresql_where=sa.text('is_active'),
    )
    op.create_index(
        'uq_operator_assignments_active_bus',
        'operator_assignments',
        ['bus_id'],
        unique=True,
        postgresql_where=sa.text('is_active'),
    )


def downgrade() -> None:
    op.drop_index('uq_operator_assignments_active_bus', table_name='operator_assignments')
    op.drop_index('uq_operator_assignments_active_operator', table_name='operator_assignments')
    op.drop_index(op.f('ix_operator_assignments_bus_id'), table_name='operator_assignments')
    op.drop_index(op.f('ix_operator_assignments_operator_id'), table_name='operator_assignments')
    op.drop_table('operator_assignments')
    op.drop_index(op.f('ix_buses_route_id'), table_name='buses')
    op.drop_index(op.f('ix_buses_registration_number'), table_name='buses')
    op.drop_index(op.f('ix_buses_fleet_number'), table_name='buses')
    op.drop_table('buses')
