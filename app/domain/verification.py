def validate_verification(
    mode: str | None,
    token: str | None,
    challenge: str | None,
    expected_token: str,
) -> int | dict:
    """Validate the Meta webhook handshake query params.

    Returns int(challenge) on success, {"error": "fallo"} on failure.
    The ValueError/TypeError crash on bad challenge is preserved (issue #1).
    """
    if mode == "subscribe" and token == expected_token:
        return int(challenge)
    return {"error": "fallo"}
