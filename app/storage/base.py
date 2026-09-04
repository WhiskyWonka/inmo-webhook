"""Abstractions for storage backends.

This module defines the interfaces that web-layer code depends on,
so the web layer never imports a concrete store implementation
(Dependency Inversion Principle). Concrete adapters (e.g. Postgres)
live in sibling modules and only need to match these protocols.
"""

import uuid
from typing import Protocol

from app.domain.messages import LeadWithMessages


class LeadStore(Protocol):
    """Interface for persisting a lead aggregate with its messages.

    ``write`` atomically upserts the lead (keyed by phone) and appends the
    messages in a single transaction.
    """

    def write(self, parsed: LeadWithMessages) -> None: ...


class PropertyStore(Protocol):
    """Interface for reading and writing ``Property`` records.

    Kept minimal: no property-management API is in scope, this is the
    storage adapter scaffolding for listing/finding/creating properties.
    """

    def create(
        self,
        reference_code: str,
        address: str,
        property_type: str,
        **kwargs,
    ) -> uuid.UUID: ...

    def list(self, **kwargs) -> list[dict]: ...

    def find_by_reference_code(self, reference_code: str) -> dict | None: ...
