"""Guards determinísticos de presença de site no scoring (issue "sem site").

Cobre o `_contradicts_site_state` e a normalização da resposta da LLM
(`_normalize_response(has_website=...)`), que removem evidências que
contradizem o fato cadastral de presença/ausência de website. Sem rede —
funções puras.
"""
from services.scoring_service import AIScoringService, _contradicts_site_state


def _evidence(title="", description="", source="dados cadastrais"):
    return {"type": "business", "severity": "ALTO", "title": title,
            "description": description, "source": source}


def test_contradiz_ausencia_de_site_quando_lead_tem_website():
    assert _contradicts_site_state(_evidence(title="Sem site próprio"), has_website=True)
    assert _contradicts_site_state(
        _evidence(description="O lead não tem um site institucional básico."),
        has_website=True,
    )
    assert _contradicts_site_state(_evidence(title="Ausência de presença digital"), has_website=True)


def test_nao_remove_evidencias_legitimas_quando_tem_website():
    assert not _contradicts_site_state(_evidence(title="WordPress detectado"), has_website=True)
    assert not _contradicts_site_state(_evidence(title="Sem e-commerce"), has_website=True)
    assert not _contradicts_site_state(_evidence(title="Site com SEO fraco"), has_website=True)


def test_remove_claim_de_site_quando_lead_nao_tem():
    assert _contradicts_site_state(_evidence(title="Tem website próprio"), has_website=False)
    assert _contradicts_site_state(
        _evidence(description="Possui um site institucional ativo."), has_website=False
    )
    assert not _contradicts_site_state(_evidence(title="Sem site próprio"), has_website=False)


def test_normalize_remove_sem_site_quando_lead_tem_website():
    svc = AIScoringService(api_key="test")
    parsed = {
        "qualification_score": 85,
        "evidence": [
            _evidence(title="Sem site próprio", description="O lead não tem site."),
            _evidence(title="WordPress + Elementor", description="CMS detectado."),
        ],
        "score_factors": [],
    }
    out = svc._normalize_response(parsed, has_website=True)
    titles = [e["title"] for e in out["evidence"]]
    assert "Sem site próprio" not in titles
    assert "WordPress + Elementor" in titles


def test_normalize_mantem_sem_site_quando_lead_nao_tem():
    svc = AIScoringService(api_key="test")
    parsed = {
        "qualification_score": 60,
        "evidence": [_evidence(title="Sem site próprio", description="Usa Instagram.")],
        "score_factors": [],
    }
    out = svc._normalize_response(parsed, has_website=False)
    assert [e["title"] for e in out["evidence"]] == ["Sem site próprio"]
