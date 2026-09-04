"""messages table, leads.phone unique, v_leads_pipeline view

Revision ID: e4b438d3a245
Revises: 0184e017b2a8
Create Date: 2026-09-03

This migration is hand-written because it contains DDL Alembic autogenerate
cannot produce: a SQL view (``v_leads_pipeline``) and index/constraint bookkeeping
(dropping the redundant non-unique ``ix_leads_phone`` index in favour of the
``uq_leads_phone`` UNIQUE constraint that backs the phone-keyed upsert).

It also creates the ``messages`` table (issue #33 overlap) which the storage
adapter (issue #41) needs in order to append messages to a lead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4b438d3a245"
down_revision: Union[str, Sequence[str], None] = "0184e017b2a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- leads.phone UNIQUE -------------------------------------------------
    # The non-unique ix_leads_phone index is redundant once a UNIQUE
    # constraint (which owns its own unique index) exists on the same column.
    #
    # Guard: adding a UNIQUE constraint fails outright if duplicate phone
    # values already exist. Fail loudly with an actionable message instead of
    # letting Postgres emit a terse error — the operator must resolve
    # duplicates first. We never silently drop or merge data.
    dupes = op.get_bind().execute(
        sa.text(
            "SELECT phone, count(*) AS n FROM leads "
            "GROUP BY phone HAVING count(*) > 1 ORDER BY n DESC"
        )
    ).fetchall()
    if dupes:
        detail = "; ".join(f"{row[0]} ({row[1]} rows)" for row in dupes[:5])
        extra = " (and more...)" if len(dupes) > 5 else ""
        raise RuntimeError(
            "Cannot create uq_leads_phone UNIQUE constraint on leads.phone: "
            "duplicate phone values already exist in the leads table. "
            "Resolve the duplicates before running this migration; no data "
            "was modified. Duplicates: "
            f"{detail}{extra}"
        )
    op.drop_index("ix_leads_phone", table_name="leads")
    op.create_unique_constraint("uq_leads_phone", "leads", ["phone"])

    # --- messages table -----------------------------------------------------
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),  # noqa: E501
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),  # noqa: E501
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="ck_messages_direction",
        ),
        sa.CheckConstraint(
            "message_type IN ('text', 'image', 'audio', 'video', 'document', "
            "'location', 'contacts', 'interactive', 'reaction', 'sticker', 'button', 'other')",
            name="ck_messages_message_type",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_messages_lead_id", "messages", ["lead_id"], unique=False)

    # --- v_leads_pipeline view ----------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE VIEW v_leads_pipeline AS
        SELECT
            l.id,
            l.phone,
            l.name,
            l.email,
            l.source,
            l.status,
            l.qualification_score,
            l.assigned_agent,
            l.created_at,
            l.updated_at,
            COUNT(m.id) AS message_count
        FROM leads l
        LEFT JOIN messages m ON m.lead_id = l.id
        GROUP BY l.id, l.phone, l.name, l.email, l.source, l.status,
                 l.qualification_score, l.assigned_agent, l.created_at, l.updated_at
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP VIEW IF EXISTS v_leads_pipeline")
    op.drop_index("ix_messages_lead_id", table_name="messages")
    op.drop_table("messages")
    op.drop_constraint("uq_leads_phone", "leads", type_="unique")
    op.create_index("ix_leads_phone", "leads", ["phone"], unique=False)
