"""Unit tests for the verification handshake logic.

Pure functions only — no FastAPI, no TestClient, no filesystem.
"""

from app.domain.verification import validate_verification

VALID_TOKEN = "test_token"


class TestValidateVerification:
    def test_returns_challenge_string_on_valid_token(self):
        result = validate_verification("subscribe", VALID_TOKEN, "987654", VALID_TOKEN)
        assert result == "987654"

    def test_returns_non_numeric_challenge_string_verbatim(self):
        """Meta's hub.challenge is an opaque string — an alphanumeric value must echo."""
        result = validate_verification("subscribe", VALID_TOKEN, "abc123xyz", VALID_TOKEN)
        assert result == "abc123xyz"

    def test_returns_none_on_bad_token(self):
        result = validate_verification("subscribe", "wrong_token", "987654", VALID_TOKEN)
        assert result is None

    def test_returns_none_when_mode_not_subscribe(self):
        result = validate_verification("unsubscribe", VALID_TOKEN, "987654", VALID_TOKEN)
        assert result is None

    def test_returns_none_when_token_is_none(self):
        result = validate_verification("subscribe", None, "987654", VALID_TOKEN)
        assert result is None

    def test_returns_none_when_challenge_is_none(self):
        """Missing challenge must not crash — returns None, caller maps to 400."""
        result = validate_verification("subscribe", VALID_TOKEN, None, VALID_TOKEN)
        assert result is None

    def test_returns_none_when_challenge_absent_with_bad_token(self):
        result = validate_verification("subscribe", None, None, VALID_TOKEN)
        assert result is None
