"""Pré-scoring determinístico de candidatos (docs/melhorias/01)."""
from services.candidate_pre_scoring_service import CandidatePreScoringService
from services.prospecting_profile_service import resolve_prospecting_profile

SVC = CandidatePreScoringService()

# Landing Pages: sem site, mas com presença ativa (Instagram, telefone,
# boa reputação) — bom candidato. Sem NENHUMA presença — mau candidato.
COM_PRESENCA = {
    "name": "Padaria Bom Pão",
    "website": None,
    "instagram_url": "https://instagram.com/bompao",
    "phone": "+5511999990000",
    "rating": 4.6,
    "rating_count": 120,
    "category": "Padaria",
}
SEM_PRESENCA = {
    "name": "Auto Peças Zé",
    "website": None,
    "phone": None,
    "rating": None,
    "rating_count": None,
    "category": None,
}

PROFILE_LANDING = resolve_prospecting_profile({
    "enrichment_steps": ["technical_site", "cnpj_receita", "business_social"],
    "prescoring_config": {"profile": "web_presence", "enabled": True, "threshold": 45},
})


def _score(item, profile=PROFILE_LANDING):
    return SVC.score_candidate(item, profile)


def test_sem_site_com_presenca_supera_sem_nenhuma_presenca():
    """Sem site + Instagram + reputação > sem site + zero presença digital."""
    bom = _score(COM_PRESENCA)
    ruim = _score(SEM_PRESENCA)
    assert bom["discovery_score"] > ruim["discovery_score"]
    assert bom["eligible_for_enrichment"] is True
    assert ruim["eligible_for_enrichment"] is False


def test_score_deterministico():
    """Mesma entrada + mesma configuração → mesmo score (sem LLM)."""
    a = _score(dict(COM_PRESENCA))
    b = _score(dict(COM_PRESENCA))
    assert a["discovery_score"] == b["discovery_score"]
    assert [f["signal"] for f in a["score_factors"]] == [f["signal"] for f in b["score_factors"]]


def test_fatores_explicaveis_com_sinal_e_evidencia():
    """Cada impacto carrega sinal identificável e evidência textual."""
    result = _score(COM_PRESENCA)
    assert result["discovery_score"] > 0
    for factor in result["score_factors"]:
        assert factor["signal"]
        assert isinstance(factor["impact"], int)
        assert factor["evidence"]
    sinais = {f["signal"] for f in result["score_factors"]}
    assert "NO_OWN_WEBSITE" in sinais
    assert "HAS_INSTAGRAM" in sinais


def test_pesos_do_perfil_mudam_ranking_sem_mudar_codigo():
    """Mudar pesos da config altera o score sem tocar no serviço."""
    profile_custom = resolve_prospecting_profile({
        "enrichment_steps": ["technical_site"],
        "prescoring_config": {
            "profile": "web_presence",
            "enabled": True,
            "threshold": 45,
            "weights": {"NO_OWN_WEBSITE": 50, "HAS_INSTAGRAM": 0},
        },
    })
    base = _score(COM_PRESENCA)
    custom = _score(COM_PRESENCA, profile_custom)
    assert custom["discovery_score"] != base["discovery_score"]


def test_perfis_diferentes_mesmo_candidato_scores_diferentes():
    """Landing valoriza presença digital; indústria não (site irrelevante)."""
    industrial = resolve_prospecting_profile({
        "enrichment_steps": ["cnpj_receita", "business_social"],
        "prescoring_config": {"profile": "industrial", "enabled": True, "threshold": 25},
    })
    erp = resolve_prospecting_profile({
        "enrichment_steps": ["cnpj_receita", "business_social"],
        "prescoring_config": {"profile": "business_opportunity", "enabled": True, "threshold": 40},
    })
    scores = {
        "landing": _score(COM_PRESENCA)["discovery_score"],
        "industrial": _score(COM_PRESENCA, industrial)["discovery_score"],
        "erp": _score(COM_PRESENCA, erp)["discovery_score"],
    }
    assert len(set(scores.values())) >= 2


def test_faixa_0_a_100():
    assert 0 <= _score(COM_PRESENCA)["discovery_score"] <= 100
    assert 0 <= _score(SEM_PRESENCA)["discovery_score"] <= 100
    # Empresa ideal (site + tudo) não estoura 100.
    cheia = {**COM_PRESENCA, "website": "https://bompao.com.br", "rating": 5.0,
             "rating_count": 9999}
    assert _score(cheia)["discovery_score"] <= 100


def test_sinais_carregam_contrato_do_registry():
    """Sinais têm key/value/source/confidence/observed_at/evidence + FACT."""
    for signal in _score(COM_PRESENCA)["signals"]:
        assert signal["key"] and signal["value"] is not None
        assert signal["source"] == "google_places"
        assert 0 <= signal["confidence"] <= 1
        assert signal["observed_at"]
        assert signal["evidence"]
        # Fase discovery: tudo é fato observado, não inferência.
        assert signal["epistemic"] == "FACT"


def test_website_social_conta_como_sem_site():
    """Website normalizado (None) + Instagram → NO_OWN_WEBSITE, não HAS_OWN."""
    result = _score(COM_PRESENCA)
    sinais = {s["key"] for s in result["signals"]}
    assert "NO_OWN_WEBSITE" in sinais
    assert "HAS_OWN_WEBSITE" not in sinais
