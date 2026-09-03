"""Integration tests that validate the schema created by ``alembic upgrade head``.

These require a reachable Postgres (DATABASE_URL). They assert the three
tables exist with the expected columns, that the 19 neighborhoods were seeded,
and that a properties row can FK to a neighborhoods row.
"""

import os
import time

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


def _skip_without_database() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — skipping schema integration test")


def _alembic_config() -> Config:
    """Build an Alembic Config from an absolute path to alembic.ini.

    Deriving the path from ``__file__`` keeps this robust regardless of the
    process working directory (e.g. when pytest runs from a subdirectory).
    """
    ini_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "alembic.ini"
    )
    return Config(os.path.abspath(ini_path))


@pytest.fixture(scope="module")
def engine():
    _skip_without_database()
    # Run the migration to head (fast no-op if already up to date).
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    return create_engine(os.environ["DATABASE_URL"])


def test_three_tables_exist(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
        ).fetchall()
    names = {row[0] for row in rows}
    assert {"neighborhoods", "properties", "leads"}.issubset(names)


def test_neighborhoods_seeded_19_rows(engine):
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM neighborhoods")).scalar_one()
        assert count == 19


@pytest.mark.parametrize(
    ("table_name", "column"),
    [
        ("neighborhoods", "id"),
        ("neighborhoods", "name"),
        ("neighborhoods", "zone"),
        ("neighborhoods", "city"),
        ("neighborhoods", "created_at"),
        ("properties", "reference_code"),
        ("properties", "neighborhood_id"),
        ("properties", "address"),
        ("properties", "property_type"),
        ("properties", "status"),
        ("properties", "metadata"),
        ("leads", "property_id"),
        ("leads", "phone"),
        ("leads", "source"),
        ("leads", "status"),
        ("leads", "metadata"),
    ],
)
def test_expected_columns_exist(engine, table_name, column):
    with engine.connect() as conn:
        cols = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t"
            ),
            {"t": table_name},
        ).fetchall()
    col_names = {row[0] for row in cols}
    assert column in col_names, f"column {table_name}.{column} missing"


def test_properties_fk_to_neighborhoods_works(engine):
    """A properties row can reference an existing seeded neighborhood."""
    with engine.begin() as conn:
        nid = conn.execute(
            text("SELECT id FROM neighborhoods WHERE name = 'Palermo'")
        ).scalar_one()
        ref = conn.execute(
            text(
                "INSERT INTO properties (reference_code, address, property_type, neighborhood_id) "
                "VALUES ('TEST-REF', 'Av. Libertador 100', 'departamento', :nid) "
                "RETURNING id"
            ),
            {"nid": nid},
        ).scalar_one()
        conn.execute(
            text("DELETE FROM properties WHERE id = :ref"),
            {"ref": ref},
        )


def test_updated_at_trigger_function_exists(engine):
    with engine.connect() as conn:
        count = conn.execute(
            text(
                "SELECT count(*) FROM pg_proc "
                "WHERE proname = 'update_updated_at_column'"
            )
        ).scalar_one()
        assert count == 1


def test_updated_at_triggers_exist(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal "
                "AND tgname IN ('update_properties_updated_at', 'update_leads_updated_at')"
            )
        ).fetchall()
    names = {row[0] for row in rows}
    assert "update_properties_updated_at" in names
    assert "update_leads_updated_at" in names


