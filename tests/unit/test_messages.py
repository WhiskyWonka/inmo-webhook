"""Unit tests for the domain model and WhatsApp payload parsing.

Pure functions only — no FastAPI, no filesystem.
"""

from __future__ import annotations

from app.domain.messages import Lead, Message, LeadWithMessages, parse_whatsapp_payload

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SINGLE_MESSAGE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "id": "wamid.ABCD1234",
                                "from": "16315551181",
                                "type": "text",
                                "text": {"body": "Hola, quiero info sobre deptos"},
                            }
                        ]
                    }
                }
            ]
        }
    ],
}

MULTI_MESSAGE_SAME_PHONE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "id": "wamid.M1",
                                "from": "16315551181",
                                "type": "text",
                                "text": {"body": "first"},
                            },
                            {
                                "id": "wamid.M2",
                                "from": "16315551181",
                                "type": "image",
                            },
                        ]
                    }
                }
            ]
        }
    ],
}

MULTI_PHONE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "id": "wamid.P1",
                                "from": "111",
                                "type": "text",
                                "text": {"body": "from phone 111"},
                            },
                            {
                                "id": "wamid.P2",
                                "from": "222",
                                "type": "text",
                                "text": {"body": "from phone 222"},
                            },
                        ]
                    }
                }
            ]
        }
    ],
}

CONTACT_NAME_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "contacts": [
                            {
                                "wa_id": "16315551181",
                                "profile": {"name": "Juan Perez"},
                            }
                        ],
                        "messages": [
                            {
                                "id": "wamid.C1",
                                "from": "16315551181",
                                "type": "text",
                                "text": {"body": "hello"},
                            }
                        ],
                    }
                }
            ]
        }
    ],
}


# ---------------------------------------------------------------------------
# Lead dataclass
# ---------------------------------------------------------------------------


class TestLead:
    def test_required_phone_only(self):
        lead = Lead(phone="5491100001111")
        assert lead.phone == "5491100001111"
        assert lead.name is None
        assert lead.email is None
        assert lead.source == "whatsapp"
        assert lead.budget_max_ars is None
        assert lead.desired_neighborhoods == []
        assert lead.desired_rooms is None
        assert lead.has_guarantee is None
        assert lead.has_pets is None
        assert lead.move_in_date is None
        assert lead.status == "nuevo"
        assert lead.qualification_score is None
        assert lead.assigned_agent is None
        assert lead.metadata == {}
        assert lead.created_at is None
        assert lead.updated_at is None

    def test_full_lead(self):
        lead = Lead(
            phone="5491100001111",
            name="Maria",
            email="maria@test.com",
            source="zonaprop",
            budget_max_ars=200000.0,
            desired_neighborhoods=["Palermo", "Recoleta"],
            desired_rooms=3,
            has_guarantee="seguro_caucion",
            has_pets=True,
            move_in_date="2026-03-01",
            status="calificado",
            qualification_score=85,
            assigned_agent="agent-01",
            metadata={"notes": "callback"},
            created_at="2026-01-15T10:00:00",
            updated_at="2026-01-15T12:00:00",
        )
        assert lead.name == "Maria"
        assert lead.desired_neighborhoods == ["Palermo", "Recoleta"]
        assert lead.status == "calificado"

    def test_default_desired_neighborhoods_is_independent(self):
        lead1 = Lead(phone="111")
        lead2 = Lead(phone="222")
        lead1.desired_neighborhoods.append("Palermo")
        assert lead2.desired_neighborhoods == []


# ---------------------------------------------------------------------------
# Message dataclass
# ---------------------------------------------------------------------------


class TestMessage:
    def test_minimal_message(self):
        msg = Message(direction="inbound", content="hi", message_type="text")
        assert msg.direction == "inbound"
        assert msg.content == "hi"
        assert msg.message_type == "text"
        assert msg.external_id is None
        assert msg.raw_payload == {}
        assert msg.timestamp == ""

    def test_full_message(self):
        raw = {"from": "111", "text": {"body": "hi"}}
        msg = Message(
            direction="outbound",
            content="bye",
            message_type="image",
            external_id="wamid.X",
            raw_payload=raw,
            timestamp="2026-01-15T10:00:00",
        )
        assert msg.external_id == "wamid.X"
        assert msg.raw_payload is raw


# ---------------------------------------------------------------------------
# Parser: basic behaviour
# ---------------------------------------------------------------------------


