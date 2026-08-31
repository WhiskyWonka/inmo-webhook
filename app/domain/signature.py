"""HMAC-SHA256 signature verification for Meta webhook requests.

Meta signs every outgoing webhook POST with HMAC-SHA256 using the app
secret, and sends the digest in the ``X-Hub-Signature-256`` header as
``sha256=<hex>``. This module computes and verifies that signature.

The signature MUST be computed over the **raw request body bytes** exactly as
they arrived on the wire — never over a re-serialized JSON value. Re-serializing
(e.g. with ``json.dumps`` or ``await request.json()``) can change key order,
whitespace, or unicode escaping, which would change the digest and cause
valid Meta (or whap mock) requests to be rejected.
"""

import hashlib
import hmac

_SIGNATURE_PREFIX = "sha256="
_HEX_DIGEST_LENGTH = 64


def verify_signature(
    header_value: str | None,
    secret: str,
    raw_body: bytes,
) -> bool:
    """Return True if ``raw_body`` matches the given ``X-Hub-Signature-256``.

    The header must be in ``sha256=<64 hex chars>`` form. Returns False for a
    missing or malformed header, an incorrect secret, or a mismatched digest.
    Uses a timing-safe comparison to avoid leaking information.
    """
    if secret == "":
        return False
    if not header_value or not header_value.startswith(_SIGNATURE_PREFIX):
        return False

    incoming_hex = header_value[len(_SIGNATURE_PREFIX):]
    if len(incoming_hex) != _HEX_DIGEST_LENGTH:
        return False

    expected_hex = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_hex, incoming_hex)
