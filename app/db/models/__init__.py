"""ORM models for database schema.

Importing this package registers all models with ``Base.metadata`` so that
Alembic's autogenerate and ``target_metadata`` pick them up automatically.
"""

from app.db.models.leads import Lead  # noqa: F401
from app.db.models.messages import Message  # noqa: F401
from app.db.models.neighborhoods import Neighborhood  # noqa: F401
from app.db.models.properties import Property  # noqa: F401

__all__ = ["Lead", "Message", "Neighborhood", "Property"]
