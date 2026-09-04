"""Regressão do gate de pre-scoring por vertical (revisão da Fase 2).

Garante que os pesos/thresholds dos seeds NÃO descartam falsamente o
público-alvo de cada vertical:

1. Engenharia: a decisão vive de CNAE/porte (pós-gate); pré-score não tem
   dados para descartar nenhum candidato razoável.
2. Desenvolvimento de Sites: empresa COM site (site desatualizado = ICP
   clássico) precisa passar.
3. ERP: empresa com site institucional sem sistema (= público-alvo) precisa
   passar; só presença zero é cortada.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from seeds.scoring_templates import DEFAULT_TEMPLATES  # noqa: E402
from services.candidate_pre_scoring_service import CandidatePreScoringService  # noqa: E402
from services.prospecting_profile_service import resolve_prospecting_profile  # noqa: E402

SVC = CandidatePreScoringService()


def _seed(label):
    matches = [t for t in DEFAULT_TEMPLATES if t["service_label"].startswith(label)]
    assert len(matches) == 1, f"seed {label!r}"
    return matches[0]


def _score(seed_label, item):
    profile = resolve_prospecting_profile(_seed(seed_label))
    return SVC.score_candidate(item, profile), profile


class TestGateVertical:
    def test_engenharia_melhor_candidato_passa(self):
        item = {"name": "Fabricante", "phone": "16 111",
                "rating": 5.0, "rating_count": 500}
        scored, profile = _score("Engenharia Mecânica", item)
        assert scored["eligible_for_enrichment"], scored["summary"]

    def test_engenharia_candidato_sem_nenhuma_presenca_pode_cair(self):
        item = {"name": "Fantasma", "website": None, "phone": None,
                "rating": None, "rating_count": None}
        scored, _ = _score("Engenharia Mecânica", item)
        # sem nenhum sinal o score é 0 — só aqui é aceitável descartar
        assert scored["discovery_score"] == 0

    def test_sites_empresa_com_site_passa(self):
        item = {"name": "Ind Automotiva", "website": "https://site.com.br",
                "phone": "16 222", "rating": 4.6, "rating_count": 40}
        scored, _ = _score("Desenvolvimento de Sites", item)
        assert scored["eligible_for_enrichment"], scored["summary"]

    def test_erp_site_institucional_sem_sistema_passa(self):
        item = {"name": "Metalúrgica", "website": "https://metal.com",
                "phone": "16 333", "rating": 4.3}
        scored, _ = _score("Aplicações Web / ERP", item)
        assert scored["eligible_for_enrichment"], scored["summary"]

    def test_erp_sem_nenhuma_presenca_nao_passa(self):
        item = {"name": "Sem Presença", "website": None, "phone": None,
                "rating": None, "rating_count": None}
        scored, _ = _score("Aplicações Web / ERP", item)
        assert not scored["eligible_for_enrichment"], scored["summary"]