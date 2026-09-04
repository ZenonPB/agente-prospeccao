"""Testes do Learning Service (Fase 3 — docs 10 e 11).

Seam: `record_outcome`, `compute_niche_prior`, `precision_at_k`,
       `match_golden_patterns`, `ThreeLevelLearning.resolve()`.
Capacidade: registrar outcomes e calcular prior de nicho, precision@k,
padrões dourados, e learning em 3 níveis (GLOBAL/VERTICAL/ORG).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.learning_service import (  # noqa: E402
    record_outcome,
    compute_niche_prior,
    precision_at_k,
    match_golden_patterns,
    three_level_learning,
)


class TestRecordOutcome:
    def test_record_outcome_nao_explode(self):
        # Apenas verifica que a função não quebra com entradas válidas
        record_outcome("org-test-1", "Landing Pages", "psicologia", "WON")
        record_outcome("org-test-1", "Landing Pages", "psicologia", "LOST")

    def test_record_com_channel(self):
        record_outcome("org-test-2", "X", "Y", "WON", channel="email")


class TestComputeNichePrior:
    def test_sem_outcomes_prior_zero(self):
        prior = compute_niche_prior("org-sem-outcomes", "Landing Pages", "psicologia")
        assert prior["total_outcomes"] == 0
        assert prior["conversion_rate"] == 0.0
        assert prior["prior_score"] == 0.0

    def test_com_outcomes_calcula_conversion(self):
        org = "org-prior-test"
        # Limpa counters anteriores (reutilização de módulo)
        for _ in range(3):
            record_outcome(org, "Landing Pages", "psicologia", "WON")
        record_outcome(org, "Landing Pages", "psicologia", "NEW")
        prior = compute_niche_prior(org, "Landing Pages", "psicologia")
        # 3 WON em 4 oportunidades (WON/MEETING/REPLIED/QUALIFIED/NEW) = 75%
        assert prior["conversion_rate"] == 75.0


class TestPrecisionAtK:
    def test_sem_leads_retorna_zero(self):
        r = precision_at_k([], k=5)
        assert r["precision_at_k"] == 0.0
        assert r["window_size"] == 0

    def test_top_k_com_todos_positivos(self):
        ranked = [{"outcome": "WON"}, {"outcome": "WON"}, {"outcome": "WON"}]
        r = precision_at_k(ranked, k=3)
        assert r["precision_at_k"] == 1.0
        assert r["positive_count"] == 3

    def test_top_k_misto(self):
        ranked = [{"outcome": "WON"}, {"outcome": "LOST"}, {"outcome": "WON"}]
        r = precision_at_k(ranked, k=3)
        assert r["precision_at_k"] == round(2/3, 3)

    def test_k_maior_que_lista(self):
        ranked = [{"outcome": "WON"}]
        r = precision_at_k(ranked, k=10)
        # Janela limita-se ao tamanho da lista
        assert r["window_size"] == 1


class TestGoldenPatterns:
    def test_padrao_web_presence_no_site(self):
        matches = match_golden_patterns("web_presence", {
            "NO_OWN_WEBSITE": True,
            "GOOGLE_RATING_COUNT": ">=5",
        })
        assert len(matches) >= 1
        assert matches[0]["pattern_id"] == "web_presence_no_site"

    def test_sem_match(self):
        matches = match_golden_patterns("web_presence", {
            "NO_OWN_WEBSITE": False,
        })
        assert matches == []


class TestThreeLevelLearning:
    def test_precedencia_org_sobre_vertical_sobre_global(self):
        tl = three_level_learning
        tl.set_global("k1", "G")
        tl.set_vertical("v1", "k1", "V")
        tl.set_org("o1", "k1", "O")
        r1 = tl.resolve("k1", "v1", "o1")
        r2 = tl.resolve("k1", "v1", "outro-org")
        r3 = tl.resolve("k1", "outro-v", "outro-org")
        assert r1["source"] == "ORGANIZATION" and r1["value"] == "O"
        assert r2["source"] == "VERTICAL" and r2["value"] == "V"
        assert r3["source"] == "GLOBAL" and r3["value"] == "G"
