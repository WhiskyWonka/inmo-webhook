"""``messages`` table — individual WhatsApp (or other channel) messages per lead.

The storage adapter appends one row per inbound/outbound message when writing a
``LeadWithMessages`` aggregate. ``external_id`` (the platform message id) is
nullable and unique, giving a natural idempotency key: re-delivered messages
with the same external id are skipped.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    raw_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, server_default=text("'{}'::jsonb")
    )
    received_at = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    created_at = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="ck_messages_direction",
        ),
        CheckConstraint(
            "message_type IN ('text', 'image', 'audio', 'video', 'document', "
            "'location', 'contacts', 'interactive', 'reaction', 'sticker', 'button', 'other')",
            name="ck_messages_message_type",
        ),
    )
