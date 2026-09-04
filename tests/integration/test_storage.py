"""Integration tests for the Postgres storage adapters.

These exercise ``PostgresLeadStore`` (upsert by phone, message append,
idempotency via external_id), ``PostgresPropertyStore``, and
``PostgresPropertyLogStore`` against a reachable Postgres (DATABASE_URL).
They run in CI.
"""

import os
import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.domain.messages import Lead, LeadWithMessages, Message
from app.domain.neighborhoods import Neighborhood, Zone
from app.domain.properties import PropertyLog
from app.storage.postgres import (
    PostgresLeadStore,
    PostgresNeighborhoodStore,
    PostgresPropertyLogStore,
    PostgresPropertyStore,
)
from tests.integration._helpers import (
    _alembic_config,
    _skip_without_database,
    _unique_phone,
)


@pytest.fixture(scope="module")
def engine():
    _skip_without_database()
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    return create_engine(os.environ["DATABASE_URL"])


# ---------------------------------------------------------------------------
# PostgresLeadStore
# ---------------------------------------------------------------------------


def test_write_upserts_lead_and_appends_message(engine):
    store = PostgresLeadStore(engine)
    phone = _unique_phone()
    lead = Lead(phone=phone, name="Juan", source="whatsapp", status="nuevo")
    parsed = LeadWithMessages(
        lead=lead,
        messages=[Message(direction="inbound", content="hola", message_type="text")],
    )
    try:
        store.write(parsed)
        with engine.connect() as conn:
            lead_id, name = conn.execute(
                text("SELECT id, name FROM leads WHERE phone = :p"), {"p": phone}
            ).one()
            count = conn.execute(
                text("SELECT count(*) FROM messages WHERE lead_id = :l"),
                {"l": lead_id},
            ).scalar_one()
        assert name == "Juan"
        assert count == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM leads WHERE phone = :p"), {"p": phone})


def test_write_twice_updates_lead_no_duplicate(engine):
    """Re-inserting the same phone updates the lead and keeps a single row."""
    store = PostgresLeadStore(engine)
    phone = _unique_phone()
    try:
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone, name="A"),
                messages=[Message(direction="inbound", content="one", message_type="text")],
            )
        )
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone, name="B"),
                messages=[Message(direction="inbound", content="two", message_type="text")],
            )
        )
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT name FROM leads WHERE phone = :p"), {"p": phone}
            ).fetchall()
            lead_id = conn.execute(
                text("SELECT id FROM leads WHERE phone = :p"), {"p": phone}
            ).scalar_one()
            message_count = conn.execute(
                text("SELECT count(*) FROM messages WHERE lead_id = :l"), {"l": lead_id}
            ).scalar_one()
        assert len(rows) == 1, "duplicate lead created for same phone"
        assert rows[0][0] == "B", "profile field was not updated on re-delivery"
        assert message_count == 2, "both messages should be appended across writes"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM leads WHERE phone = :p"), {"p": phone})


def test_write_preserves_status_and_source_on_update(engine):
    """Re-delivering an inbound message must not reset pipeline status/source.

    The WhatsApp parser always supplies status="nuevo"/source="whatsapp", so an
    UPDATE-on-conflict that clobbered those would reset an agent-tracked stage.
    """
    store = PostgresLeadStore(engine)
    phone = _unique_phone()
    try:
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone, name="A"),
                messages=[Message(direction="inbound", content="one", message_type="text")],
            )
        )
        # Simulate an agent progressing the pipeline + channel attribution.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE leads SET status = 'calificado', source = 'zonaprop' "
                    "WHERE phone = :p"
                ),
                {"p": phone},
            )
        # A re-delivered inbound message (parser default: status nuevo/source whatsapp).
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone, name="B"),
                messages=[Message(direction="inbound", content="two", message_type="text")],
            )
        )
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT name, status, source FROM leads WHERE phone = :p"),
                {"p": phone},
            ).one()
        assert row[0] == "B", "profile field was not updated"
        assert row[1] == "calificado", "status was reset by a re-delivered message"
        assert row[2] == "zonaprop", "source was overwritten by a re-delivered message"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM leads WHERE phone = :p"), {"p": phone})


