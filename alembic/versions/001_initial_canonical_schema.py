"""Create canonical tables.

Revision ID: 001
Revises:
Create Date: 2025-05-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_order_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=True),
        sa.Column("order_date", sa.DateTime(), nullable=True),
        sa.Column("freight", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_order_id"),
    )
    op.create_index(
        op.f("ix_canonical_orders_source_order_id"),
        "canonical_orders",
        ["source_order_id"],
        unique=False,
    )

    op.create_table(
        "canonical_order_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("discount", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("line_total", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["canonical_orders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "validation_exceptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("rule_name", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expected_value", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("actual_value", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["canonical_orders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("validation_exceptions")
    op.drop_table("canonical_order_lines")
    op.drop_index(
        op.f("ix_canonical_orders_source_order_id"), table_name="canonical_orders"
    )
    op.drop_table("canonical_orders")
