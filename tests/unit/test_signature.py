"""Unit tests for HMAC-SHA256 signature verification.

These vectors are verified against the reference digest from the whap mock and
OpenSSL:
    printf '%s' '{"object":"whatsapp_business_account"}' \
      | openssl dgst -sha256 -hmac 'test-app-secret'
    -> b6978b21c4467654c466607663db9b43fae44b71083568df403e0a077089208e
"""

import hmac
import hashlib

from app.domain.signature import verify_signature

SECRET = "test-app-secret"
# Compact JSON body (no whitespace) — matches whap's JSON.stringify output.
BODY = b'{"object":"whatsapp_business_account"}'
# Independently verified with openssl (see module docstring).
REFERENCE_DIGEST = "b6978b21c4467654c466607663db9b43fae44b71083568df403e0a077089208e"


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class TestVerifySignature:
    def test_matches_openssl_reference_digest(self):
        assert verify_signature(f"sha256={REFERENCE_DIGEST}", SECRET, BODY) is True

    def test_accepts_valid_signature(self):
        assert verify_signature(_sign(BODY), SECRET, BODY) is True

    def test_rejects_missing_header(self):
        assert verify_signature(None, SECRET, BODY) is False

    def test_rejects_absent_secret(self):
        assert verify_signature(_sign(BODY), "", BODY) is False

    def test_rejects_wrong_secret(self):
        assert verify_signature(_sign(BODY, "wrong-secret"), SECRET, BODY) is False

    def test_rejects_tampered_body(self):
        other = b'{"object":"something_else"}'
        assert verify_signature(_sign(BODY), SECRET, other) is False

    def test_rejects_malformed_prefix(self):
        digest = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
        assert verify_signature(f"md5={digest}", SECRET, BODY) is False

    def test_rejects_short_hex(self):
        assert verify_signature("sha256=deadbeef", SECRET, BODY) is False

    def test_rejects_wrong_length_digest(self):
        assert verify_signature("sha256=abc", SECRET, BODY) is False

    def test_empty_secret_never_accepts(self):
        assert verify_signature(_sign(BODY), "", BODY) is False
