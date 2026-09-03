"""Declarative base shared by all ORM models and consumed by Alembic.

``Base.metadata`` is the single source of truth for the database schema in the
migration pipeline. It is intentionally empty for now: model tables
(properties, leads, neighborhoods) are introduced in a future change. Keeping
the base importable lets ``migrations/env.py`` wire ``target_metadata`` once
and have it pick up any future models automatically.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models in this project."""
