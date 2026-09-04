"""Domain value objects for properties and their audit trail."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PropertyLog:
    """A single audit-trail entry for a property change."""

    id: str
    property_id: str
    field_changed: str
    old_value: str | None
    new_value: str | None
    changed_by: str = "sistema"