def test_message_append_is_idempotent_by_external_id(engine):
    """A message with an already-seen external_id is not appended twice."""
    store = PostgresLeadStore(engine)
    phone = _unique_phone()
    ext_id = f"wamid.{uuid.uuid4().hex}"
    try:
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone),
                messages=[
                    Message(
                        direction="inbound",
                        content="dup",
                        message_type="text",
                        external_id=ext_id,
                    )
                ],
            )
        )
        # Re-delivery with the same external_id must be a no-op.
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone),
                messages=[
                    Message(
                        direction="inbound",
                        content="dup",
                        message_type="text",
                        external_id=ext_id,
                    )
                ],
            )
        )
        with engine.connect() as conn:
            lead_id = conn.execute(
                text("SELECT id FROM leads WHERE phone = :p"), {"p": phone}
            ).scalar_one()
            count = conn.execute(
                text("SELECT count(*) FROM messages WHERE lead_id = :l"), {"l": lead_id}
            ).scalar_one()
        assert count == 1, "idempotent message was appended twice"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM leads WHERE phone = :p"), {"p": phone})


def test_write_all_none_upsert_branch_reuses_existing_lead(engine):
    """The all-None set_ fallback reuses an existing lead and appends messages.

    When none of the UPDATE-on-conflict profile fields are present (only the
    phone/source/status columns, which are excluded from ``set_``), the store
    must insert-if-new and otherwise reuse the existing lead id rather than
    error out. Re-writing the same all-None lead must keep a single row.
    """
    store = PostgresLeadStore(engine)
    phone = _unique_phone()
    try:
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone),
                messages=[Message(direction="inbound", content="one", message_type="text")],
            )
        )
        # Re-deliver the same all-None lead: exercises the conflict path where
        # ``set_`` is empty and the existing lead id is reused.
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone),
                messages=[Message(direction="inbound", content="two", message_type="text")],
            )
        )
        with engine.connect() as conn:
            ids = conn.execute(
                text("SELECT id FROM leads WHERE phone = :p"), {"p": phone}
            ).fetchall()
            lead_id = conn.execute(
                text("SELECT id FROM leads WHERE phone = :p"), {"p": phone}
            ).scalar_one()
            message_count = conn.execute(
                text("SELECT count(*) FROM messages WHERE lead_id = :l"),
                {"l": lead_id},
            ).scalar_one()
        assert len(ids) == 1, "all-None re-write created a duplicate lead"
        assert message_count == 2, "messages were not appended in the all-None branch"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM leads WHERE phone = :p"), {"p": phone})


def test_v_leads_pipeline_view_exists_and_returns_rows(engine):
    """The v_leads_pipeline view exists and reflects lead + message counts."""
    store = PostgresLeadStore(engine)
    phone = _unique_phone()
    try:
        store.write(
            LeadWithMessages(
                lead=Lead(phone=phone, status="nuevo", qualification_score=50),
                messages=[
                    Message(direction="inbound", content="a", message_type="text"),
                    Message(direction="inbound", content="b", message_type="text"),
                ],
            )
        )
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT phone, status, qualification_score, message_count "
                    "FROM v_leads_pipeline WHERE phone = :p"
                ),
                {"p": phone},
            ).one_or_none()
        assert row is not None, "row missing from v_leads_pipeline"
        assert row[1] == "nuevo"
        assert row[2] == 50
        assert row[3] == 2
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM leads WHERE phone = :p"), {"p": phone})


# ---------------------------------------------------------------------------
# PostgresPropertyStore
# ---------------------------------------------------------------------------


def test_property_store_create_and_find(engine):
    store = PostgresPropertyStore(engine)
    ref = f"TST-{uuid.uuid4().hex[:6].upper()}"
    try:
        prop_id = store.create(
            reference_code=ref,
            address="Av. Test 100",
            property_type="departamento",
            rooms=2,
        )
        assert prop_id is not None
        found = store.find_by_reference_code(ref)
        assert found is not None
        assert found["reference_code"] == ref
        assert found["address"] == "Av. Test 100"
        assert found["property_type"] == "departamento"
        assert found["rooms"] == 2
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM properties WHERE reference_code = :r"), {"r": ref}
            )


