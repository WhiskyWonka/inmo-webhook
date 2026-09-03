"""create properties, leads, neighborhoods tables

Revision ID: 0184e017b2a8
Revises:
Create Date: 2026-09-02 15:42:03.326056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0184e017b2a8"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEIGHBORHOOD_SEED = sa.table(
    "neighborhoods",
    sa.column("id", sa.UUID()),
    sa.column("name", sa.String()),
    sa.column("zone", sa.String()),
    sa.column("city", sa.String()),
)

# 19 seeded barrios from issue #37.
NEIGHBORHOODS = [
    ("Palermo", "norte", "CABA"),
    ("Belgrano", "norte", "CABA"),
    ("Nuñez", "norte", "CABA"),
    ("Colegiales", "norte", "CABA"),
    ("Chacarita", "norte", "CABA"),
    ("Villa Crespo", "norte", "CABA"),
    ("Caballito", "centro", "CABA"),
    ("Almagro", "centro", "CABA"),
    ("Recoleta", "centro", "CABA"),
    ("Retiro", "centro", "CABA"),
    ("San Telmo", "sur", "CABA"),
    ("La Boca", "sur", "CABA"),
    ("Constitución", "sur", "CABA"),
    ("Flores", "oeste", "CABA"),
    ("Floresta", "oeste", "CABA"),
    ("Villa del Parque", "oeste", "CABA"),
    ("Vicente López", "gba_norte", "GBA"),
    ("San Isidro", "gba_norte", "GBA"),
    ("Tigre", "gba_norte", "GBA"),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "neighborhoods",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("zone", sa.String(length=20), nullable=False),
        sa.Column("city", sa.String(length=30), server_default=sa.text("'CABA'"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),  # noqa: E501
        sa.CheckConstraint(
            "zone IN ('norte', 'centro', 'sur', 'oeste', 'gba_norte', 'gba_oeste', 'gba_sur')",
            name="ck_neighborhoods_zone",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "properties",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("reference_code", sa.String(length=20), nullable=False),
        sa.Column("neighborhood_id", sa.UUID(), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("property_type", sa.String(length=30), nullable=False),
        sa.Column("rooms", sa.Integer(), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("square_meters", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("rent_price_ars", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("expenses_ars", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "guarantee_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
        sa.Column("pets_allowed", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("available_from", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'disponible'"), nullable=False),  # noqa: E501
        sa.Column(
            "portal_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),  # noqa: E501
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),  # noqa: E501
        sa.CheckConstraint(
            "property_type IN ('departamento', 'ph', 'casa', 'local', 'oficina', 'deposito')",
            name="ck_properties_property_type",
        ),
        sa.CheckConstraint(
            "status IN ('disponible', 'reservado', 'alquilado', 'pausado', 'inactivo')",
            name="ck_properties_status",
        ),
        sa.CheckConstraint("bathrooms IS NULL OR bathrooms >= 0", name="ck_properties_bathrooms_nonneg"),  # noqa: E501
        sa.CheckConstraint("bedrooms IS NULL OR bedrooms >= 0", name="ck_properties_bedrooms_nonneg"),  # noqa: E501
        sa.CheckConstraint("rooms IS NULL OR rooms > 0", name="ck_properties_rooms_positive"),
        sa.ForeignKeyConstraint(["neighborhood_id"], ["neighborhoods.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_code"),
    )
    op.create_index("ix_properties_available_from", "properties", ["available_from"], unique=False)
    op.create_index("ix_properties_neighborhood_id", "properties", ["neighborhood_id"], unique=False)  # noqa: E501
    op.create_index("ix_properties_property_type", "properties", ["property_type"], unique=False)
    op.create_index("ix_properties_rent_price_ars", "properties", ["rent_price_ars"], unique=False)
    op.create_index("ix_properties_status", "properties", ["status"], unique=False)
    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=30), server_default=sa.text("'whatsapp'"), nullable=False),  # noqa: E501
        sa.Column("budget_max_ars", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "desired_neighborhoods",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
        sa.Column("desired_rooms", sa.Integer(), nullable=True),
        sa.Column("has_guarantee", sa.String(length=30), nullable=True),
        sa.Column("has_pets", sa.Boolean(), nullable=True),
        sa.Column("move_in_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'nuevo'"), nullable=False),  # noqa: E501
        sa.Column("qualification_score", sa.Integer(), nullable=True),
        sa.Column("assigned_agent", sa.String(length=50), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),  # noqa: E501
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),  # noqa: E501
        sa.CheckConstraint(
            "has_guarantee IS NULL OR has_guarantee IN ('propietaria', 'seguro_caucion', 'garantia_bancaria', 'ninguna', 'en_tramite')",  # noqa: E501
            name="ck_leads_has_guarantee",
        ),
        sa.CheckConstraint(
            "source IN ('whatsapp', 'zonaprop', 'argenprop', 'mercadolibre', 'web', 'instagram', 'facebook', 'referido', 'otro')",  # noqa: E501
            name="ck_leads_source",
        ),
        sa.CheckConstraint(
            "status IN ('nuevo', 'calificando', 'calificado', 'visita_agendada', 'en_documentacion', 'aprobado', 'descartado', 'convertido')",  # noqa: E501
            name="ck_leads_status",
        ),
        sa.CheckConstraint(
            "qualification_score IS NULL OR (qualification_score >= 0 AND qualification_score <= 100)",  # noqa: E501
            name="ck_leads_qualification_score",
        ),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_created_at", "leads", ["created_at"], unique=False)
    op.create_index("ix_leads_phone", "leads", ["phone"], unique=False)
    op.create_index("ix_leads_property_id", "leads", ["property_id"], unique=False)
    op.create_index("ix_leads_source", "leads", ["source"], unique=False)
    op.create_index("ix_leads_status", "leads", ["status"], unique=False)

    # Shared function + updated_at triggers (there is no SQLAlchemy runtime ORM
    # change; triggers are pure DDL so Alembic autogenerate cannot emit them).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER update_properties_updated_at
        BEFORE UPDATE ON properties
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )
    op.execute(
        """
        CREATE TRIGGER update_leads_updated_at
        BEFORE UPDATE ON leads
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # Seed the 19 barrios (issue #37).
    op.bulk_insert(
        NEIGHBORHOOD_SEED,
        [
            {"name": name, "zone": zone, "city": city}
            for name, zone, city in NEIGHBORHOODS
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS update_leads_updated_at ON leads")
    op.execute("DROP TRIGGER IF EXISTS update_properties_updated_at ON properties")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.drop_index("ix_leads_status", table_name="leads")
    op.drop_index("ix_leads_source", table_name="leads")
    op.drop_index("ix_leads_property_id", table_name="leads")
    op.drop_index("ix_leads_phone", table_name="leads")
    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_table("leads")
    op.drop_index("ix_properties_status", table_name="properties")
    op.drop_index("ix_properties_rent_price_ars", table_name="properties")
    op.drop_index("ix_properties_property_type", table_name="properties")
    op.drop_index("ix_properties_neighborhood_id", table_name="properties")
    op.drop_index("ix_properties_available_from", table_name="properties")
    op.drop_table("properties")
    op.drop_table("neighborhoods")
