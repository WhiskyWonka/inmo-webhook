"""Unit tests for the verification handshake logic.

Pure functions only — no FastAPI, no TestClient, no filesystem.
"""

import pytest

from app.domain.verification import validate_verification

VALID_TOKEN = "test_token"


class TestValidateVerification:
    def test_returns_challenge_on_valid_token(self):
        result = validate_verification("subscribe", VALID_TOKEN, "987654", VALID_TOKEN)
        assert result == 987654

    def test_returns_error_on_bad_token(self):
        result = validate_verification("subscribe", "wrong_token", "987654", VALID_TOKEN)
        assert result == {"error": "fallo"}

    def test_returns_error_when_mode_not_subscribe(self):
        result = validate_verification("unsubscribe", VALID_TOKEN, "987654", VALID_TOKEN)
        assert result == {"error": "fallo"}

    def test_returns_error_when_token_is_none(self):
        result = validate_verification("subscribe", None, "987654", VALID_TOKEN)
        assert result == {"error": "fallo"}

    def test_missing_challenge_crashes(self):
        """Regression-guard: missing challenge raises TypeError (issue #1)."""
        with pytest.raises(TypeError):
            validate_verification("subscribe", VALID_TOKEN, None, VALID_TOKEN)

    def test_non_numeric_challenge_crashes(self):
        """Regression-guard: non-numeric challenge raises ValueError (issue #1)."""
        with pytest.raises(ValueError):
            validate_verification("subscribe", VALID_TOKEN, "abc", VALID_TOKEN)
