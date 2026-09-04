"""Persistência do score_vector (docs/melhorias/02) — compatibilidade com o legado."""
from database.models import Lead
from services.enrichment_orchestrator import _persist_scoring
from services.scoring_service import AIScoringService, VECTOR_WEIGHTS


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
    parsed = {"score_vector": {"need": 150, "contactability": -10, "digital_maturity": 50}}
    out = svc._normalize_response(parsed)
    vec = out["score_vector"]
    assert vec["need"] == 100
    assert vec["contactability"] == 0
    # `overall` é agregação ponderada pelo perfil (doc 02) — nunca média opaca.
    w = VECTOR_WEIGHTS["generic"]
    expected = round((100 * w["need"] + 0 * w["contactability"] + 50 * w["digital_maturity"])
                     / (w["need"] + w["contactability"] + w["digital_maturity"]))
    assert vec["overall"] == expected
    assert vec["formula_version"] == "vector-v1-generic"
    # qualification_score segue obrigatório/default.
    assert out["qualification_score"] == 0


def test_normalize_response_sem_vetor_nao_cria_chave():
    svc = AIScoringService()
    out = svc._normalize_response({"score_factors": [], "evidence": []})
    assert "score_vector" not in out


def test_formula_version_e_do_backend_registra_o_perfil():
    """A LLM não escolhe a fórmula: o backend registra o perfil usado na
    agregação (doc 02 — auditoria da fórmula)."""
    svc = AIScoringService()
    out = svc._normalize_response({
        "score_vector": {"need": 80, "formula_version": "erp-v2"},
    })
    assert out["score_vector"]["formula_version"] == "vector-v1-generic"


def test_overall_nao_conta_metadados_na_media():
    """`formula_version`/`rationale` não são dimensões: só as dims conhecidas
    entram na agregação ponderada (need 80, icp_fit fora dos pesos → ignora,
    usa need=80 com peso total do need) → overall = 80."""
    svc = AIScoringService()
    out = svc._normalize_response({
        "score_vector": {"need": 80, "icp_fit": 60, "formula_version": "erp-v2"},
    })
    assert out["score_vector"]["overall"] == 80
    assert "icp_fit" not in out["score_vector"] or \
        out["score_vector"].get("icp_fit") == 60
