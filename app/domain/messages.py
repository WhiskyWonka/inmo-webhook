from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Lead:
    """First-class domain entity representing a real-estate lead.

    Identity is by phone number (one lead per phone). Fields align with
    the relational ``leads`` table (issue #31).

    ``metadata`` is kept as the field name despite shadowing the stdlib
    module because: (a) ``from __future__ import annotations`` means the
    name is not evaluated at import time, (b) field access via
    ``lead.metadata`` is unambiguous in context, and (c) it matches the
    DB column name.  Alternatives like ``extra`` or ``metadata_fields``
    were considered but add indirection without benefit.
    """

    phone: str
    name: str | None = None
    email: str | None = None
    source: str = "whatsapp"
    budget_max_ars: float | None = None
    desired_neighborhoods: list[str] = field(default_factory=list)
    desired_rooms: int | None = None
    has_guarantee: str | None = None
    has_pets: bool | None = None
    move_in_date: str | None = None
    status: str = "nuevo"
    qualification_score: int | None = None
    assigned_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Message:
    """A single inbound or outbound message associated with a lead."""

    direction: str
    content: str
    message_type: str
    external_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class LeadWithMessages:
    """Aggregate returned by the parser: one lead upsert + its messages."""

    lead: Lead
    messages: list[Message] = field(default_factory=list)


def parse_whatsapp_payload(data: dict) -> list[LeadWithMessages]:
    """Parse a Meta webhook POST payload into grouped lead+messages.

    Traverses ``entry[].changes[].value.messages[]`` grouping by sender
    phone.  Each distinct phone yields **one** ``LeadWithMessages`` with a
    single ``Lead`` upsert and a list of that phone's ``Message`` objects.

    Returns an empty list if ``data["object"]`` is not
    ``"whatsapp_business_account"``.
    """
    if data.get("object") != "whatsapp_business_account":
        return []

    # Accumulate results keyed by sender phone.
    groups: dict[str, LeadWithMessages] = {}
    # Contact names extracted from value.contacts (if present).
    contact_names: dict[str, str] = {}

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Extract contact profile names from the contacts block.
            for contact in value.get("contacts", []):
                phone = contact.get("wa_id") or contact.get("id", "")
                profile = contact.get("profile", {})
                name = profile.get("name") or contact.get("name")
                if phone and name:
                    contact_names[phone] = name

            for msg in value.get("messages", []):
                phone = msg.get("from")
                if not phone:
                    continue

                # One Lead per distinct phone.
                if phone not in groups:
                    groups[phone] = LeadWithMessages(
                        lead=Lead(
                            phone=phone,
                            name=contact_names.get(phone),
                            source="whatsapp",
                            status="nuevo",
                        ),
                        messages=[],
                    )

                message = Message(
                    direction="inbound",
                    content=msg.get("text", {}).get("body", ""),
                    message_type=msg.get("type", "text"),
                    external_id=msg.get("id"),
                    raw_payload=msg,
                    timestamp=datetime.now().isoformat(),
                )
                groups[phone].messages.append(message)

    return list(groups.values())
