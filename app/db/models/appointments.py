"""``appointments`` table — scheduled property visits for leads."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=text("30")
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pendiente'"),
    )
    reminder_sent_24h: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, server_default=text("false")
    )
    reminder_sent_1h: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, server_default=text("false")
    )
    reminder_sent_15min: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, server_default=text("false")
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    interested_after_visit: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    created_at = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pendiente', 'confirmada', 'realizada', 'no_show', "
            "'cancelada_inquilino', 'cancelada_propietario', 'reprogramada')",
            name="ck_appointments_status",
        ),
        Index("ix_appointments_lead_id", "lead_id"),
        Index("ix_appointments_property_id", "property_id"),
        Index("ix_appointments_scheduled_at", "scheduled_at"),
        Index("ix_appointments_status", "status"),
    )