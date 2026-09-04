"""Testes do score vetorial por perfil (doc 02) e why_signals do card (doc 16)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

import pytest  # noqa: E402

from services.scoring_service import AIScoringService, VECTOR_WEIGHTS  # noqa: E402


SVC = AIScoringService(api_key="test")

DIMS = {
    "need": 91, "commercial_fit": 80,
    "digital_maturity": 84, "contactability": 72,
}


def _parsed(vector_extra=None):
    return {
        "qualification_score": 84,
        "priority": "HOT",
        "score_vector": {**DIMS, **(vector_extra or {})},
        "evidence": [],
    }


class TestScoreVector:
    def test_dims_no_range_0_100_e_formula_registra_perfil(self):
        out = SVC._normalize_response(_parsed(), profile_key="web_presence")
        vec = out["score_vector"]
        for dim in ("need", "commercial_fit", "digital_maturity", "contactability"):
            assert 0 <= vec[dim] <= 100
        assert vec["formula_version"] == "vector-v1-web_presence"

    def test_overall_agregado_por_peso_do_perfil(self):
        # Lead com maturidade digital baixa e necessidade alta: os pesos
        # divergentes (digital_maturity 0.4 vs 0.15) têm que mudar o overall.
        lead = {"qualification_score": 70, "score_vector": {
            "need": 90, "commercial_fit": 50,
            "digital_maturity": 20, "contactability": 60}}
        out_web = SVC._normalize_response(lead, profile_key="web_presence")
        out_biz = SVC._normalize_response(
            {"qualification_score": 70, "score_vector": dict(lead["score_vector"])},
            profile_key="business_opportunity")
        assert out_web["score_vector"]["overall"] != out_biz["score_vector"]["overall"]
        w = VECTOR_WEIGHTS["web_presence"]
        expected = round(sum(lead["score_vector"][k] * w[k] for k in w) / sum(w.values()))
        assert out_web["score_vector"]["overall"] == expected

    def test_clamp_de_dimensoes_fora_da_faixa(self):
        out = SVC._normalize_response(
            _parsed({"need": 250, "contactability": -30}),
            profile_key="generic",
        )
        vec = out["score_vector"]
        assert vec["need"] == 100
        assert vec["contactability"] == 0

    def test_llm_nao_pode_inventar_formula_version(self):
        out = SVC._normalize_response(
            _parsed({"formula_version": "prompt-hack"}), profile_key="generic")
        assert out["score_vector"]["formula_version"] == "vector-v1-generic"

    def test_sem_dimensoes_vetor_fica_ausente_compat(self):
        out = SVC._normalize_response({"qualification_score": 50, "evidence": []})
        assert "score_vector" not in out

    def test_ranking_muda_entre_landing_e_erp_para_o_mesmo_lead(self):
        # Lead com alta maturidade digital e baixa necessidade: Landing Page
        # (web_presence) deve pontuar acima de ERP (business_opportunity).
        lead = _parsed({"need": 20, "digital_maturity": 95})
        lp = SVC._normalize_response(lead, profile_key="web_presence")
        erp = SVC._normalize_response(dict(lead), profile_key="business_opportunity")
        assert lp["score_vector"]["overall"] > erp["score_vector"]["overall"]


class TestWhySignals:
    def _lead(self, evidence_val):
        from database.models import Lead
        # Lead transitório (sem DB) — só _lead_summary é exercitado.
        return Lead(evidence=evidence_val, score_vector=None)

    def test_card_so_mostra_titles_de_evidence(self):
        from src.routes.leads import _lead_summary  # API (sys.path via conftest)
        lead = self._lead([
            {"title": "Load time 4800ms", "severity": "ALTO"},
            {"title": "Rating 4.5", "severity": "INFO"},
            {"title": "Sem CTA", "severity": "MEDIO"},
            {"title": "Quarto sinal"},
        ])
        summary = _lead_summary(lead)
        assert summary["why_signals"] == [
            "Load time 4800ms", "Rating 4.5", "Sem CTA"]

    def test_sem_evidencia_card_nao_afirma_nada(self):
        from src.routes.leads import _lead_summary
        assert _lead_summary(self._lead([]))["why_signals"] == []
        assert _lead_summary(self._lead(None))["why_signals"] == []
