"""Schema metadata layer for database migrations.

This package holds the SQLAlchemy Core metadata used by Alembic to generate
and apply migrations. It is NOT a runtime storage layer: the application still
persists leads via the injected ``LeadStore`` abstraction at runtime. Model
tables (properties, leads, neighborhoods) are added in a future change.
"""
