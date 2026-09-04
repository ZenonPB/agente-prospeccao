"""Testes do Discovery Planner (Fase 3 — doc 22).

Seam: `DiscoveryPlanner.plan(profile, lead_context)` e `plan_discovery()`.
Capacidade: produzir plano auditável de descoberta pela oferta (providers + budget + queries),
não executa — só planeja.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.discovery_planner_service import (  # noqa: E402
    DiscoveryPlanner,
    plan_discovery,
    cnae_discovery_plan,
)


class TestPlanDiscovery:
    def test_business_opportunity_inclui_google_places_e_cnae(self):
        plan = plan_discovery({"profile_key": "business_opportunity"})
        types = [p["type"] for p in plan["providers"]]
        assert "google_places" in types
        assert "cnae_discovery" in types

    def test_web_presence_inclui_google_places(self):
        plan = plan_discovery({"profile_key": "web_presence"})
        assert len(plan["providers"]) > 0
        assert plan["providers"][0]["type"] == "google_places"

    def test_target_candidates_e_definido(self):
        plan = plan_discovery({"profile_key": "web_presence"})
        assert plan["target_candidates"] > 0
        assert isinstance(plan["target_candidates"], int)

    def test_cada_provider_tem_budget(self):
        plan = plan_discovery({"profile_key": "web_presence"})
        for p in plan["providers"]:
            assert "budget" in p
            assert p["budget"] > 0


class TestDiscoveryPlanner:
    """Seam: DiscoveryPlanner.plan() — interface com seam profundo."""

    def test_plan_anota_plan_source_e_audit(self):
        planner = DiscoveryPlanner()
        result = planner.plan({"profile_key": "web_presence"})
        assert result["plan_source"] == "prospecting_profile + capability_registry"
        assert "audit_notes" in result
        assert len(result["audit_notes"]) >= 3

    def test_plan_passa_profile_key_para_audit(self):
        planner = DiscoveryPlanner()
        result = planner.plan({"profile_key": "industrial"})
        assert "profile=industrial" in result["audit_notes"]
        assert "providers=" in result["audit_notes"][1]

    def test_plan_aceita_lead_context(self):
        planner = DiscoveryPlanner()
        result = planner.plan(
            {"profile_key": "web_presence"},
            lead_context={"has_website": False, "has_cnpj": True},
        )
        assert result["profile_key"] == "web_presence"


class TestCnaeDiscoveryPlan:
    def test_basico(self):
        plan = cnae_discovery_plan("2512-8/00", state="SP", city="Araraquara")
        assert plan["type"] == "cnae_discovery"
        assert plan["filters"]["cnae_code"] == "2512-8/00"
        assert plan["filters"]["state"] == "SP"
        assert plan["filters"]["city"] == "Araraquara"

    def test_sem_filtros_opcionais(self):
        plan = cnae_discovery_plan("2512-8/00")
        assert "cnae_code" in plan["filters"]
        # city/state devem ser None e removidos (serialização limpa)
        assert "city" not in plan["filters"]
        assert "state" not in plan["filters"]
