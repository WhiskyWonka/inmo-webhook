"""Integration tests for the FastAPI webhook endpoints.

Uses TestClient against the real app. Settings are injected directly —
no importlib.reload, no monkeypatch.setenv.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.storage.lead_log import LeadLogStore
from app.web import create_app

VALID_TOKEN = "test_token"

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


@pytest.fixture
def client(tmp_path):
    """Return a TestClient wired to a per-test log path and verify token."""
    log_file = tmp_path / "leads.log"
    settings = Settings(verify_token=VALID_TOKEN, leads_log_path=str(log_file))
    store = LeadLogStore(settings.leads_log_path)
    app = create_app(settings, store)
    tc = TestClient(app)
    tc.log_file = log_file
    return tc


def test_verify_handshake_returns_challenge(client):
    """GET /webhook returns the challenge when mode and token match."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "987654",
        },
    )
    assert response.status_code == 200
    assert response.json() == 987654


def test_verify_handshake_rejects_bad_token(client):
    """GET /webhook returns an error when the token does not match."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "987654",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"error": "fallo"}


def test_post_uses_injected_store_backend(tmp_path):
    """A custom LeadStore backend can be injected into create_app (DIP)."""
    from app.domain.messages import Lead

    class FakeStore:
        def __init__(self):
            self.written: list[Lead] = []

        def write(self, lead: Lead) -> None:
            self.written.append(lead)

    settings = Settings(verify_token=VALID_TOKEN, leads_log_path=str(tmp_path / "x.log"))
    fake = FakeStore()
    app = create_app(settings, fake)
    tc = TestClient(app)

    response = tc.post("/webhook", json=WHATSAPP_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(fake.written) == 1
    assert fake.written[0].phone == "16315551181"
    assert fake.written[0].text == "this is a text message"


def test_post_valid_payload_writes_log_line(client):
    """POST /webhook with a WhatsApp payload writes one formatted log line."""
    response = client.post("/webhook", json=WHATSAPP_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    lines = client.log_file.read_text().strip().splitlines()
    assert len(lines) == 1

    ts_part, phone_part, text_part = lines[0].split(" | ")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?", ts_part)
    assert phone_part == "16315551181"
    assert text_part == "this is a text message"


def test_post_unrelated_payload_writes_no_log(client):
    """POST /webhook with a non-WhatsApp object is ignored, log stays empty."""
    response = client.post("/webhook", json={"object": "something_else"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not client.log_file.exists()


def test_post_multiple_messages_writes_all_log_lines(client):
    """POST /webhook with multiple messages writes one line per message."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "16315551181", "text": {"body": "first"}},
                                {"from": "5491100001111", "text": {"body": "second"}},
                            ]
                        }
                    }
                ]
            }
        ],
    }

    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    lines = client.log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("| 16315551181 | first")
    assert lines[1].endswith("| 5491100001111 | second")


def test_verify_handshake_missing_challenge_crashes(client):
    """Regression-guard: missing hub.challenge currently crashes the endpoint (issue #1)."""
    with pytest.raises(TypeError):
        client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": VALID_TOKEN},
        )


def test_verify_handshake_non_numeric_challenge_crashes(client):
    """Regression-guard: non-numeric hub.challenge currently crashes the endpoint (issue #1)."""
    with pytest.raises(ValueError):
        client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VALID_TOKEN,
                "hub.challenge": "abc",
            },
        )
