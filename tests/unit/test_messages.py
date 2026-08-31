"""Unit tests for WhatsApp payload parsing.

Pure functions only — no FastAPI, no filesystem.
"""

from app.domain.messages import Lead, parse_whatsapp_payload

WHATSAPP_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "16315551181",
                                "text": {"body": "this is a text message"},
                            }
                        ]
                    }
                }
            ]
        }
    ],
}


class TestParseWhatsappPayload:
    def test_valid_payload_returns_lead(self):
        leads = parse_whatsapp_payload(WHATSAPP_PAYLOAD)
        assert len(leads) == 1
        lead = leads[0]
        assert isinstance(lead, Lead)
        assert lead.phone == "16315551181"
        assert lead.text == "this is a text message"
        assert len(lead.timestamp) > 0  # ISO 8601 string

    def test_unrelated_object_returns_empty(self):
        leads = parse_whatsapp_payload({"object": "something_else"})
        assert leads == []

    def test_empty_entry_returns_empty(self):
        leads = parse_whatsapp_payload({
            "object": "whatsapp_business_account",
            "entry": [],
        })
        assert leads == []

    def test_missing_messages_key_returns_empty(self):
        leads = parse_whatsapp_payload({
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"contacts": []}}]}],
        })
        assert leads == []

    def test_multiple_messages(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"from": "111", "text": {"body": "first"}},
                                    {"from": "222", "text": {"body": "second"}},
                                ]
                            }
                        }
                    ]
                }
            ],
        }
        leads = parse_whatsapp_payload(payload)
        assert len(leads) == 2
        assert leads[0].phone == "111"
        assert leads[0].text == "first"
        assert leads[1].phone == "222"
        assert leads[1].text == "second"

    def test_missing_text_defaults_to_empty(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [{"from": "555"}]
                            }
                        }
                    ]
                }
            ],
        }
        leads = parse_whatsapp_payload(payload)
        assert len(leads) == 1
        assert leads[0].text == ""
