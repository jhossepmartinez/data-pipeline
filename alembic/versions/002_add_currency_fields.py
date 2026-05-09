"""add_currency_fields

Revision ID: 002
Revises: 001
Create Date: 2025-05-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "canonical_orders",
        sa.Column("original_currency", sa.String(), nullable=True),
    )
    op.add_column(
        "canonical_orders",
        sa.Column("exchange_rate", sa.Numeric(precision=10, scale=6), nullable=True),
    )
    op.add_column(
        "canonical_orders",
        sa.Column(
            "total_amount_base", sa.Numeric(precision=10, scale=2), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("canonical_orders", "total_amount_base")
    op.drop_column("canonical_orders", "exchange_rate")
    op.drop_column("canonical_orders", "original_currency")
