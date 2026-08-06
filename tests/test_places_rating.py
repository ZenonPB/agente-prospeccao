"""Testes do roadmap-vendas 4.6 — reputação do Google como sinal de scoring.

Cobrem a extração (places `_parse_lead`) e a montagem do fact de reputação no
`scoring_service.extract_business_facts`. Sem rede — funções puras.
"""
from services.places_service import GooglePlacesService
from services.scoring_service import extract_business_facts


def test_parse_lead_extrai_rating_e_avaliacoes():
    svc = GooglePlacesService(api_key="test")
    place = {
        "id": "ChIJ123",
        "displayName": {"text": "Doceria Doce Sabor"},
        "websiteUri": "https://doceria.com.br",
        "nationalPhoneNumber": "(16) 3333-0000",
        "formattedAddress": "Rua X, 10 - Centro, Araraquara - SP, Brasil",
        "primaryTypeDisplayName": {"text": "Doceria"},
        "rating": 3.2,
        "userRatingCount": 11,
        "googleMapsUri": "https://maps.google.com/?cid=abc",
    }
    out = svc._parse_lead(place)
    assert out["rating"] == 3.2
    assert out["rating_count"] == 11
    assert out["maps_uri"] == "https://maps.google.com/?cid=abc"
    assert out["name"] == "Doceria Doce Sabor"


def test_parse_lead_sem_rating_fica_none():
    svc = GooglePlacesService(api_key="test")
    out = svc._parse_lead({"id": "x", "displayName": {"text": "Sem Nota"}})
    assert out["rating"] is None
    assert out["rating_count"] is None
    assert out["maps_uri"] is None


def test_extract_business_facts_inclui_reputacao_google():
    facts = extract_business_facts(
        company_name="Doce Sabor",
        category="Doceria",
        city="Araraquara",
        state="SP",
        website=None,
        segment_hint="doceria",
        google_rating=3.2,
        google_rating_count=11,
    )
    joined = "\n".join(facts)
    assert "Reputação Google: 3.2★ com 11 avaliações" in joined


def test_extract_business_facts_sem_rating_nao_inventa():
    facts = extract_business_facts(
        company_name="X",
        category="",
        city="A",
        state="SP",
        website="https://x.com.br",
        segment_hint="",
    )
    assert all("Reputação Google" not in f for f in facts)
