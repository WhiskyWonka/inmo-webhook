def validate_verification(
    mode: str | None,
    token: str | None,
    challenge: str | None,
    expected_token: str,
) -> str | None:
    """Validate the Meta webhook handshake query params.

    On success returns the raw ``hub.challenge`` string (echoed verbatim, as
    Meta's documentation requires it be returned with HTTP 200). Returns None
    on any failure so the caller can map it to an appropriate error status.

    ``hub.challenge`` is an opaque string (not numeric) — it is never coerced
    and must not crash on non-numeric or missing values.
    """
    if mode == "subscribe" and token == expected_token and challenge is not None:
        return challenge
    return None
