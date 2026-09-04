"""Persistência do score_vector (docs/melhorias/02) — compatibilidade com o legado."""
from database.models import Lead
from services.enrichment_orchestrator import _persist_scoring
from services.scoring_service import AIScoringService


def _lead():
    return Lead(company_name="X", city="São Paulo")


def test_score_vector_persistido_quando_presente():
    lead = _lead()
    scoring = {
        "qualification_score": 75,
        "score_vector": {"need": 91, "icp_fit": 85, "overall": 75,
                         "formula_version": "landing-page-v1"},
    }
    _persist_scoring(lead, scoring, None, 60)
    assert lead.score_vector["overall"] == 75
    assert lead.score_vector["need"] == 91
    assert lead.score_vector["formula_version"] == "landing-page-v1"
    # Legado intocado — fonte de verdade do funil continua o mesmo.
    assert lead.qualification_score == 75
    assert lead.status.value == "QUALIFICADO"


def test_score_vector_nulo_quando_ausente():
    lead = _lead()
    _persist_scoring(lead, {"qualification_score": 30}, None, 60)
    assert lead.score_vector is None
    assert lead.qualification_score == 30
    assert lead.status.value == "DESQUALIFICADO"


def test_normalize_response_clampa_dimensoes_e_deriva_overall():
    svc = AIScoringService()
    parsed = {"score_vector": {"need": 150, "icp_fit": -10, "intent": 50}}
    out = svc._normalize_response(parsed)
    vec = out["score_vector"]
    assert vec["need"] == 100
    assert vec["icp_fit"] == 0
    assert vec["overall"] == round((100 + 0 + 50) / 3)
    assert vec["formula_version"] == "generic-v1"
    # qualification_score segue obrigatório/default.
    assert out["qualification_score"] == 0


def test_normalize_response_sem_vetor_nao_cria_chave():
    svc = AIScoringService()
    out = svc._normalize_response({"score_factors": [], "evidence": []})
    assert "score_vector" not in out


def test_normalize_response_preserva_formula_version():
    svc = AIScoringService()
    out = svc._normalize_response({
        "score_vector": {"need": 80, "formula_version": "erp-v2"},
    })
    assert out["score_vector"]["formula_version"] == "erp-v2"


def test_overall_nao_conta_formula_version_na_media():
    """Bug corrigido: com o código antigo, 80+60 dividia por 3 (contava
    formula_version como dimensão) → 47; correto é média das dimensões = 70."""
    svc = AIScoringService()
    out = svc._normalize_response({
        "score_vector": {"need": 80, "icp_fit": 60, "formula_version": "erp-v2"},
    })
    assert out["score_vector"]["overall"] == 70
