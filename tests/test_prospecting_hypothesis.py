"""Testes do Prospecting Hypothesis (Fase 3 — doc 28).

Seam: `build_hypothesis(profile_key, lead_context)` e `vertical_pack_for(profile_key)`.
Capacidade: declarar hipótese comercial (problem/hypothesis/expected_lift/key_signals)
e pack de providers de enriquecimento por perfil.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.prospecting_hypothesis_service import (  # noqa: E402
    build_hypothesis,
    vertical_pack_for,
)


class TestBuildHypothesis:
    def test_perfil_industrial_tem_lift_proprio(self):
        h = build_hypothesis("industrial")
        assert h["profile_key"] == "industrial"
        assert h["expected_lift"] == 0.30
        assert "problem" in h
        assert "hypothesis" in h
        assert len(h["key_signals"]) > 0

    def test_perfil_web_presence_tem_lift_proprio(self):
        h = build_hypothesis("web_presence")
        assert h["expected_lift"] == 0.40
        assert h["key_signals"] != build_hypothesis("industrial")["key_signals"]

    def test_perfil_desconhecido_cai_no_generic(self):
        h = build_hypothesis("perfil_inexistente")
        assert h["profile_key"] == "perfil_inexistente"
        # Cai no generic mas mantém o profile_key do request
        assert h["expected_lift"] == 0.25

    def test_lead_context_e_anexado(self):
        ctx = {"company_name": "Teste"}
        h = build_hypothesis("industrial", lead_context=ctx)
        assert h["lead_context"] == ctx

    def test_cada_perfil_tem_problem_e_hypothesis_distintos(self):
        a = build_hypothesis("web_presence")
        b = build_hypothesis("business_opportunity")
        c = build_hypothesis("industrial")
        # Problemas e hipóteses DEVEM ser específicos (consolidação §27: "Não
        # duplicar inteligência comercial")
        assert a["problem"] != b["problem"] != c["problem"]
        assert a["hypothesis"] != b["hypothesis"] != c["hypothesis"]


class TestVerticalPack:
    def test_web_presence_tem_technical_enrichment(self):
        pack = vertical_pack_for("web_presence")
        assert "technical_enrichment" in pack["enrichment_pack"]

    def test_industrial_tem_cnae_discovery(self):
        pack = vertical_pack_for("industrial")
        assert "cnae_discovery" in pack["enrichment_pack"]

    def test_perfil_desconhecido_cai_no_generic(self):
        pack = vertical_pack_for("perfil_inexistente")
        assert pack["profile_key"] == "perfil_inexistente"
        assert len(pack["enrichment_pack"]) > 0
