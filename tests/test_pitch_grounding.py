"""Testes do grounding do pitch/suggested_subject (Frente A).

Valida que alegações técnico/UX inventadas ("sem responsividade", "site
atualizado", etc. sem evidência correspondente) são rejeitadas e substituídas
por um pitch determinístico construído da evidência aprovada mais forte.
"""
from services.scoring_service import (
    AIScoringService,
    _build_grounded_pitch,
    _pitch_is_grounded,
)

EVIDENCE = [
    {
        "type": "technical",
        "severity": "ALTO",
        "title": "Formulário de contato ausente",
        "description": "Formulário de contato ausente na página (HTML sem <form>).",
        "source": "relatório técnico",
    },
    {
        "type": "technical",
        "severity": "BAIXO",
        "title": "SSL/HTTPS válido",
        "description": "SSL/HTTPS válido e redirecionamento HTTP→HTTPS ativo.",
        "source": "relatório técnico",
    },
]


def test_pitch_claiming_unresponsive_without_evidence_is_rejected():
    text = "O site não é responsivo e está perdendo conversão."
    assert _pitch_is_grounded(text, EVIDENCE) is False


def test_pitch_claiming_outdated_without_cms_evidence_is_rejected():
    text = "O site está desatualizado e isso afasta clientes."
    assert _pitch_is_grounded(text, EVIDENCE) is False


def test_pitch_citing_grounded_evidence_is_kept():
    text = "Não encontramos formulário de contato na página da empresa."
    assert _pitch_is_grounded(text, EVIDENCE) is True


def test_generic_subject_without_footprint_is_rejected():
    assert _pitch_is_grounded("Proposta de parceria", EVIDENCE) is False


def test_fallback_pitch_cites_evidence():
    out = _build_grounded_pitch(EVIDENCE, target_service="Desenvolvimento de Sites")
    assert out["pitch_angle"]
    assert "formul" in out["pitch_angle"].lower()
    assert out["suggested_subject"]


def test_normalize_replaces_hallucinated_pitch():
    parsed = {
        "qualification_score": 70,
        "pitch_angle": "O site é atualizado mas sem responsividade, perde conversão.",
        "suggested_subject": "Proposta de parceria",
        "evidence": EVIDENCE,
        "score_factors": [],
    }
    result = AIScoringService()._normalize_response(
        parsed, has_website=True, target_service="Desenvolvimento de Sites"
    )
    # Fallback determinístico: cita a evidência real (formulário ausente).
    assert result["pitch_angle"]
    assert "formul" in result["pitch_angle"].lower()
    assert "atualizado" not in result["pitch_angle"].lower()
    assert "responsiv" not in result["pitch_angle"].lower()
    assert result["suggested_subject"]