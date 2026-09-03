"""Unit tests for the SQLAlchemy schema models (properties, leads, neighborhoods).

These tests inspect ``Base.metadata`` directly — no database required. They
verify that the models declare the expected columns, types, check constraints,
foreign keys, and server defaults that the migration pipeline relies on.
"""

from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import Boolean, Date, DateTime, Integer, Numeric, String

import app.db  # noqa: F401 — ensures all models are registered
from app.db.base import Base


def _check_constraints(table_name: str) -> dict[str, CheckConstraint]:
    table = Base.metadata.tables[table_name]
    return {
        c.name: c
        for c in table.constraints
        if isinstance(c, CheckConstraint) and c.name
    }


def _quoted_literal_count(ck: CheckConstraint) -> int:
    """Count the quoted string literals (allowed values) in a CHECK IN list."""
    return ck.sqltext.text.count("'") // 2


# --------------------------------------------------------------------------
# metadata registration
# --------------------------------------------------------------------------


def test_all_three_tables_registered_in_base_metadata():
    """Base.metadata must see the three model tables."""
    assert "neighborhoods" in Base.metadata.tables
    assert "properties" in Base.metadata.tables
    assert "leads" in Base.metadata.tables


# --------------------------------------------------------------------------
# neighborhoods
# --------------------------------------------------------------------------


def test_neighborhoods_columns_and_types():
    table = Base.metadata.tables["neighborhoods"]
    assert set(table.c.keys()) == {
        "id",
        "name",
        "zone",
        "city",
        "created_at",
    }
    assert isinstance(table.c.id.type, UUID)
    assert isinstance(table.c.name.type, String)
    assert table.c.name.type.length == 50
    assert isinstance(table.c.zone.type, String)
    assert table.c.zone.type.length == 20
    assert isinstance(table.c.city.type, String)
    assert table.c.city.type.length == 30
    assert isinstance(table.c.created_at.type, DateTime)


def test_neighborhoods_not_null_and_defaults():
    table = Base.metadata.tables["neighborhoods"]
    assert not table.c.id.nullable
    assert not table.c.name.nullable
    assert not table.c.zone.nullable
    assert not table.c.city.nullable
    assert table.c.city.server_default.arg.text == "'CABA'"
    assert table.c.id.server_default.arg.text == "gen_random_uuid()"
    assert table.c.id.primary_key


def test_neighborhoods_zone_check():
    ck = _check_constraints("neighborhoods")["ck_neighborhoods_zone"]
    assert "norte" in ck.sqltext.text
    assert "centro" in ck.sqltext.text
    assert "sur" in ck.sqltext.text
    assert "oeste" in ck.sqltext.text
    assert "gba_oeste" in ck.sqltext.text
    assert "gba_sur" in ck.sqltext.text
    # Exactly 7 allowed zones.
    assert _quoted_literal_count(ck) == 7


# --------------------------------------------------------------------------
# properties
# --------------------------------------------------------------------------


def test_properties_columns_and_types():
    table = Base.metadata.tables["properties"]
    assert isinstance(table.c.id.type, UUID)
    assert isinstance(table.c.reference_code.type, String)
    assert table.c.reference_code.type.length == 20
    assert isinstance(table.c.neighborhood_id.type, UUID)
    assert isinstance(table.c.address.type, String)
    assert table.c.address.type.length == 255
    assert isinstance(table.c.property_type.type, String)
    assert table.c.property_type.type.length == 30
    assert isinstance(table.c.rooms.type, Integer)
    assert isinstance(table.c.bedrooms.type, Integer)
    assert isinstance(table.c.bathrooms.type, Integer)
    assert isinstance(table.c.square_meters.type, Numeric)
    assert isinstance(table.c.rent_price_ars.type, Numeric)
    assert isinstance(table.c.expenses_ars.type, Numeric)
    assert isinstance(table.c.guarantee_types.type, JSONB)
    assert isinstance(table.c.pets_allowed.type, Boolean)
    assert isinstance(table.c.available_from.type, Date)
    assert isinstance(table.c.status.type, String)
    assert isinstance(table.c.portal_urls.type, JSONB)
    assert isinstance(table.c.metadata.type, JSONB)
    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.updated_at.type, DateTime)


def test_properties_not_null_and_unique():
    table = Base.metadata.tables["properties"]
    assert not table.c.reference_code.nullable
    assert not table.c.address.nullable
    assert not table.c.property_type.nullable
    assert not table.c.status.nullable
    assert table.c.neighborhood_id.nullable
    # reference_code is unique
    from sqlalchemy import UniqueConstraint

    uniques = [
        uc
        for uc in table.constraints
        if isinstance(uc, UniqueConstraint) and list(uc.columns) == [table.c.reference_code]
    ]
    assert len(uniques) == 1


def test_properties_defaults():
    table = Base.metadata.tables["properties"]
    assert table.c.id.server_default.arg.text == "gen_random_uuid()"
    assert table.c.guarantee_types.server_default.arg.text == "'[]'::jsonb"
    assert table.c.portal_urls.server_default.arg.text == "'{}'::jsonb"
    assert table.c.metadata.server_default.arg.text == "'{}'::jsonb"
    assert table.c.status.server_default.arg.text == "'disponible'"
    assert table.c.pets_allowed.server_default.arg.text == "false"
    assert table.c.created_at.server_default.arg.text == "CURRENT_TIMESTAMP"
    assert table.c.updated_at.server_default.arg.text == "CURRENT_TIMESTAMP"


