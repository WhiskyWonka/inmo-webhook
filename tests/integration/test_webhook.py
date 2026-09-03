"""Integration tests for the FastAPI webhook endpoints.

Uses TestClient against the real app. Settings are injected directly —
no importlib.reload, no monkeypatch.setenv.
"""

import hashlib
import hmac
import json
import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.storage.lead_log import LeadLogStore
from app.web import create_app

VALID_TOKEN = "test_token"
APP_SECRET = "test-app-secret"

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


def _sign(body: bytes, secret: str = APP_SECRET) -> str:
    """Return the X-Hub-Signature-256 value for a raw body."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _signed_post(tc: TestClient, payload: dict, secret: str = APP_SECRET):
    """Post a payload signed with HMAC-SHA256, using the compact body bytes."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"X-Hub-Signature-256": _sign(body, secret)}
    return tc.post("/webhook", content=body, headers=headers)


@pytest.fixture
def client(tmp_path):
    """Return a TestClient wired to a per-test log path and verify token."""
    log_file = tmp_path / "leads.log"
    settings = Settings(
        verify_token=VALID_TOKEN, app_secret=APP_SECRET, leads_log_path=str(log_file)
    )
    store = LeadLogStore(settings.leads_log_path)
    app = create_app(settings, store)
    tc = TestClient(app)
    tc.log_file = log_file
    return tc


def test_verify_handshake_returns_challenge(client):
    """GET /webhook echoes the challenge string with HTTP 200 (Meta expects raw echo)."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "987654",
        },
    )
    assert response.status_code == 200
    assert response.text == "987654"


def test_verify_handshake_echoes_non_numeric_challenge(client):
    """Meta's hub.challenge is an opaque string — alphanumeric challenge echoes with 200."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "abc123xyz",
        },
    )
    assert response.status_code == 200
    assert response.text == "abc123xyz"


def test_verify_handshake_rejects_bad_token(client):
    """GET /webhook returns HTTP 400 (empty body) when the token does not match."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "987654",
        },
    )
    assert response.status_code == 400
    assert response.text == ""


@pytest.mark.skip(reason="#41 — parser/web/storage incompatible with new domain")
def test_post_uses_injected_store_backend(tmp_path):
    """A custom LeadStore backend can be injected into create_app (DIP)."""
    from app.domain.messages import Lead

    class FakeStore:
        def __init__(self):
            self.written: list[Lead] = []

        def write(self, lead: Lead) -> None:
            self.written.append(lead)

    settings = Settings(
        verify_token=VALID_TOKEN,
        app_secret=APP_SECRET,
        leads_log_path=str(tmp_path / "x.log"),
    )
    fake = FakeStore()
    app = create_app(settings, fake)
    tc = TestClient(app)

    response = _signed_post(tc, WHATSAPP_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(fake.written) == 1
    assert fake.written[0].phone == "16315551181"
    assert fake.written[0].text == "this is a text message"


@pytest.mark.skip(reason="#41 — parser/web/storage incompatible with new domain")
def test_post_valid_payload_writes_log_line(client):
    """POST /webhook with a WhatsApp payload writes one formatted log line."""
    response = _signed_post(client, WHATSAPP_PAYLOAD)
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
    response = _signed_post(client, {"object": "something_else"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not client.log_file.exists()


@pytest.mark.skip(reason="#41 — parser/web/storage incompatible with new domain")
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

    response = _signed_post(client, payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    lines = client.log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("| 16315551181 | first")
    assert lines[1].endswith("| 5491100001111 | second")


def test_post_missing_signature_returns_403(client):
    """POST /webhook without X-Hub-Signature-256 is rejected with 403."""
    body = json.dumps(WHATSAPP_PAYLOAD, separators=(",", ":")).encode("utf-8")
    response = client.post("/webhook", content=body)
    assert response.status_code == 403
    assert response.text == ""


def test_post_bad_signature_returns_403(client):
    """POST /webhook with an invalid signature is rejected with 403."""
    body = json.dumps(WHATSAPP_PAYLOAD, separators=(",", ":")).encode("utf-8")
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body, "wrong-secret")},
    )
    assert response.status_code == 403
    assert response.text == ""


def test_post_tampered_body_returns_403(client):
    """POST /webhook whose body was altered after signing is rejected with 403."""
    valid_body = json.dumps(WHATSAPP_PAYLOAD, separators=(",", ":")).encode("utf-8")
    signature = _sign(valid_body)
    tampered_body = valid_body.replace(b"this is a text message", b"tampered!")
    response = client.post(
        "/webhook",
        content=tampered_body,
        headers={"X-Hub-Signature-256": signature},
    )
    assert response.status_code == 403
    assert response.text == ""


def test_post_invalid_json_with_valid_signature_returns_400(client):
    """A signed non-JSON body is rejected with 400 (no crash)."""
    body = b"not-json"
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body)},
    )
    assert response.status_code == 400
    assert response.text == ""


def test_verify_handshake_missing_challenge_returns_400(client):
    """Missing hub.challenge must not crash — returns HTTP 400 (issue #1)."""
    response = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": VALID_TOKEN},
    )
    assert response.status_code == 400
    assert response.text == ""


def test_verify_handshake_bad_mode_returns_400(client):
    """A non-subscribe mode returns HTTP 400."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "other",
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "987654",
        },
    )
    assert response.status_code == 400
    assert response.text == ""
