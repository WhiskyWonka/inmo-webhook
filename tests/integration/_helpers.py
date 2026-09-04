"""Shared helpers for the integration test suite (DB-backed tests).

These were previously duplicated across the four integration test modules
(``_skip_without_database`` / ``_alembic_config`` / ``_unique_phone``). Import
them from here instead of redefining them in each test file.
"""

import os
import uuid

import pytest
from alembic.config import Config


def _skip_without_database() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — skipping Postgres integration test")


def _alembic_config() -> Config:
    """Build an Alembic Config from an absolute path to alembic.ini.

    Deriving the path from ``__file__`` keeps this robust regardless of the
    process working directory (e.g. when pytest runs from a subdirectory).
    """
    ini_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "alembic.ini"
    )
    return Config(os.path.abspath(ini_path))


def _unique_phone() -> str:
    return f"+54911{uuid.uuid4().hex[:10]}"