class TestParseWhatsappPayload:
    def test_single_message_returns_one_parsed_message(self):
        results = parse_whatsapp_payload(SINGLE_MESSAGE_PAYLOAD)
        assert len(results) == 1
        parsed = results[0]
        assert isinstance(parsed, LeadWithMessages)
        assert isinstance(parsed.lead, Lead)
        assert len(parsed.messages) == 1

    def test_lead_phone_and_defaults(self):
        results = parse_whatsapp_payload(SINGLE_MESSAGE_PAYLOAD)
        lead = results[0].lead
        assert lead.phone == "16315551181"
        assert lead.source == "whatsapp"
        assert lead.status == "nuevo"
        assert lead.name is None  # no contacts block

    def test_message_fields(self):
        results = parse_whatsapp_payload(SINGLE_MESSAGE_PAYLOAD)
        msg = results[0].messages[0]
        assert isinstance(msg, Message)
        assert msg.direction == "inbound"
        assert msg.content == "Hola, quiero info sobre deptos"
        assert msg.message_type == "text"
        assert msg.external_id == "wamid.ABCD1234"
        assert isinstance(msg.raw_payload, dict)
        assert len(msg.timestamp) > 0  # ISO 8601

    def test_non_whatsapp_object_returns_empty(self):
        results = parse_whatsapp_payload({"object": "something_else"})
        assert results == []

    def test_completely_empty_payload_returns_empty(self):
        results = parse_whatsapp_payload({})
        assert results == []

    def test_empty_entry_returns_empty(self):
        results = parse_whatsapp_payload({
            "object": "whatsapp_business_account",
            "entry": [],
        })
        assert results == []

    def test_missing_messages_returns_empty(self):
        results = parse_whatsapp_payload({
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"contacts": []}}]}],
        })
        assert results == []

    def test_missing_from_is_skipped_gracefully(self):
        """A message without ``from`` is skipped, not fatal."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"id": "wamid.NOFROM", "type": "text"},
                                    {"id": "wamid.OK1", "from": "555", "type": "text"},
                                ]
                            }
                        }
                    ]
                }
            ],
        }
        results = parse_whatsapp_payload(payload)
        assert len(results) == 1
        assert results[0].lead.phone == "555"
        assert len(results[0].messages) == 1
        assert results[0].messages[0].external_id == "wamid.OK1"

    def test_message_without_id_has_external_id_none(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"from": "555", "type": "text"},
                                ]
                            }
                        }
                    ]
                }
            ],
        }
        results = parse_whatsapp_payload(payload)
        assert len(results) == 1
        msg = results[0].messages[0]
        assert msg.external_id is None

    def test_missing_text_defaults_to_empty(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [{"id": "wamid.X", "from": "555"}]
                            }
                        }
                    ]
                }
            ],
        }
        results = parse_whatsapp_payload(payload)
        assert len(results) == 1
        assert results[0].messages[0].content == ""
        assert results[0].messages[0].message_type == "text"


# ---------------------------------------------------------------------------
# Parser: grouping by phone
# ---------------------------------------------------------------------------


class TestParseGroupingByPhone:
    def test_same_phone_yields_one_parsed_message_with_two_messages(self):
        results = parse_whatsapp_payload(MULTI_MESSAGE_SAME_PHONE_PAYLOAD)
        assert len(results) == 1
        assert results[0].lead.phone == "16315551181"
        assert len(results[0].messages) == 2

    def test_two_phones_yields_two_parsed_messages(self):
        results = parse_whatsapp_payload(MULTI_PHONE_PAYLOAD)
        assert len(results) == 2
        phones = {r.lead.phone for r in results}
        assert phones == {"111", "222"}

    def test_message_types_preserved(self):
        results = parse_whatsapp_payload(MULTI_MESSAGE_SAME_PHONE_PAYLOAD)
        types = [m.message_type for m in results[0].messages]
        assert types == ["text", "image"]


# ---------------------------------------------------------------------------
# Parser: contact name extraction
# ---------------------------------------------------------------------------


class TestParseContactName:
    def test_name_extracted_from_contacts_block(self):
        results = parse_whatsapp_payload(CONTACT_NAME_PAYLOAD)
        assert len(results) == 1
        assert results[0].lead.name == "Juan Perez"

    def test_name_only_from_payload_not_elsewhere(self):
        results = parse_whatsapp_payload(SINGLE_MESSAGE_PAYLOAD)
        assert results[0].lead.name is None  # no contacts block

    def test_name_resolved_from_id_when_wa_id_absent(self):
        """Contact keyed by ``id`` (no ``wa_id``) still maps to the lead."""

        def _payload():
            return {
                "object": "whatsapp_business_account",
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "contacts": [
                                        {
                                            "id": "111",
                                            "profile": {"name": "Ana Lopez"},
                                        }
                                    ],
                                    "messages": [
                                        {
                                            "id": "wamid.WAID",
                                            "from": "111",
                                            "type": "text",
                                            "text": {"body": "hola"},
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                ],
            }

        results = parse_whatsapp_payload(_payload())
        assert len(results) == 1
        assert results[0].lead.name == "Ana Lopez"


# ---------------------------------------------------------------------------
# Parser: multiple entries / changes
# ---------------------------------------------------------------------------


class TestParseMultipleEntries:
    def test_entries_across_multiple_changes_collapsed(self):
        """Two changes in one entry, each with messages from same phone → one LeadWithMessages."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.A1",
                                        "from": "111",
                                        "type": "text",
                                        "text": {"body": "a"},
                                    }
                                ]
                            }
                        },
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.B1",
                                        "from": "111",
                                        "type": "text",
                                        "text": {"body": "b"},
                                    }
                                ]
                            }
                        },
                    ]
                }
            ],
        }
        results = parse_whatsapp_payload(payload)
        assert len(results) == 1
        assert results[0].lead.phone == "111"
        assert len(results[0].messages) == 2

    def test_entries_across_multiple_entries_collapsed(self):
        """Same phone in two separate entries → one LeadWithMessages."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.E1",
                                        "from": "999",
                                        "type": "text",
                                        "text": {"body": "entry1"},
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.E2",
                                        "from": "999",
                                        "type": "text",
                                        "text": {"body": "entry2"},
                                    }
                                ]
                            }
                        }
                    ]
                },
            ],
        }
        results = parse_whatsapp_payload(payload)
        assert len(results) == 1
        assert len(results[0].messages) == 2
