"""Add mortgage-data columns surfaced by the Personal Area (valuation source,
refinance block, previously-owned-property flag).

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    valuation_enum = postgresql.ENUM(
        "self_assessment", "appraiser", "contractor",
        name="valuationsourceenum",
    )
    refinance_enum = postgresql.ENUM(
        "save_total", "reduce_monthly", "change_risk", "shorten_period", "consolidate_loans",
        name="refinancepurposeenum",
    )
    bind = op.get_bind()
    valuation_enum.create(bind, checkfirst=True)
    refinance_enum.create(bind, checkfirst=True)

    op.add_column("applications", sa.Column(
        "valuation_source",
        postgresql.ENUM("self_assessment", "appraiser", "contractor",
                        name="valuationsourceenum", create_type=False),
        nullable=True,
    ))
    op.add_column("applications", sa.Column("previously_owned_property", sa.Boolean(), nullable=True))
    op.add_column("applications", sa.Column(
        "refinance_purpose",
        postgresql.ENUM("save_total", "reduce_monthly", "change_risk", "shorten_period", "consolidate_loans",
                        name="refinancepurposeenum", create_type=False),
        nullable=True,
    ))
    op.add_column("applications", sa.Column("refinance_inject_amount", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "refinance_inject_amount")
    op.drop_column("applications", "refinance_purpose")
    op.drop_column("applications", "previously_owned_property")
    op.drop_column("applications", "valuation_source")
    bind = op.get_bind()
    postgresql.ENUM(name="refinancepurposeenum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="valuationsourceenum").drop(bind, checkfirst=True)
