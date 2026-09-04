"""PostgreSQL storage adapters.

Concrete implementations of the ``LeadStore`` and ``PropertyStore`` protocols.
They use SQLAlchemy 2.0 connections/transactions and the ORM models from
``app/db/models`` to persist leads (with their messages) and properties. The
web layer never imports these directly — it only depends on the protocols in
``app/storage/base.py`` (Dependency Inversion Principle).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from app.db.models.leads import Lead as LeadModel
from app.db.models.messages import Message as MessageModel
from app.db.models.neighborhoods import Neighborhood as NeighborhoodModel
from app.db.models.properties import Property as PropertyModel
from app.domain.messages import LeadWithMessages, Message
from app.domain.neighborhoods import Neighborhood, Zone

# Columns that are set on INSERT but intentionally NOT clobbered by an
# UPDATE-on-conflict. ``status`` is pipeline state (v_leads_pipeline) and
# ``source`` is channel attribution — the WhatsApp parser always supplies
# their defaults ("nuevo"/"whatsapp"), so re-delivering a message must not
# reset an agent-tracked stage or overwrite the originating channel.
UPDATE_EXCLUDED = frozenset({"phone", "source", "status"})


def _lead_values(parsed: LeadWithMessages) -> dict:
    """Build the column dict for a leads upsert (excluding id/created_at/updated_at).

    Only non-None lead profile fields are included so an UPDATE-on-conflict
    does not null out existing data with an absent Optional field.
    """
    lead = parsed.lead
    values: dict = {
        "phone": lead.phone,
        "source": lead.source,
        "status": lead.status,
    }
    mappings = {
        "name": lead.name,
        "email": lead.email,
        "budget_max_ars": lead.budget_max_ars,
        "desired_neighborhoods": lead.desired_neighborhoods or None,
        "desired_rooms": lead.desired_rooms,
        "has_guarantee": lead.has_guarantee,
        "has_pets": lead.has_pets,
        "move_in_date": lead.move_in_date,
        "qualification_score": lead.qualification_score,
        "assigned_agent": lead.assigned_agent,
        "metadata": lead.metadata or None,
    }
    for column, value in mappings.items():
        if value is not None:
            values[column] = value
    return values


class PostgresLeadStore:
    """Persist a ``LeadWithMessages`` aggregate to Postgres.

    ``write`` upserts the lead keyed by ``phone`` (one lead per phone) and
    appends each message in the same transaction. Message inserts are
    idempotent via the unique ``external_id``: re-delivered messages are
    skipped rather than duplicated.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def write(self, parsed: LeadWithMessages) -> None:
        values = _lead_values(parsed)
        phone = values["phone"]
        with self._engine.begin() as conn:
            # Fields to actually update on conflict: profile/qualification only,
            # never status/source (pipeline/channel state) or phone (identity).
            set_ = {k: values[k] for k in values if k not in UPDATE_EXCLUDED}
            if set_:
                insert_stmt = pg_insert(LeadModel.__table__).values(**values)
                stmt = insert_stmt.on_conflict_do_update(
                    constraint="uq_leads_phone",
                    set_={k: insert_stmt.excluded[k] for k in set_},
                )
                stmt = stmt.returning(LeadModel.__table__.c.id)
                lead_id = conn.execute(stmt).scalar_one()
            else:
                # No profile fields to update: insert if new, otherwise reuse
                # the existing lead id (which must exist on conflict).
                stmt = (
                    pg_insert(LeadModel.__table__)
                    .values(**values)
                    .on_conflict_do_nothing(constraint="uq_leads_phone")
                    .returning(LeadModel.__table__.c.id)
                )
                lead_id = conn.execute(stmt).scalar_one_or_none()
                if lead_id is None:
                    lead_id = conn.execute(
                        select(LeadModel.__table__.c.id).where(
                            LeadModel.__table__.c.phone == phone
                        )
                    ).scalar_one()
            self._append_messages(conn, lead_id, parsed.messages)

    @staticmethod
    def _append_messages(conn, lead_id: uuid.UUID, messages: list[Message]) -> None:
        for message in messages:
            values: dict = {
                "lead_id": lead_id,
                "direction": message.direction,
                "content": message.content,
                "message_type": message.message_type,
                "raw_payload": message.raw_payload or {},
            }
            if message.external_id is None:
                # No external id: plain insert, no idempotency key available.
                conn.execute(pg_insert(MessageModel.__table__).values(**values))
                continue
            # Idempotency: the unique external_id index makes re-delivered
            # messages a no-op rather than a duplicate.
            values["external_id"] = message.external_id
            stmt = pg_insert(MessageModel.__table__).values(**values)
            conn.execute(stmt.on_conflict_do_nothing(index_elements=["external_id"]))


class PostgresPropertyStore:
    """Read/write ``Property`` records backed by the ``properties`` table.

    Minimal on purpose: no property-management API is in scope (#41). This
    scaffolding provides create / list / find-by-reference_code for the
    storage layer.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(self, reference_code: str, address: str, property_type: str, **kwargs) -> uuid.UUID:
        values = {
            "reference_code": reference_code,
            "address": address,
            "property_type": property_type,
            **kwargs,
        }
        stmt = (
            pg_insert(PropertyModel.__table__)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["reference_code"])
            .returning(PropertyModel.__table__.c.id)
        )
        with self._engine.begin() as conn:
            prop_id = conn.execute(stmt).scalar_one_or_none()
            if prop_id is None:
                # Unique-constraint conflict on reference_code: return the
                # existing row's id so create() is idempotent (never None).
                prop_id = conn.execute(
                    select(PropertyModel.__table__.c.id).where(
                        PropertyModel.__table__.c.reference_code == reference_code
                    )
                ).scalar_one()
        return prop_id

    def list(self, **filters) -> list[dict]:
        stmt = select(PropertyModel.__table__)
        for column, value in filters.items():
            if value is not None:
                stmt = stmt.where(PropertyModel.__table__.c[column] == value)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    def find_by_reference_code(self, reference_code: str) -> dict | None:
        stmt = (
            select(PropertyModel.__table__)
            .where(PropertyModel.__table__.c.reference_code == reference_code)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None


class PostgresNeighborhoodStore:
    """Read-only adapter for the seeded ``neighborhoods`` table.

    ``list`` returns domain ``Neighborhood`` objects. When *zone* is given,
    only neighborhoods in that zone are returned.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list(self, zone: str | None = None) -> list[Neighborhood]:
        stmt = select(NeighborhoodModel.__table__)
        if zone is not None:
            stmt = stmt.where(NeighborhoodModel.__table__.c.zone == zone)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [
            Neighborhood(
                id=str(row["id"]),
                name=row["name"],
                zone=Zone(row["zone"]),
                city=row["city"],
            )
            for row in rows
        ]
