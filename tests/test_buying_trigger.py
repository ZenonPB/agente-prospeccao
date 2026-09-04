"""Testes do Buying Trigger (Fase 3 — doc 26).

Seam: `detect_buying_triggers(events)` e `icp_vs_intent(profile, intent_score, icp_match)`.
Capacidade: converter intent events em triggers acionáveis e distinguir ICP (perfil
fixo) de Intent (evento temporal) com classificação TIMELY/PROFILED/COLD.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.buying_trigger_service import (  # noqa: E402
    detect_buying_triggers,
    icp_vs_intent,
)


class TestDetectBuyingTriggers:
    def test_hiring_vira_trigger_expansao(self):
        triggers = detect_buying_triggers([
            {"key": "HIRING", "confidence": 0.9, "evidence_refs": ["vaga"]},
        ])
        assert len(triggers) == 1
        assert triggers[0]["trigger"] == "HIRING"
        assert "Expansão" in triggers[0]["label"]
        assert triggers[0]["confidence"] == 0.9

    def test_evento_sem_mapeamento_e_descartado(self):
        triggers = detect_buying_triggers([
            {"key": "UNKNOWN_KEY", "confidence": 0.9, "evidence_refs": []},
        ])
        assert triggers == []

    def test_multiplos_triggers_preservam_ordem(self):
        triggers = detect_buying_triggers([
            {"key": "HIRING", "confidence": 0.9, "evidence_refs": []},
            {"key": "NEW_BRANCH", "confidence": 0.8, "evidence_refs": []},
        ])
        assert [t["trigger"] for t in triggers] == ["HIRING", "NEW_BRANCH"]


class TestIcpVsIntent:
    def test_intent_score_alto_e_timely(self):
        result = icp_vs_intent("industrial", intent_score=75.0, icp_match=True)
        assert result["classification"] == "TIMELY"
        assert result["frame"] == "intent"

    def test_intent_score_baixo_e_profiled_se_match(self):
        result = icp_vs_intent("industrial", intent_score=30.0, icp_match=True)
        assert result["classification"] == "PROFILED"
        assert result["frame"] == "icp"

    def test_sem_intent_e_sem_match_e_cold(self):
        result = icp_vs_intent("generic", intent_score=20.0, icp_match=False)
        assert result["classification"] == "COLD"
        assert result["frame"] == "cold"

    def test_icp_e_resolvido_por_perfil(self):
        result = icp_vs_intent("web_presence", intent_score=0, icp_match=True)
        assert "icp" in result
        assert result["icp"]["has_site"] == "weak_or_none"
