"""Unit tests for the Appointment domain aggregate.

Pure domain — no FastAPI, no database.
"""

from datetime import datetime

import pytest

from app.domain.appointments import Appointment, AppointmentStatus


class TestAppointmentStatus:
    def test_is_str_enum(self):
        assert issubclass(AppointmentStatus, str)

    def test_has_exactly_seven_members(self):
        assert len(AppointmentStatus) == 7

    def test_member_values_match_spanish_strings(self):
        assert AppointmentStatus.pendiente.value == "pendiente"
        assert AppointmentStatus.confirmada.value == "confirmada"
        assert AppointmentStatus.realizada.value == "realizada"
        assert AppointmentStatus.no_show.value == "no_show"
        assert AppointmentStatus.cancelada_inquilino.value == "cancelada_inquilino"
        assert AppointmentStatus.cancelada_propietario.value == "cancelada_propietario"
        assert AppointmentStatus.reprogramada.value == "reprogramada"


class TestAppointment:
    @staticmethod
    def _sample(**overrides) -> Appointment:
        base = {
            "id": "appt-123",
            "lead_id": "lead-456",
            "property_id": "prop-789",
            "scheduled_at": datetime(2026, 9, 10, 15, 0, 0),
        }
        base.update(overrides)
        return Appointment(**base)

    def test_full_construction(self):
        appt = self._sample(
            duration_minutes=45,
            status=AppointmentStatus.confirmada,
            reminder_sent_24h=True,
            reminder_sent_1h=False,
            reminder_sent_15min=True,
            feedback="Excelente visita",
            interested_after_visit=True,
        )
        assert appt.id == "appt-123"
        assert appt.lead_id == "lead-456"
        assert appt.property_id == "prop-789"
        assert appt.scheduled_at == datetime(2026, 9, 10, 15, 0, 0)
        assert appt.duration_minutes == 45
        assert appt.status == AppointmentStatus.confirmada
        assert appt.reminder_sent_24h is True
        assert appt.reminder_sent_1h is False
        assert appt.reminder_sent_15min is True
        assert appt.feedback == "Excelente visita"
        assert appt.interested_after_visit is True

    def test_status_defaults_to_pendiente(self):
        appt = self._sample()
        assert appt.status == AppointmentStatus.pendiente

    def test_duration_minutes_defaults_to_30(self):
        appt = self._sample()
        assert appt.duration_minutes == 30

    def test_reminder_flags_default_to_false(self):
        appt = self._sample()
        assert appt.reminder_sent_24h is False
        assert appt.reminder_sent_1h is False
        assert appt.reminder_sent_15min is False

    def test_feedback_defaults_to_none(self):
        appt = self._sample()
        assert appt.feedback is None

    def test_interested_after_visit_defaults_to_none(self):
        appt = self._sample()
        assert appt.interested_after_visit is None

    def test_is_frozen(self):
        appt = self._sample()
        try:
            appt.status = AppointmentStatus.realizada  # type: ignore[misc]
            assert False, "frozen dataclass should reject mutation"
        except AttributeError:
            pass

    def test_requires_required_fields(self):
        with pytest.raises(TypeError):
            Appointment()  # type: ignore[call-arg]