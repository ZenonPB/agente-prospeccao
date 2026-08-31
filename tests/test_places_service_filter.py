"""Testes do filtro de cidade/UF + locationRestriction + max_pages em search_places.

Cobre as 3 defesas em profundidade:
- A: filtro pós-busca por city/state (descarte silencioso)
- C: max_pages=3 (teto, antes 6)
- D: locationRestriction.circle no payload quando location_bias fornecido
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.places_service import GooglePlacesService


def _place(i: int, *, city="Araraquara", state="SP", category="Clínica de Fisioterapia") -> dict:
    return {
        "id": f"place-{i}",
        "displayName": {"text": f"Clínica {i}"},
        "websiteUri": f"https://clinica{i}.com.br",
        "nationalPhoneNumber": f"(16) 9{i:04d}-0000",
        "formattedAddress": f"Rua {i}, 10 - Centro, {city} - {state}, Brasil",
        "primaryTypeDisplayName": {"text": category},
        "rating": 4.5,
        "userRatingCount": 20,
        "googleMapsUri": f"https://maps.google.com/?cid={i}",
    }


def _fake_post_capture(places: list, captured: list, *, next_page_token: str | None = None):
    async def fake_post(url, headers=None, json=None):
        captured.append(json)
        resp = MagicMock()
        resp.json.return_value = {"places": places, "nextPageToken": next_page_token}
        return resp

    return fake_post


def _fake_post_single_page(places: list):
    """Sem nextPageToken — encerra o loop em 1 página."""

    async def fake_post(url, headers=None, json=None):
        resp = MagicMock()
        resp.json.return_value = {"places": places}
        return resp

    return fake_post


# --- A. Filtro pós-busca por city/UF ---


def test_search_places_descarta_resultado_fora_da_cidade():
    svc = GooglePlacesService(api_key="test")
    places = [_place(1, city="Araraquara", state="SP"), _place(2, city="São José", state="SC")]
    fake_client = MagicMock()
    fake_client.post = _fake_post_single_page(places)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(
            svc.search_places("clinicas", max_results=10, filter_city="Araraquara", filter_state="SP")
        )

    assert len(leads) == 1
    assert leads[0]["name"] == "Clínica 1"


def test_search_places_descarta_quando_cidade_vazia_no_resultado():
    svc = GooglePlacesService(api_key="test")
    place = _place(1, city="", state="")
    place["formattedAddress"] = None
    fake_client = MagicMock()
    fake_client.post = _fake_post_single_page([place])
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(
            svc.search_places("clinicas", max_results=10, filter_city="Araraquara", filter_state="SP")
        )

    assert leads == []


def test_search_places_sem_filtro_cidade_mantem_todos():
    svc = GooglePlacesService(api_key="test")
    places = [_place(1, city="Araraquara"), _place(2, city="São José")]
    fake_client = MagicMock()
    fake_client.post = _fake_post_single_page(places)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(svc.search_places("clinicas", max_results=10))

    assert len(leads) == 2


def test_search_places_compara_cidade_ignorando_acentos():
    svc = GooglePlacesService(api_key="test")
    # API retornou "Sao Jose" (sem acento) — deve casar com filtro "São José".
    places = [_place(1, city="Sao Jose", state="SP")]
    fake_client = MagicMock()
    fake_client.post = _fake_post_single_page(places)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(
            svc.search_places("clinicas", max_results=10, filter_city="São José", filter_state="SP")
        )

    assert len(leads) == 1


# --- C. max_pages reduzido ---


def test_search_places_max_pages_3():
    """Mesmo com nextPageToken sempre presente, o loop para em 3 páginas."""
    svc = GooglePlacesService(api_key="test")
    call_count = {"n": 0}

    async def fake_post(url, headers=None, json=None):
        call_count["n"] += 1
        resp = MagicMock()
        resp.json.return_value = {
            "places": [_place(call_count["n"] * 100 + i) for i in range(20)],
            "nextPageToken": f"tok-{call_count['n']}",
        }
        return resp

    fake_client = MagicMock()
    fake_client.post = fake_post
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(svc.search_places("clinicas", max_results=100))

    assert call_count["n"] == 3, "max_pages deve ser 3 (não 6)"
    assert len(leads) == 60


# --- D. locationRestriction.circle no payload ---


def test_search_places_envia_location_restriction_no_payload():
    svc = GooglePlacesService(api_key="test")
    captured: list = []
    fake_client = MagicMock()
    fake_client.post = _fake_post_capture([_place(1)], captured)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        asyncio.run(
            svc.search_places(
                "clinicas",
                max_results=10,
                location_bias={
                    "circle": {
                        "center": {"latitude": -21.7943, "longitude": -48.1756},
                        "radius": 25_000,
                    }
                },
            )
        )

    assert len(captured) == 1, f"Esperado 1 chamada, got {len(captured)} — helper deve usar next_page_token=None"
    assert "locationBias" in captured[0]
    assert captured[0]["locationBias"]["circle"]["center"]["latitude"] == -21.7943


def test_search_places_envia_included_type_quando_informado():
    svc = GooglePlacesService(api_key="test")
    captured: list = []
    fake_client = MagicMock()
    fake_client.post = _fake_post_capture([_place(1)], captured)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        asyncio.run(
            svc.search_places(
                "clinicas de fisioterapia", max_results=10, included_type="physiotherapist"
            )
        )

    assert len(captured) == 1
    assert captured[0].get("includedType") == "physiotherapist"


def test_search_places_sem_location_bias_ou_tipo_nao_adiciona_campos():
    svc = GooglePlacesService(api_key="test")
    captured: list = []
    fake_client = MagicMock()
    fake_client.post = _fake_post_capture([_place(1)], captured)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        asyncio.run(svc.search_places("clinicas", max_results=10))

    payload = captured[0]
    assert "locationRestriction" not in payload
    assert "includedType" not in payload


# --- Combinação A + C + D ---


def test_search_places_combinado_filtra_e_para_3_paginas():
    svc = GooglePlacesService(api_key="test")
    page_idx = {"n": 0}
    pages_data = [
        [_page_city := _place(1, city="Araraquara")],  # ok
        [_place(2, city="São José"), _page_city2 := _place(3, city="Araraquara")],  # 1 ok, 1 fora
        [_place(4, city="Lages"), _place(5, city="Araraquara")],  # 1 ok, 1 fora
        [_place(6, city="Guaíba")],  # todos fora
    ]
    captured: list = []

    async def fake_post(url, headers=None, json=None):
        captured.append(json)
        page_idx["n"] += 1
        resp = MagicMock()
        resp.json.return_value = {
            "places": pages_data[page_idx["n"] - 1],
            "nextPageToken": "x" if page_idx["n"] < 4 else None,
        }
        return resp

    fake_client = MagicMock()
    fake_client.post = fake_post
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(
            svc.search_places(
                "clinicas",
                max_results=10,
                filter_city="Araraquara",
                filter_state="SP",
                location_bias={
                    "circle": {"center": {"latitude": -21.79, "longitude": -48.18}, "radius": 25_000}
                },
                included_type="physiotherapist",
            )
        )

    # 3 de Araraquara + 0 fora (todos os "São José", "Lages", "Guaíba" descartados)
    assert {l["name"] for l in leads} == {"Clínica 1", "Clínica 3", "Clínica 5"}
    assert len(captured) == 3
    assert all("locationBias" in p for p in captured)
    assert all(p.get("includedType") == "physiotherapist" for p in captured)
