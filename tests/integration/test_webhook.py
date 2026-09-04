"""Integration tests for the FastAPI webhook endpoints.

Uses TestClient against the real app. Settings are injected directly —
no importlib.reload, no monkeypatch.setenv.

The handshake, signature, and request-shaping tests use an in-memory
``FakeStore`` so they run without a database. The persistence tests that
exercise the real ``PostgresLeadStore`` are gated on ``DATABASE_URL`` (they
run in CI against Postgres).
"""

import hashlib
import hmac
import json
import os
import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import Settings
from app.domain.messages import LeadWithMessages
from app.storage.postgres import PostgresLeadStore
from app.web import create_app
from tests.integration._helpers import (
    _alembic_config,
    _skip_without_database,
    _unique_phone,
)

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
                                "id": "wamid.ABCD1234",
                                "from": "16315551181",
                                "type": "text",
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


class FakeStore:
    """In-memory store matching the evolved LeadStore protocol (LeadWithMessages)."""

    def __init__(self):
        self.written: list[LeadWithMessages] = []

    def write(self, parsed: LeadWithMessages) -> None:
        self.written.append(parsed)


@pytest.fixture
def client():
    """Return a TestClient wired to an in-memory FakeStore and verify token."""
    settings = Settings(verify_token=VALID_TOKEN, app_secret=APP_SECRET)
    fake = FakeStore()
    app = create_app(settings, fake)
    tc = TestClient(app)
    tc.store = fake
    return tc


@pytest.fixture(scope="module")
def pg_engine():
    """Run migrations to head and return an engine; skip without DATABASE_URL."""
    _skip_without_database()
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    return create_engine(os.environ["DATABASE_URL"])


# ---------------------------------------------------------------------------
# Handshake (Meta verification)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Request shaping / signature
# ---------------------------------------------------------------------------


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


def test_post_unrelated_payload_writes_nothing(client):
    """POST /webhook with a non-WhatsApp object is ignored — nothing written."""
    response = _signed_post(client, {"object": "something_else"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert client.store.written == []


# ---------------------------------------------------------------------------
# Store injection (DIP) — no DB required
# ---------------------------------------------------------------------------


def test_post_uses_injected_store_backend(client):
    """A store matching the LeadStore protocol is injected into create_app (DIP)."""
    response = _signed_post(client, WHATSAPP_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(client.store.written) == 1
    parsed = client.store.written[0]
    assert isinstance(parsed, LeadWithMessages)
    assert parsed.lead.phone == "16315551181"
    assert len(parsed.messages) == 1
    assert parsed.messages[0].content == "this is a text message"


# ---------------------------------------------------------------------------
# Persistence — real Postgres store (CI)
# ---------------------------------------------------------------------------


def test_post_persists_lead_with_message(pg_engine):
    """A signed POST persists the lead (upsert by phone) and its message."""
    store = PostgresLeadStore(pg_engine)
    settings = Settings(verify_token=VALID_TOKEN, app_secret=APP_SECRET)
    phone = _unique_phone()
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": f"wamid.{uuid.uuid4().hex}",
                                    "from": phone,
                                    "type": "text",
                                    "text": {"body": "hola quiero info"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    try:
        client = TestClient(create_app(settings, store))
        response = _signed_post(client, payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        with pg_engine.connect() as conn:
            lead_id, source, status = conn.execute(
                text("SELECT id, source, status FROM leads WHERE phone = :p"),
                {"p": phone},
            ).one()
            count = conn.execute(
                text("SELECT count(*) FROM messages WHERE lead_id = :l"),
                {"l": lead_id},
            ).scalar_one()
        assert source == "whatsapp"
        assert status == "nuevo"
        assert count == 1
    finally:
        with pg_engine.begin() as conn:
            conn.execute(text("DELETE FROM leads WHERE phone = :p"), {"p": phone})


def test_post_multiple_phones_persist_each_lead(pg_engine):
    """A POST with messages from two phones persists both leads (one upsert each)."""
    store = PostgresLeadStore(pg_engine)
    settings = Settings(verify_token=VALID_TOKEN, app_secret=APP_SECRET)
    phone1 = _unique_phone()
    phone2 = _unique_phone()
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": f"wamid.{uuid.uuid4().hex}",
                                    "from": phone1,
                                    "type": "text",
                                    "text": {"body": "first"},
                                },
                                {
                                    "id": f"wamid.{uuid.uuid4().hex}",
                                    "from": phone2,
                                    "type": "text",
                                    "text": {"body": "second"},
                                },
                            ]
                        }
                    }
                ]
            }
        ],
    }
    try:
        client = TestClient(create_app(settings, store))
        response = _signed_post(client, payload)
        assert response.status_code == 200
        with pg_engine.connect() as conn:
            phones = {
                row[0]
                for row in conn.execute(
                    text("SELECT phone FROM leads WHERE phone IN (:a, :b)"),
                    {"a": phone1, "b": phone2},
                ).fetchall()
            }
        assert phones == {phone1, phone2}
    finally:
        with pg_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM leads WHERE phone IN (:a, :b)"),
                {"a": phone1, "b": phone2},
            )
