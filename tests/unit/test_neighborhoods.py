"""Unit tests for the Neighborhood value object and Zone enum.

Pure domain — no FastAPI, no database.
"""

import pytest

from app.domain.neighborhoods import Neighborhood, Zone


class TestZone:
    def test_all_members_present(self):
        expected = {"norte", "centro", "sur", "oeste", "gba_norte", "gba_oeste", "gba_sur"}
        assert {z.value for z in Zone} == expected

    def test_member_count(self):
        assert len(Zone) == 7

    def test_str_enum_values_are_strings(self):
        for z in Zone:
            assert isinstance(z.value, str)

    def test_zone_compares_cleanly_with_string(self):
        assert Zone.norte == "norte"
        assert Zone("centro") == Zone.centro

    def test_zone_rejects_out_of_enum_value(self):
        with pytest.raises(ValueError):
            Zone("no_such_zone")


class TestNeighborhood:
    def test_minimal_construction(self):
        n = Neighborhood(id="abc-123", name="Palermo", zone=Zone.norte)
        assert n.id == "abc-123"
        assert n.name == "Palermo"
        assert n.zone == Zone.norte
        assert n.city == "CABA"

    def test_explicit_city(self):
        n = Neighborhood(id="x", name="Tigre", zone=Zone.gba_norte, city="GBA")
        assert n.city == "GBA"

    def test_is_frozen(self):
        n = Neighborhood(id="1", name="Recoleta", zone=Zone.centro)
        try:
            n.name = "other"  # type: ignore[misc]
            assert False, "frozen dataclass should reject mutation"
        except AttributeError:
            pass

    def test_buildable_across_all_zones(self):
        for zone in Zone:
            n = Neighborhood(id="id", name=f"Barrio {zone.value}", zone=zone)
            assert n.zone == zone
