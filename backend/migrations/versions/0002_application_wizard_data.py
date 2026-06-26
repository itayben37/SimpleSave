"""Add wizard_data JSONB column to applications

Stores raw questionnaire answers that have no dedicated column
(num_borrowers, first_home, marital_status, incomes, tier, etc.).

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("wizard_data", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "wizard_data")
