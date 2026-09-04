"""Domain value objects for neighborhoods.

Pure domain layer — no framework imports.  A ``Neighborhood`` is a
read-only reference entity seeded in the database; the webhook service
never writes to this table.
"""

from dataclasses import dataclass
from enum import Enum


class Zone(str, Enum):
    """Canonical zones matching the DB CHECK constraint on ``neighborhoods.zone``."""

    norte = "norte"
    centro = "centro"
    sur = "sur"
    oeste = "oeste"
    gba_norte = "gba_norte"
    gba_oeste = "gba_oeste"
    gba_sur = "gba_sur"


@dataclass(frozen=True)
class Neighborhood:
    """Read-only reference to a neighborhood / barrio."""

    id: str
    name: str
    zone: Zone
    city: str = "CABA"
