"""Behavior tests for the FastAPI webhook.

The log file path is bound at module import time (``LEADS_LOG_PATH``), so the
``client`` fixture sets ``LEADS_LOG_PATH`` and ``VERIFY_TOKEN`` *before*
reloading ``main`` via ``importlib.reload``. Each test gets its own temporary
log file through ``tmp_path``, keeping assertions isolated and deterministic.
"""

import importlib
import re

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Return a TestClient wired to a per-test log path and verify token."""
    log_file = tmp_path / "leads.log"
    monkeypatch.setenv("LEADS_LOG_PATH", str(log_file))
    monkeypatch.setenv("VERIFY_TOKEN", "test_verify_token")
    importlib.reload(main)
    client = TestClient(main.app)
    client.log_file = log_file
    return client


VALID_TOKEN = "test_verify_token"

# A realistic Meta / WhatsApp Cloud API payload with a single text message.
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


def test_post_valid_payload_writes_log_line(client):
    """POST /webhook with a WhatsApp payload writes one formatted log line."""
    response = client.post("/webhook", json=WHATSAPP_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    lines = client.log_file.read_text().strip().splitlines()
    assert len(lines) == 1

    line = lines[0]
    # Timestamp is an ISO 8601 datetime; phone and text match the payload.
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", line)
    assert line.endswith("| 16315551181 | this is a text message")


def test_post_unrelated_payload_writes_no_log(client):
    """POST /webhook with a non-WhatsApp object is ignored, and log stays empty."""
    response = client.post("/webhook", json={"object": "something_else"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not client.log_file.exists()
