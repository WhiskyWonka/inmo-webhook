"""Abstractions for storage backends.

This module defines the interfaces that web-layer code depends on,
so the web layer never imports a concrete store implementation
(Dependency Inversion Principle). Concrete adapters (e.g. Postgres)
live in sibling modules and only need to match these protocols.
"""

import uuid
from datetime import datetime
from typing import Protocol

from app.domain.appointments import Appointment, AppointmentStatus
from app.domain.messages import LeadWithMessages
from app.domain.neighborhoods import Neighborhood
from app.domain.properties import PropertyLog


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


class NeighborhoodStore(Protocol):
    """Interface for listing seeded neighborhoods."""

    def list(self, zone: str | None = None) -> list[Neighborhood]: ...


class PropertyLogStore(Protocol):
    """Interface for appending to and reading the property audit trail.

    Entries are written as a side-effect of property updates (the triggers
    that populate it are out of scope); this adapter provides the
    persistence scaffolding. ``list`` returns entries ordered oldest-first
    by created_at, with id as tiebreaker for rows written in the same
    transaction.
    """

    def append(
        self,
        property_id: str,
        field_changed: str,
        old_value: str | None,
        new_value: str | None,
        changed_by: str = "sistema",
    ) -> None: ...

    def list(self, property_id: str | None = None) -> list[PropertyLog]: ...


class AppointmentStore(Protocol):
    """Interface for scheduling and querying property visit appointments."""

    def create(
        self,
        lead_id: str,
        property_id: str,
        scheduled_at: datetime,
        duration_minutes: int | None = 30,
        status: AppointmentStatus = AppointmentStatus.pendiente,
        reminder_sent_24h: bool | None = False,
        reminder_sent_1h: bool | None = False,
        reminder_sent_15min: bool | None = False,
        feedback: str | None = None,
        interested_after_visit: bool | None = None,
    ) -> uuid.UUID: ...

    def list(
        self,
        lead_id: str | None = None,
        property_id: str | None = None,
        status: AppointmentStatus | None = None,
    ) -> list[Appointment]: ...

    def find_by_id(self, appointment_id: str) -> Appointment | None: ...
