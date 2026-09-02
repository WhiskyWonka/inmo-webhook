"""``properties`` table — real-estate listings managed by the platform."""

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


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    reference_code: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True
    )
    neighborhood_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("neighborhoods.id", ondelete="SET NULL"),
        nullable=True,
    )
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    property_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    square_meters: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    rent_price_ars: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    expenses_ars: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    guarantee_types: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, server_default=text("'[]'::jsonb")
    )
    pets_allowed: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, server_default=text("false")
    )
    available_from = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'disponible'"),
    )
    portal_urls: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, server_default=text("'{}'::jsonb")
    )
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
            "property_type IN ('departamento', 'ph', 'casa', 'local', 'oficina', 'deposito')",
            name="ck_properties_property_type",
        ),
        CheckConstraint("rooms IS NULL OR rooms > 0", name="ck_properties_rooms_positive"),
        CheckConstraint(
            "bedrooms IS NULL OR bedrooms >= 0", name="ck_properties_bedrooms_nonneg"
        ),
        CheckConstraint(
            "bathrooms IS NULL OR bathrooms >= 0",
            name="ck_properties_bathrooms_nonneg",
        ),
        CheckConstraint(
            "status IN ('disponible', 'reservado', 'alquilado', 'pausado', 'inactivo')",
            name="ck_properties_status",
        ),
        Index("ix_properties_status", "status"),
        Index("ix_properties_neighborhood_id", "neighborhood_id"),
        Index("ix_properties_property_type", "property_type"),
        Index("ix_properties_rent_price_ars", "rent_price_ars"),
        Index("ix_properties_available_from", "available_from"),
    )
