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

    # Timestamp is ISO 8601 (optionally with microseconds), then " | phone | text".
    ts_part, phone_part, text_part = lines[0].split(" | ")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?", ts_part)
    assert phone_part == "16315551181"
    assert text_part == "this is a text message"


def test_post_unrelated_payload_writes_no_log(client):
    """POST /webhook with a non-WhatsApp object is ignored, and log stays empty."""
    response = client.post("/webhook", json={"object": "something_else"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not client.log_file.exists()


def test_post_multiple_messages_writes_all_log_lines(client):
    """POST /webhook with multiple messages writes one line per message."""
    payload = WHATSAPP_PAYLOAD.copy()
    payload["entry"][0]["changes"][0]["value"]["messages"] = [
        {"from": "16315551181", "text": {"body": "first"}},
        {"from": "5491100001111", "text": {"body": "second"}},
    ]

    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    lines = client.log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("| 16315551181 | first")
    assert lines[1].endswith("| 5491100001111 | second")


def test_verify_handshake_missing_challenge_crashes(client):
    """Regresion-guard: a missing hub.challenge currently crashes the endpoint.

    Documents the *current* buggy behavior (see GitHub issue #1): the endpoint
    calls int(challenge) without validating that challenge is present, so a
    missing value raises TypeError. FastAPI's TestClient re-raises the server
    exception instead of returning a 500, so we assert that the crash happens.
    When issue #1 is fixed to return a graceful error, this test must change.
    """
    with pytest.raises(TypeError):
        client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": VALID_TOKEN},
        )


def test_verify_handshake_non_numeric_challenge_crashes(client):
    """Regresion-guard: a non-numeric hub.challenge currently crashes the endpoint.

    Documents the current buggy behavior (see GitHub issue #1): int('abc') raises
    ValueError. The TestClient re-raises it rather than returning a 500. When the
    issue is fixed to return a graceful error, this test must change.
    """
    with pytest.raises(ValueError):
        client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VALID_TOKEN,
                "hub.challenge": "abc",
            },
        )
