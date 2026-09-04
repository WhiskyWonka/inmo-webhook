"""create appointments table

Revision ID: b0c1d2e3f4a5
Revises: a1b2c3d4e5f6
Create Date: 2026-09-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the appointments table and its updated_at trigger."""
    op.create_table(
        "appointments",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column(
            "duration_minutes",
            sa.Integer(),
            server_default=sa.text("30"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pendiente'"),
            nullable=False,
        ),
        sa.Column(
            "reminder_sent_24h",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.Column(
            "reminder_sent_1h",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.Column(
            "reminder_sent_15min",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("interested_after_visit", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pendiente', 'confirmada', 'realizada', 'no_show', "
            "'cancelada_inquilino', 'cancelada_propietario', 'reprogramada')",
            name="ck_appointments_status",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_appointments_lead_id", "appointments", ["lead_id"], unique=False
    )
    op.create_index(
        "ix_appointments_property_id", "appointments", ["property_id"], unique=False
    )
    op.create_index(
        "ix_appointments_scheduled_at", "appointments", ["scheduled_at"], unique=False
    )
    op.create_index(
        "ix_appointments_status", "appointments", ["status"], unique=False
    )

    # The shared update_updated_at_column() function already exists (created by
    # 0184e017b2a8); only the per-table trigger is new DDL.
    op.execute(
        """
        CREATE TRIGGER update_appointments_updated_at
        BEFORE UPDATE ON appointments
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )


def downgrade() -> None:
    """Drop the appointments table and its trigger."""
    op.execute("DROP TRIGGER IF EXISTS update_appointments_updated_at ON appointments")
    op.drop_index("ix_appointments_status", table_name="appointments")
    op.drop_index("ix_appointments_scheduled_at", table_name="appointments")
    op.drop_index("ix_appointments_property_id", table_name="appointments")
    op.drop_index("ix_appointments_lead_id", table_name="appointments")
    op.drop_table("appointments")