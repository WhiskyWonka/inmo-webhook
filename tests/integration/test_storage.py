"""Integration tests for the Postgres storage adapters.

These exercise ``PostgresLeadStore`` (upsert by phone, message append,
idempotency via external_id) and ``PostgresPropertyStore`` against a reachable
Postgres (DATABASE_URL). They run in CI.
"""

import os
import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from app.domain.messages import Lead, LeadWithMessages, Message
from app.storage.postgres import PostgresLeadStore, PostgresPropertyStore
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
