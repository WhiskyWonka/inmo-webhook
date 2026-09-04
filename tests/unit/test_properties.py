"""Unit tests for the PropertyLog value object.

Pure domain — no FastAPI, no database.
"""

import pytest

from app.domain.properties import PropertyLog


class TestPropertyLog:
    def test_full_construction(self):
        log = PropertyLog(
            id="abc-123",
            property_id="prop-456",
            field_changed="rent_price_ars",
            old_value="100000",
            new_value="150000",
        )
        assert log.id == "abc-123"
        assert log.property_id == "prop-456"
        assert log.field_changed == "rent_price_ars"
        assert log.old_value == "100000"
        assert log.new_value == "150000"

    def test_changed_by_defaults_to_sistema(self):
        log = PropertyLog(
            id="1",
            property_id="p1",
            field_changed="status",
            old_value=None,
            new_value="reservado",
        )
        assert log.changed_by == "sistema"

    def test_explicit_changed_by(self):
        log = PropertyLog(
            id="1",
            property_id="p1",
            field_changed="status",
            old_value=None,
            new_value="reservado",
            changed_by="agente-7",
        )
        assert log.changed_by == "agente-7"

    def test_old_and_new_value_accept_none(self):
        log = PropertyLog(
            id="1",
            property_id="p1",
            field_changed="address",
            old_value=None,
            new_value=None,
        )
        assert log.old_value is None
        assert log.new_value is None

    def test_is_frozen(self):
        log = PropertyLog(
            id="1",
            property_id="p1",
            field_changed="status",
            old_value=None,
            new_value="reservado",
        )
        try:
            log.field_changed = "other"  # type: ignore[misc]
            assert False, "frozen dataclass should reject mutation"
        except AttributeError:
            pass

    def test_requires_field_changed(self):
        with pytest.raises(TypeError):
            PropertyLog(id="1", property_id="p1")  # type: ignore[call-arg]

    def test_rejects_empty_field_changed(self):
        with pytest.raises(ValueError, match="field_changed"):
            PropertyLog(
                id="1",
                property_id="2",
                field_changed="",
                old_value=None,
                new_value=None,
            )

    def test_rejects_whitespace_only_field_changed(self):
        with pytest.raises(ValueError, match="field_changed"):
            PropertyLog(
                id="1",
                property_id="2",
                field_changed="   ",
                old_value=None,
                new_value=None,
            )

    def test_accepts_normal_field_changed(self):
        log = PropertyLog(
            id="1",
            property_id="2",
            field_changed="status",
            old_value=None,
            new_value="reservado",
        )
        assert log.field_changed == "status"
