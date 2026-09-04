"""Gate de promoção Candidate → Lead no lote de coleta (docs/melhorias/06/07)."""
from services.candidate_pre_scoring_service import CandidatePreScoringService
from services.prospecting_profile_service import resolve_prospecting_profile

SVC = CandidatePreScoringService()

ITEMS = [
    {"name": "Forte", "website": None, "instagram_url": "https://instagram.com/f",
     "phone": "119", "rating": 4.8, "rating_count": 200, "category": "Clínica"},
    {"name": "Médio", "website": None, "phone": "118", "rating": 4.0,
     "rating_count": 15, "category": "Oficina"},
    {"name": "Fraco", "website": None, "phone": None, "rating": None,
     "rating_count": None, "category": None},
]

PROFILE_ON = resolve_prospecting_profile({
    "enrichment_steps": ["technical_site"],
    "prescoring_config": {"profile": "web_presence", "enabled": True, "threshold": 45},
})
PROFILE_OFF = resolve_prospecting_profile({"enrichment_steps": ["technical_site"]})


def test_gate_desligado_promove_tudo_regressao():
    """Sem config, lote passa intacto — comportamento atual preservado."""
    selected, stats = SVC.select_candidates(ITEMS, PROFILE_OFF)
    assert selected == ITEMS
    assert stats["discarded"] == 0


def test_gate_descarta_apenas_abaixo_do_threshold():
    selected, stats = SVC.select_candidates(ITEMS, PROFILE_ON)
    nomes = [i["name"] for i in selected]
    assert "Forte" in nomes
    assert "Fraco" not in nomes
    assert stats["discarded"] >= 1
    assert stats["evaluated"] == len(ITEMS)


def test_selecionados_ordenados_por_score_com_anotacoes():
    selected, _ = SVC.select_candidates(ITEMS, PROFILE_ON)
    scores = [i["discovery_score"] for i in selected]
    assert scores == sorted(scores, reverse=True)
    for item in selected:
        assert item["prescoring_summary"]


def test_top_k_limita_promocao():
    profile = resolve_prospecting_profile({
        "enrichment_steps": ["technical_site"],
        "prescoring_config": {"profile": "web_presence", "enabled": True,
                              "threshold": 0, "top_k": 1},
    })
    selected, stats = SVC.select_candidates(ITEMS, profile)
    assert len(selected) == 1
    assert selected[0]["name"] == "Forte"
    assert stats["eligible"] == 1


def test_nenhum_item_no_lote_nao_explode():
    selected, stats = SVC.select_candidates([], PROFILE_ON)
    assert selected == []
    assert stats["evaluated"] == 0
