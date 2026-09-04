"""Domain aggregate for rental property visit appointments."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AppointmentStatus(str, Enum):
    pendiente = "pendiente"
    confirmada = "confirmada"
    realizada = "realizada"
    no_show = "no_show"
    cancelada_inquilino = "cancelada_inquilino"
    cancelada_propietario = "cancelada_propietario"
    reprogramada = "reprogramada"


@dataclass(frozen=True)
class Appointment:
    id: str                # UUID
    lead_id: str           # FK -> Lead
    property_id: str       # FK -> Property
    scheduled_at: datetime
    duration_minutes: int | None = 30
    status: AppointmentStatus = AppointmentStatus.pendiente
    reminder_sent_24h: bool | None = False
    reminder_sent_1h: bool | None = False
    reminder_sent_15min: bool | None = False
    feedback: str | None = None
    interested_after_visit: bool | None = None