"""Testes do Decision Maker Strategy (Fase 3 — doc 25).

Seam: `resolve_contact_strategy(profile_key)`.
Capacidade: declarar ordem de providers de contato + prioridade de canais por perfil.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.decision_maker_strategy_service import resolve_contact_strategy  # noqa: E402


class TestResolveContactStrategy:
    def test_industrial_prioriza_cnpj_qsa(self):
        s = resolve_contact_strategy("industrial")
        assert s["profile_key"] == "industrial"
        assert s["provider_order"][0] == "cnpj_qsa"
        assert "cnpj_qsa" in s["provider_order"]

    def test_web_presence_prioriza_domain_first(self):
        s = resolve_contact_strategy("web_presence")
        assert s["provider_order"][0] == "domain_first_person"

    def test_business_opportunity_prioriza_cnpj(self):
        s = resolve_contact_strategy("business_opportunity")
        assert s["provider_order"][0] == "cnpj_qsa"

    def test_perfil_desconhecido_cai_no_generic(self):
        s = resolve_contact_strategy("perfil_inexistente")
        assert s["profile_key"] == "perfil_inexistente"
        # generic usa linkedin_search como primeira opção
        assert s["provider_order"][0] == "linkedin_search"

    def test_channel_priority_e_diferente_por_perfil(self):
        """Consolidação §27: Não duplicar inteligência — cada perfil deve ter canais distintos."""
        web = resolve_contact_strategy("web_presence")["channel_priority"]
        ind = resolve_contact_strategy("industrial")["channel_priority"]
        # Industrial prioriza phone antes de linkedin; web não
        assert ind != web

    def test_stop_after_e_calculado(self):
        s = resolve_contact_strategy("industrial")
        assert s["stop_after"] >= 1
        assert s["stop_after"] <= len(s["provider_order"])

    def test_provider_order_preserva_ordem_declarada(self):
        s = resolve_contact_strategy("web_presence")
        # A ordem importa: domain_first → linkedin → email_pattern
        order = s["provider_order"]
        assert order.index("domain_first_person") < order.index("email_pattern_inference")