def test_property_store_list_filters_by_property_type(engine):
    store = PostgresPropertyStore(engine)
    ref = f"TST-{uuid.uuid4().hex[:6].upper()}"
    try:
        store.create(
            reference_code=ref,
            address="Av. Filtro 1",
            property_type="casa",
        )
        results = store.list(property_type="casa")
        refs = {row["reference_code"] for row in results}
        assert ref in refs
        results_dep = store.list(property_type="departamento")
        assert ref not in {row["reference_code"] for row in results_dep}
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM properties WHERE reference_code = :r"), {"r": ref}
            )


# ---------------------------------------------------------------------------
# PostgresPropertyLogStore
# ---------------------------------------------------------------------------


def test_property_log_store_append_and_list(engine):
    store = PostgresPropertyStore(engine)
    log_store = PostgresPropertyLogStore(engine)
    ref = f"TST-{uuid.uuid4().hex[:6].upper()}"
    try:
        prop_id = store.create(
            reference_code=ref,
            address="Av. Logs 1",
            property_type="departamento",
        )
        assert prop_id is not None
        log_store.append(
            property_id=str(prop_id),
            field_changed="rent_price_ars",
            old_value=None,
            new_value="150000",
        )
        log_store.append(
            property_id=str(prop_id),
            field_changed="status",
            old_value="disponible",
            new_value="reservado",
        )
        entries = log_store.list(property_id=str(prop_id))
        assert len(entries) == 2
        assert all(isinstance(e, PropertyLog) for e in entries)
        assert entries[0].field_changed == "rent_price_ars"
        assert entries[0].old_value is None
        assert entries[0].new_value == "150000"
        assert entries[0].changed_by == "sistema", "changed_by should default to 'sistema'"
        assert entries[1].field_changed == "status"
        assert entries[1].old_value == "disponible"
        assert entries[1].new_value == "reservado"
        # Entries are returned oldest-first.
        assert [e.field_changed for e in entries] == ["rent_price_ars", "status"]
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM properties WHERE reference_code = :r"), {"r": ref}
            )


def test_property_log_store_list_filters_by_property_id(engine):
    store = PostgresPropertyStore(engine)
    log_store = PostgresPropertyLogStore(engine)
    ref_a = f"TST-{uuid.uuid4().hex[:6].upper()}"
    ref_b = f"TST-{uuid.uuid4().hex[:6].upper()}"
    try:
        prop_a = store.create(
            reference_code=ref_a,
            address="Av. A 1",
            property_type="departamento",
        )
        prop_b = store.create(
            reference_code=ref_b,
            address="Av. B 1",
            property_type="casa",
        )
        assert prop_a is not None and prop_b is not None
        log_store.append(
            property_id=str(prop_a),
            field_changed="status",
            old_value=None,
            new_value="reservado",
        )
        log_store.append(
            property_id=str(prop_b),
            field_changed="status",
            old_value=None,
            new_value="pausado",
        )
        log_store.append(
            property_id=str(prop_a),
            field_changed="address",
            old_value="Av. A 1",
            new_value="Av. A 2",
        )
        only_a = log_store.list(property_id=str(prop_a))
        assert [e.field_changed for e in only_a] == ["status", "address"]
        assert all(e.property_id == str(prop_a) for e in only_a)
        only_b = log_store.list(property_id=str(prop_b))
        assert [e.field_changed for e in only_b] == ["status"]
        all_entries = log_store.list()
        assert {str(prop_a), str(prop_b)} == {e.property_id for e in all_entries}
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM properties WHERE reference_code IN (:a, :b)"),
                {"a": ref_a, "b": ref_b},
            )


def test_property_log_store_append_rejects_empty_field_changed(engine):
    log_store = PostgresPropertyLogStore(engine)
    prop_id = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValueError, match="field_changed"):
        log_store.append(
            property_id=prop_id,
            field_changed="",
            old_value=None,
            new_value="x",
        )
    # The rejected append must not persist any row.
    assert log_store.list(property_id=prop_id) == []


