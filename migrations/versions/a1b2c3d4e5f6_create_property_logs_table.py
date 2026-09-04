"""create property_logs table

Revision ID: a1b2c3d4e5f6
Revises: e4b438d3a245
Create Date: 2026-09-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e4b438d3a245"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the property_logs audit trail table."""
    op.create_table(
        "property_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("field_changed", sa.String(length=50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column(
            "changed_by",
            sa.String(length=50),
            server_default=sa.text("'sistema'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_property_logs_property_id", "property_logs", ["property_id"], unique=False
    )
    op.create_index(
        "ix_property_logs_created_at", "property_logs", ["created_at"], unique=False
    )


def downgrade() -> None:
    """Drop the property_logs table."""
    op.drop_index("ix_property_logs_created_at", table_name="property_logs")
    op.drop_index("ix_property_logs_property_id", table_name="property_logs")
    op.drop_table("property_logs")
