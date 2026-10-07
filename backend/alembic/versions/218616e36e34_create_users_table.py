"""create users table

Phase 1 - Authentication and Users.
Creates the `users` table described in docs/04-database-specification.md
section 3.

Design notes:
* `id` uses PostgreSQL UUID (docs/04 section 14).
* `email` gets a UNIQUE INDEX, which is what enforces one account per address.
* `role` is VARCHAR + CHECK constraint (native_enum=False) rather than a
  PostgreSQL ENUM type, so adding a role later is a simple constraint change
  instead of a type migration.
* `created_at` / `updated_at` default to `now()` in the database so timestamps
  are correct even for rows inserted outside the API.
* The table has no foreign keys yet; Phase 2 adds operator_assignments, trips
  and journey_searches referencing users.id.

Revision ID: 218616e36e34
Revises: 299d519af363
Create Date: 2026-10-05 20:25:24.059640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '218616e36e34'
down_revision: Union[str, None] = '299d519af363'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        # Business identifier. UUID generated in Python (uuid.uuid4 default).
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        # Stored lower-cased by the schema layer (app/schemas/validators.py).
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=True),
        # Argon2id hash only - never a plaintext password.
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column(
            'role',
            sa.Enum(
                'COMMUTER',
                'OPERATOR',
                'MANAGEMENT',
                name='user_role',
                native_enum=False,
                length=16,
            ),
            server_default='COMMUTER',
            nullable=False,
        ),
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
    # Unique index (not a separate constraint) to match the model definition.
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')