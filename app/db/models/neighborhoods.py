"""``neighborhoods`` table — barrios/zonas used for property geolocation."""

import uuid

from sqlalchemy import CheckConstraint, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Neighborhood(Base):
    __tablename__ = "neighborhoods"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    zone: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'CABA'"),
    )
    created_at = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(
            "zone IN ('norte', 'centro', 'sur', 'oeste', "
            "'gba_norte', 'gba_oeste', 'gba_sur')",
            name="ck_neighborhoods_zone",
        ),
    )
