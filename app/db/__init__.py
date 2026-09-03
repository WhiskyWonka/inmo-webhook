"""Schema metadata layer for database migrations.

This package holds the SQLAlchemy Core metadata used by Alembic to generate
and apply migrations. It is NOT a runtime storage layer: the application still
persists leads via the injected ``LeadStore`` abstraction at runtime.

Importing ``app.db`` registers all ORM models (neighborhoods, properties, leads)
with ``Base.metadata`` so that ``migrations/env.py`` picks them up automatically
via ``target_metadata = Base.metadata``.
"""

import app.db.models  # noqa: F401  — register models with Base.metadata
