"""Abstractions for storage backends.

This module defines the interfaces that web-layer code depends on,
so the web layer never imports a concrete store implementation
(Dependency Inversion Principle).
"""

from typing import Protocol

from app.domain.messages import Lead


class LeadStore(Protocol):
    """Interface for persisting Lead records."""

    def write(self, lead: Lead) -> None: ...
