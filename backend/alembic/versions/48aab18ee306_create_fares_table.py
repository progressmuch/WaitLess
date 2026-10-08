"""create fares table

Phase 3 - Journey Pricing.
Table described in docs/04-database-specification.md section 9.

Design notes:
* A fare row is a price for a validity window, not a mutable price tag:
  `effective_from` opens the window and `effective_to` closes it (NULL = the
  current, open-ended fare). Changing a price inserts a new row and closes the
  old one, so historical fares are preserved (docs/02 business rule 7).
* `ck_fares_effective_window` makes an empty window impossible even for
  writes that bypass the service layer.
* `amount` is Numeric(10, 2): money is decimal, never a float
  (docs/04 section 14); `currency` defaults to "USD".
* `created_at` only - docs/04 section 9 lists no `updated_at` for fares,
  because a fare is written once and never re-priced.
* Indexes: `ix_fares_route_id` answers the per-route list, and
  `ix_fares_origin_destination` answers GET /fares/search (its leftmost column
  also serves a search filtered by origin alone). A destination-only filter
  is rare enough not to warrant a third index.
* Foreign keys are left unnamed so PostgreSQL assigns its default names
  (<table>_<column>_fkey), which is exactly what `Base.metadata.create_all`
  produces for the test database.

Revision ID: 48aab18ee306
Revises: 0d6cf8f316be
Create Date: 2026-10-08 11:14:35.770215

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48aab18ee306'
down_revision: Union[str, None] = '0d6cf8f316be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fares',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('route_id', sa.Uuid(), nullable=False),
        sa.Column('origin_stop_id', sa.Uuid(), nullable=False),
        sa.Column('destination_stop_id', sa.Uuid(), nullable=False),
        # Decimal with two places: an amount with more decimals is rejected by
        # the schema layer rather than silently rounded here.
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default=sa.text("'USD'"), nullable=False),
        # Validity window [effective_from, effective_to); NULL = open ended.
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        # Deactivated fares stay in the table as history.
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            'effective_to IS NULL OR effective_to > effective_from',
            name='ck_fares_effective_window',
        ),
        sa.ForeignKeyConstraint(['destination_stop_id'], ['stops.id']),
        sa.ForeignKeyConstraint(['origin_stop_id'], ['stops.id']),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # Fare search filters on the stop pair; the prefix also covers origin only.
    op.create_index(
        'ix_fares_origin_destination',
        'fares',
        ['origin_stop_id', 'destination_stop_id'],
        unique=False,
    )
    op.create_index(op.f('ix_fares_route_id'), 'fares', ['route_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fares_route_id'), table_name='fares')
    op.drop_index('ix_fares_origin_destination', table_name='fares')
    op.drop_table('fares')
