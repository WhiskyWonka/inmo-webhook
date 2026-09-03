"""``leads`` table — prospective tenants captured via WhatsApp and other channels."""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'whatsapp'"),
    )
    budget_max_ars: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    desired_neighborhoods: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, server_default=text("'[]'::jsonb")
    )
    desired_rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_guarantee: Mapped[str | None] = mapped_column(String(30), nullable=True)
    has_pets: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    move_in_date = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'nuevo'"),
    )
    qualification_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
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
            "source IN ('whatsapp', 'zonaprop', 'argenprop', 'mercadolibre', "
            "'web', 'instagram', 'facebook', 'referido', 'otro')",
            name="ck_leads_source",
        ),
        CheckConstraint(
            "has_guarantee IS NULL OR has_guarantee IN ('propietaria', 'seguro_caucion', "
            "'garantia_bancaria', 'ninguna', 'en_tramite')",
            name="ck_leads_has_guarantee",
        ),
        CheckConstraint(
            "qualification_score IS NULL OR (qualification_score >= 0 AND qualification_score <= 100)",  # noqa: E501
            name="ck_leads_qualification_score",
        ),
        CheckConstraint(
            "status IN ('nuevo', 'calificando', 'calificado', 'visita_agendada', "
            "'en_documentacion', 'aprobado', 'descartado', 'convertido')",
            name="ck_leads_status",
        ),
        Index("ix_leads_status", "status"),
        Index("ix_leads_property_id", "property_id"),
        Index("ix_leads_source", "source"),
        Index("ix_leads_created_at", "created_at"),
        Index("ix_leads_phone", "phone"),
    )