def test_property_log_store_list_orders_ties_by_id(engine):
    """Rows sharing a created_at must come back ordered by id ascending.

    ``CURRENT_TIMESTAMP`` is the transaction start time, so a trigger that
    writes multiple entries in one transaction yields identical created_at
    values; the id tiebreaker makes that order deterministic.
    """
    store = PostgresPropertyStore(engine)
    log_store = PostgresPropertyLogStore(engine)
    ref = f"TST-{uuid.uuid4().hex[:6].upper()}"
    # Two explicit ids with known ascending order (…0001 < …0002).
    id_low = "00000000-0000-0000-0000-000000000001"
    id_high = "00000000-0000-0000-0000-000000000002"
    ts = "2026-09-04 10:00:00"
    try:
        prop_id = store.create(
            reference_code=ref,
            address="Av. Ties 1",
            property_type="departamento",
        )
        assert prop_id is not None
        # Insert in REVERSE id order with the same explicit created_at, so a
        # missing ORDER BY id would return them in the wrong order.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO property_logs "
                    "(id, property_id, field_changed, old_value, new_value, "
                    "changed_by, created_at) "
                    "VALUES (:id, :pid, :field, NULL, NULL, 'sistema', :ts)"
                ),
                {"id": id_high, "pid": str(prop_id), "field": "high-id", "ts": ts},
            )
            conn.execute(
                text(
                    "INSERT INTO property_logs "
                    "(id, property_id, field_changed, old_value, new_value, "
                    "changed_by, created_at) "
                    "VALUES (:id, :pid, :field, NULL, NULL, 'sistema', :ts)"
                ),
                {"id": id_low, "pid": str(prop_id), "field": "low-id", "ts": ts},
            )
        entries = log_store.list(property_id=str(prop_id))
        assert [e.id for e in entries] == [id_low, id_high]
        assert [e.field_changed for e in entries] == ["low-id", "high-id"]
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM properties WHERE reference_code = :r"), {"r": ref}
            )


def test_property_log_store_list_empty_for_property_without_logs(engine):
    store = PostgresPropertyStore(engine)
    log_store = PostgresPropertyLogStore(engine)
    ref = f"TST-{uuid.uuid4().hex[:6].upper()}"
    try:
        prop_id = store.create(
            reference_code=ref,
            address="Av. Sin Logs 1",
            property_type="departamento",
        )
        assert prop_id is not None
        assert log_store.list(property_id=str(prop_id)) == []
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM properties WHERE reference_code = :r"), {"r": ref}
            )


def test_property_log_store_append_unknown_property_raises(engine):
    """Appending for a nonexistent property violates the FK and stores nothing."""
    log_store = PostgresPropertyLogStore(engine)
    missing = str(uuid.uuid4())
    with pytest.raises(IntegrityError):
        log_store.append(
            property_id=missing,
            field_changed="status",
            old_value=None,
            new_value="reservado",
        )
    # The failed append must not persist any row.
    assert log_store.list(property_id=missing) == []


# ---------------------------------------------------------------------------
# PostgresNeighborhoodStore
# ---------------------------------------------------------------------------


def test_neighborhood_store_list_all(engine):
    store = PostgresNeighborhoodStore(engine)
    results = store.list()
    names = {n.name for n in results}
    assert "Palermo" in names
    assert "Tigre" in names
    assert len(results) == 19, "expected the exact seeded neighborhood set"
    # City is per-row: CABA rows default to CABA, GBA rows are stored as GBA.
    assert {n.city for n in results if n.zone == Zone.gba_norte} == {"GBA"}
    assert {n.city for n in results if n.zone != Zone.gba_norte} == {"CABA"}
    for n in results:
        assert isinstance(n, Neighborhood)
        assert isinstance(n.zone, Zone)
        assert n.id


def test_neighborhood_store_list_filters_by_zone(engine):
    store = PostgresNeighborhoodStore(engine)
    gba_norte = store.list(zone="gba_norte")
    gba_names = {n.name for n in gba_norte}
    assert {"Vicente López", "San Isidro", "Tigre"} <= gba_names
    assert all(n.zone == Zone.gba_norte for n in gba_norte)
    norte = store.list(zone="norte")
    norte_names = {n.name for n in norte}
    assert "Palermo" in norte_names
    assert "Tigre" not in norte_names
    assert all(n.zone == Zone.norte for n in norte)