def test_properties_check_constraints():
    ck = _check_constraints("properties")
    assert "ck_properties_property_type" in ck
    assert "ck_properties_status" in ck
    assert "ck_properties_rooms_positive" in ck
    assert "ck_properties_bedrooms_nonneg" in ck
    assert "ck_properties_bathrooms_nonneg" in ck
    assert "departamento" in ck["ck_properties_property_type"].sqltext.text
    assert "reservado" in ck["ck_properties_status"].sqltext.text
    # Exactly 6 allowed property types and 5 allowed statuses.
    assert _quoted_literal_count(ck["ck_properties_property_type"]) == 6
    assert _quoted_literal_count(ck["ck_properties_status"]) == 5
    # rooms must be strictly positive when present.
    assert "> 0" in ck["ck_properties_rooms_positive"].sqltext.text


def test_properties_foreign_key_to_neighborhoods():
    table = Base.metadata.tables["properties"]
    fks = [fk for fk in table.foreign_keys]
    assert len(fks) == 1
    fk = fks[0]
    assert fk.parent.key == "neighborhood_id"
    assert fk.column.table.name == "neighborhoods"
    assert fk.ondelete == "SET NULL"


def test_properties_indexes():
    indexes = {ix.name: list(ix.columns) for ix in Base.metadata.tables["properties"].indexes}
    assert "ix_properties_status" in indexes
    assert "ix_properties_neighborhood_id" in indexes
    assert "ix_properties_property_type" in indexes
    assert "ix_properties_rent_price_ars" in indexes
    assert "ix_properties_available_from" in indexes


# --------------------------------------------------------------------------
# leads
# --------------------------------------------------------------------------


def test_leads_columns_and_types():
    table = Base.metadata.tables["leads"]
    assert isinstance(table.c.id.type, UUID)
    assert isinstance(table.c.property_id.type, UUID)
    assert isinstance(table.c.phone.type, String)
    assert table.c.phone.type.length == 20
    assert isinstance(table.c.name.type, String)
    assert table.c.name.type.length == 100
    assert isinstance(table.c.email.type, String)
    assert table.c.email.type.length == 100
    assert isinstance(table.c.source.type, String)
    assert table.c.source.type.length == 30
    assert isinstance(table.c.budget_max_ars.type, Numeric)
    assert isinstance(table.c.desired_neighborhoods.type, JSONB)
    assert isinstance(table.c.desired_rooms.type, Integer)
    assert isinstance(table.c.has_guarantee.type, String)
    assert table.c.has_guarantee.type.length == 30
    assert isinstance(table.c.has_pets.type, Boolean)
    assert isinstance(table.c.move_in_date.type, Date)
    assert isinstance(table.c.status.type, String)
    assert isinstance(table.c.qualification_score.type, Integer)
    assert isinstance(table.c.assigned_agent.type, String)
    assert table.c.assigned_agent.type.length == 50
    assert isinstance(table.c.metadata.type, JSONB)
    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.updated_at.type, DateTime)


def test_leads_not_null_and_defaults():
    table = Base.metadata.tables["leads"]
    assert table.c.id.server_default.arg.text == "gen_random_uuid()"
    assert not table.c.phone.nullable
    assert not table.c.source.nullable
    assert not table.c.status.nullable
    assert table.c.property_id.nullable
    assert table.c.name.nullable
    assert table.c.source.server_default.arg.text == "'whatsapp'"
    assert table.c.status.server_default.arg.text == "'nuevo'"
    assert table.c.metadata.server_default.arg.text == "'{}'::jsonb"
    assert table.c.desired_neighborhoods.server_default.arg.text == "'[]'::jsonb"


def test_leads_check_constraints():
    ck = _check_constraints("leads")
    assert "ck_leads_source" in ck
    assert "ck_leads_has_guarantee" in ck
    assert "ck_leads_status" in ck
    assert "ck_leads_qualification_score" in ck
    assert "mercadolibre" in ck["ck_leads_source"].sqltext.text
    assert "seguro_caucion" in ck["ck_leads_has_guarantee"].sqltext.text
    assert "convertido" in ck["ck_leads_status"].sqltext.text
    assert "100" in ck["ck_leads_qualification_score"].sqltext.text
    # Exactly 9 source values and 8 status values.
    assert _quoted_literal_count(ck["ck_leads_source"]) == 9
    assert _quoted_literal_count(ck["ck_leads_status"]) == 8
    # qualification_score is bounded at both ends.
    assert ">= 0" in ck["ck_leads_qualification_score"].sqltext.text
    assert "<= 100" in ck["ck_leads_qualification_score"].sqltext.text


def test_leads_foreign_key_to_properties():
    table = Base.metadata.tables["leads"]
    fks = [fk for fk in table.foreign_keys]
    assert len(fks) == 1
    fk = fks[0]
    assert fk.parent.key == "property_id"
    assert fk.column.table.name == "properties"
    assert fk.ondelete == "SET NULL"


def test_leads_indexes():
    indexes = {ix.name: list(ix.columns) for ix in Base.metadata.tables["leads"].indexes}
    assert "ix_leads_status" in indexes
    assert "ix_leads_property_id" in indexes
    assert "ix_leads_source" in indexes
    assert "ix_leads_created_at" in indexes
    assert "ix_leads_phone" in indexes
