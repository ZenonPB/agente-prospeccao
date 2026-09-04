"""Testes do template dedicado de Landing Pages (docs/melhorias/03).

Landing Page é uma venda diferente de site institucional: o prospect ideal
já tem tráfego/reputação/presença social mas não converte. Os testes
garantem que o seed distingue presença digital sem conversão de ausência
total de demanda — sem depender de banco.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from seeds.scoring_templates import DEFAULT_TEMPLATES  # noqa: E402
from services.candidate_pre_scoring_service import CandidatePreScoringService  # noqa: E402
from services.prospecting_profile_service import resolve_prospecting_profile  # noqa: E402


def _landing_template():
    matches = [t for t in DEFAULT_TEMPLATES if t["service_label"] == "Landing Pages"]
    assert len(matches) == 1, "seed deve ter exatamente 1 template de Landing Pages"
    return matches[0]


def _score(item):
    tmpl = _landing_template()
    profile = resolve_prospecting_profile(tmpl)
    return CandidatePreScoringService().score_candidate(item, profile)


class TestLandingPageSeed:
    def test_template_presente_com_perfil_web_presence(self):
        tmpl = _landing_template()
        assert tmpl["requires_technical_report"] is False
        assert tmpl["prescoring_config"]["profile"] == "web_presence"
        assert tmpl["prescoring_config"]["enabled"] is True

    def test_nao_depende_de_criterios_de_erp_engenharia(self):
        tmpl = _landing_template()
        # Sem dados cadastrais (CNAE/porte) como pré-requisito; enrichment
        # social/site primeiro.
        assert "cnpj_receita" not in tmpl["enrichment_steps"]

    def test_instagram_80_avaliacoes_sem_site_pontua_alto(self):
        item = {
            "name": "Clínica Bem Estar",
            "website": None,
            "instagram_url": "@clinicabemestar",
            "phone": "16 99999-0000",
            "rating": 4.5,
            "rating_count": 80,
        }
        scored = _score(item)
        assert scored["discovery_score"] >= 60, scored["summary"]
        assert scored["eligible_for_enrichment"] is True

    def test_sem_site_sem_reviews_sem_social_nao_e_hot(self):
        item = {"name": "Sem Presença", "website": None, "phone": "16 3333-0000"}
        scored = _score(item)
        assert scored["discovery_score"] < 45, scored["summary"]
        assert scored["eligible_for_enrichment"] is False

    def test_sinais_fact_em_todos_os_casos(self):
        item = {"name": "X", "website": None, "instagram_url": "@x",
                "phone": "11 1", "rating": 4.2, "rating_count": 40}
        scored = _score(item)
        assert all(s["epistemic"] == "FACT" for s in scored["signals"])