def test_updated_at_trigger_actually_fires(engine):
    """UPDATE on properties must bump updated_at via the trigger.

    ``CURRENT_TIMESTAMP`` is transaction-stable in Postgres (it returns the
    transaction start time), so the INSERT and the UPDATE must run in separate
    committed transactions for ``updated_at`` to advance.
    """
    with engine.begin() as conn:
        ref = conn.execute(
            text(
                "INSERT INTO properties (reference_code, address, property_type, status) "
                "VALUES ('TRIG-RUN', 'Av. Siempre Viva 1', 'departamento', 'disponible') "
                "RETURNING id"
            )
        ).scalar_one()
        first = conn.execute(
            text("SELECT updated_at FROM properties WHERE id = :ref"),
            {"ref": ref},
        ).scalar_one()
    time.sleep(0.05)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE properties SET status = 'reservado' WHERE id = :ref"),
            {"ref": ref},
        )
    with engine.begin() as conn:
        second = conn.execute(
            text("SELECT updated_at FROM properties WHERE id = :ref"),
            {"ref": ref},
        ).scalar_one()
        conn.execute(
            text("DELETE FROM properties WHERE id = :ref"),
            {"ref": ref},
        )
    assert second > first, "updated_at did not advance after UPDATE"


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        # properties.property_type invalid value
        (
            "INSERT INTO properties (reference_code, address, property_type) "
            "VALUES ('CK-PT', 'Rivadavia 1', :pt)",
            {"pt": "castillo"},
        ),
        # properties.status invalid value
        (
            "INSERT INTO properties (reference_code, address, property_type, status) "
            "VALUES ('CK-ST', 'Rivadavia 2', 'casa', :st)",
            {"st": "vendido"},
        ),
        # properties.rooms must be > 0 when set
        (
            "INSERT INTO properties (reference_code, address, property_type, rooms) "
            "VALUES ('CK-RO', 'Rivadavia 3', 'casa', :rooms)",
            {"rooms": -1},
        ),
        # leads.qualification_score must be between 0 and 100
        (
            "INSERT INTO leads (phone, qualification_score) VALUES ('+5491100000001', :qs)",
            {"qs": 150},
        ),
    ],
)
def test_check_constraints_reject_invalid_data(engine, sql, params):
    """Inserting data that violates a CHECK constraint must raise IntegrityError."""
    with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text(sql), params)


def test_on_delete_set_null_fires(engine):
    """Deleting a neighborhood must set referencing properties.neighborhood_id to NULL."""
    with engine.begin() as conn:
        # Create a throwaway neighborhood so we don't disturb the seeded ones.
        nid = conn.execute(
            text(
                "INSERT INTO neighborhoods (name, zone, city) "
                "VALUES ('Test Barrio', 'sur', 'CABA') RETURNING id"
            )
        ).scalar_one()
        ref = conn.execute(
            text(
                "INSERT INTO properties (reference_code, address, property_type, neighborhood_id) "
                "VALUES ('FK-DEL', 'Av. del Barrio 10', 'departamento', :nid) RETURNING id"
            ),
            {"nid": nid},
        ).scalar_one()
        conn.execute(text("DELETE FROM neighborhoods WHERE id = :nid"), {"nid": nid})
        nid_after = conn.execute(
            text("SELECT neighborhood_id FROM properties WHERE id = :ref"),
            {"ref": ref},
        ).scalar_one()
        conn.execute(
            text("DELETE FROM properties WHERE id = :ref"),
            {"ref": ref},
        )
    assert nid_after is None, "neighborhood deletion did not SET NULL the property FK"


def test_upgrade_downgrade_roundtrip():
    """Downgrade to base removes the tables, upgrade to head restores them."""
    _skip_without_database()
    cfg = _alembic_config()

    command.downgrade(cfg, "base")
    with create_engine(os.environ["DATABASE_URL"]).connect() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
        ).fetchall()
        names = {row[0] for row in tables}
        assert not {"neighborhoods", "properties", "leads"}.intersection(names), (
            "app tables still present after downgrade base"
        )
        version = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert version is None

    command.upgrade(cfg, "head")
    with create_engine(os.environ["DATABASE_URL"]).connect() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
        ).fetchall()
        names = {row[0] for row in tables}
        assert {"neighborhoods", "properties", "leads"}.issubset(names)
        count = conn.execute(text("SELECT count(*) FROM neighborhoods")).scalar_one()
        assert count == 19
        # A downgrade/upgrade cycle must also recreate the new index.
        idx = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'leads' AND indexname = 'ix_leads_phone'"
            )
        ).scalar_one_or_none()
        assert idx == "ix_leads_phone"
