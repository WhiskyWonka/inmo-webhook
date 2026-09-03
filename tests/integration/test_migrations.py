"""Integration smoke tests for the Alembic migration pipeline."""

import os

import pytest
from alembic import command
from alembic.config import Config


def _skip_without_database() -> None:
    """Skip the migrations tests unless a database URL is configured.

    This lets the suite run locally without a database: the migration smoke
    tests only exercise the migration pipeline when a Postgres instance is
    actually reachable (e.g. CI or a configured DATABASE_URL).
    """
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — skipping Alembic migration smoke test")


def _run_upgrade_head() -> None:
    """Run ``alembic upgrade head`` against the configured database."""
    # Absolute path so it works regardless of the pytest working directory.
    ini_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "alembic.ini"
    )
    cfg = Config(os.path.abspath(ini_path))
    command.upgrade(cfg, "head")


def test_alembic_upgrade_head_runs_without_error():
    """``alembic upgrade head`` must run without error against Postgres.

    With an empty migration history this is a no-op: it must succeed and not
    raise, but create no tables.
    """
    _skip_without_database()
    try:
        _run_upgrade_head()
    except Exception as exc:  # noqa: BLE001 - surface the real cause for diagnostics
        pytest.fail(f"alembic upgrade head failed against the configured database: {exc!r}")