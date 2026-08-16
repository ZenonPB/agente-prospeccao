"""Testes do threshold de qualificação configurável por organização.

Cobre:
- função pura `compute_threshold_candidates` (cálculo F1, escolha do ótimo);
- `_persist_scoring` aplicando o threshold configurado por org.
"""
from src.services.analytics_service import compute_threshold_candidates
from database.models import Lead, LeadStatus
from services.enrichment_orchestrator import _persist_scoring


def test_threshold_vazio_retorna_atual():
    """Sem leads no período, mantém o threshold atual sem candidatos."""
    out = compute_threshold_candidates(
        scored=[], converted_ids=set(), current_threshold=70,
    )
    assert out["recommended_threshold"] == 70
    assert out["current_threshold"] == 70
    assert out["candidates"] == []
    assert out["leads_considered"] == 0
    assert "Sem leads pontuados" in out["rationale"]


def test_threshold_escolhe_f1_maximo():
    """Threshold que maximiza F1 sobre convertidos vs qualificados."""
    scored = [
        (95, "a"), (90, "b"), (85, "c"),  # 3 convertidos esperados
        (70, "d"), (65, "e"), (60, "f"),  # acima de 60, sem conversão
        (55, "g"), (50, "h"),             # abaixo, sem conversão
        (40, "i"), (35, "j"),
    ]
    converted = {"a", "b", "c"}
    out = compute_threshold_candidates(
        scored=scored, converted_ids=converted, current_threshold=60,
    )
    assert out["leads_considered"] == 10
    assert out["converted_total"] == 3
    # Limiares candidatos de 30 a 90 (passo 5).
    thresholds = [c["threshold"] for c in out["candidates"]]
    assert thresholds[0] == 30
    assert thresholds[-1] == 90
    # Em algum candidato, F1 deve melhorar vs threshold 60 (recall baixo).
    f1_60 = next(c for c in out["candidates"] if c["threshold"] == 60)["f1"]
    f1_85 = next(c for c in out["candidates"] if c["threshold"] == 85)["f1"]
    assert f1_85 >= f1_60


def test_threshold_recomendado_eh_o_max_f1():
    """O `recommended_threshold` corresponde ao candidato com maior F1."""
    scored = [(s, f"id-{s}") for s in [10, 20, 30, 80, 85, 90, 95, 99]]
    converted = {"id-80", "id-85", "id-90", "id-95", "id-99"}
    out = compute_threshold_candidates(
        scored=scored, converted_ids=converted, current_threshold=60,
    )
    best_candidate = max(out["candidates"], key=lambda c: c["f1"])
    assert out["recommended_threshold"] == best_candidate["threshold"]


def test_persist_scoring_usa_threshold_da_org():
    """`_persist_scoring` aplica QUALIFICADO quando score >= threshold da org."""
    lead = Lead(qualification_score=0, status=LeadStatus.NOVO)
    scoring_data = {
        "qualification_score": 70,
        "qualification_reason": "test",
        "primary_need": "",
        "priority": "WARM",
        "priority_reasoning": "",
        "executive_summary": "",
        "pitch_angle": "",
        "suggested_subject": "",
        "score_factors": [],
        "evidence": [],
    }
    _persist_scoring(lead, scoring_data, enrichment=None, qualification_threshold=80)
    assert lead.qualification_score == 70
    assert lead.status == LeadStatus.DESQUALIFICADO  # 70 < 80

    lead2 = Lead(qualification_score=0, status=LeadStatus.NOVO)
    _persist_scoring(lead2, scoring_data, enrichment=None, qualification_threshold=60)
    assert lead2.status == LeadStatus.QUALIFICADO  # 70 >= 60


def test_persist_scoring_default_60_compatibilidade():
    """Sem threshold explícito, mantém o comportamento histórico (60)."""
    lead = Lead(qualification_score=0, status=LeadStatus.NOVO)
    scoring_data = {
        "qualification_score": 60,
        "priority": "",
        "score_factors": [],
        "evidence": [],
    }
    _persist_scoring(lead, scoring_data, enrichment=None)
    assert lead.status == LeadStatus.QUALIFICADO  # 60 >= 60

    lead2 = Lead(qualification_score=0, status=LeadStatus.NOVO)
    scoring_data["qualification_score"] = 59
    _persist_scoring(lead2, scoring_data, enrichment=None)
    assert lead2.status == LeadStatus.DESQUALIFICADO  # 59 < 60
