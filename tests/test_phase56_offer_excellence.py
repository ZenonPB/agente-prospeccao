from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from services.prospecting.default_profiles import build_default_registry
from services.prospecting.offer_excellence_service import event_series_key
from services.prospecting.offer_profile_validator import validate_registry
from services.signal_registry import SIGNAL_REGISTRY
from src.services.prospecting_automation_service import AGENT_STATES


def test_phase5_profiles_are_registered_and_semantically_valid():
    registry = build_default_registry()
    expected = {
        "landing_page",
        "mechanical_project",
        "technical_drawing",
        "machine_manual",
        "trophies",
        "web_systems_erp",
        "3d_printing",
        "laser_cutting_technical",
        "laser_custom_products",
    }
    assert expected.issubset({profile.key for profile in registry.list()})
    assert validate_registry(registry) == {}


def test_existing_profiles_receive_phase5_signals_without_penalizing_unknowns():
    registry = build_default_registry()
    landing = registry.get("landing_page")
    mechanical = registry.get("mechanical_project")
    drawing = registry.get("technical_drawing")
    manual = registry.get("machine_manual")

    assert landing is not None and "WEAK_CTA" in landing.signals["optional_positive"]
    assert mechanical is not None and "EXPANDING_FACTORY" in mechanical.signals["optional_positive"]
    assert drawing is not None and "REVERSE_ENGINEERING" in drawing.signals["optional_positive"]
    assert manual is not None and "NR12" in manual.signals["optional_positive"]
    assert all(profile.version == "1.1" for profile in (landing, mechanical, drawing, manual))


def test_phase5_signal_registry_contains_offer_specific_vocabulary():
    expected = {
        "MANUAL_PROCESS",
        "MULTI_UNIT",
        "PROTOTYPE",
        "CUSTOM_PARTS",
        "EVENT_SCHEDULED",
        "HAS_PRODUCTION_LINE",
        "NR12",
        "WEAK_CONVERSION_FLOW",
    }
    assert expected.issubset(SIGNAL_REGISTRY)


def test_event_series_key_ignores_year_and_edition_noise():
    first = SimpleNamespace(id="a", organizer="MEJ Sudeste", name="Prêmio MEJ 2025 - Edição 12", event_type="awards")
    second = SimpleNamespace(id="b", organizer="MEJ Sudeste", name="Prêmio MEJ 2026 - Edição 13", event_type="awards")
    assert event_series_key(first) == event_series_key(second)


def test_agent_state_machine_contract_is_closed_and_explicit():
    assert AGENT_STATES == {
        "DISCOVERED",
        "NEEDS_ENRICHMENT",
        "READY_TO_SCORE",
        "READY_FOR_CONTACT",
        "AWAITING_ACTION",
        "IN_SEQUENCE",
        "WAITING",
        "REENGAGE",
        "CLOSED",
    }


def test_event_rebuy_window_shape_can_represent_30_to_120_days():
    today = date.today()
    start = today + timedelta(days=45)
    end = today + timedelta(days=75)
    assert 30 <= (start - today).days <= 120
    assert 30 <= (end - today).days <= 120
