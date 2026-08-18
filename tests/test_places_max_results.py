"""Teste do teto real de coleta (A1) — max_results não é estourado por página.

Sem rede: mocka `httpx.AsyncClient` para devolver UMA página com 20 resultados
e garante que `search_places(max_results=10)` retorna exatamente 10 (antes o
loop interno adicionava a página inteira).
"""
from unittest.mock import AsyncMock, MagicMock, patch

from services.places_service import GooglePlacesService


def _place(i: int) -> dict:
    return {
        "id": f"place-{i}",
        "displayName": {"text": f"Empresa {i}"},
        "websiteUri": f"https://empresa{i}.com.br",
        "nationalPhoneNumber": f"(16) 9{i:04d}-0000",
        "formattedAddress": f"Rua {i}, 10 - Centro, Araraquara - SP, Brasil",
        "primaryTypeDisplayName": {"text": "Academia"},
        "rating": 4.0,
        "userRatingCount": 10,
        "googleMapsUri": f"https://maps.google.com/?cid={i}",
    }


def _fake_post_response(places: list):
    async def fake_post(url, headers=None, json=None):
        resp = MagicMock()
        resp.json.return_value = {"places": places}
        return resp

    return fake_post


def test_search_places_respeita_max_results_dentro_da_pagina():
    svc = GooglePlacesService(api_key="test")
    fake_client = MagicMock()
    fake_client.post = _fake_post_response([_place(i) for i in range(20)])
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(svc.search_places("academias em Araraquara", max_results=10))

    assert len(leads) == 10, "max_results deve ser respeitado dentro da página"
    names = [l["name"] for l in leads]
    assert "Empresa 0" in names and "Empresa 9" in names
    assert "Empresa 10" not in names


def test_search_places_sem_exclusao_mantem_teto():
    svc = GooglePlacesService(api_key="test")
    fake_client = MagicMock()
    fake_client.post = _fake_post_response([_place(i) for i in range(20)])
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(svc.search_places("academias", max_results=5))

    assert len(leads) == 5


def test_search_places_nao_muta_exclude_place_ids():
    """Coleta incremental: o set de já-coletados NÃO pode crescer dentro da busca.

    Regressão do bug que zerava rodadas seguintes: `excluded = exclude_place_ids
    or set()` aliás o set do chamador quando não-vazio, e o `excluded.add(...)`
    interno contaminava o `existing_ids_set` da org — o `filter_new_batch_items`
    do pipeline via todos os resultados como "já coletados" (0 novos sempre,
    mesmo em campanha nova com a org tendo leads de outra campanha).
    """
    svc = GooglePlacesService(api_key="test")
    fake_client = MagicMock()
    fake_client.post = _fake_post_response([_place(i) for i in range(20)])
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    already_known = {"place-0", "place-1"}

    with patch("services.places_service.httpx.AsyncClient", return_value=fake_client):
        import asyncio

        leads = asyncio.run(
            svc.search_places("academias", max_results=5, exclude_place_ids=already_known)
        )

    assert len(leads) == 5
    assert {l["place_id_candidate"] for l in leads} == {"place-2", "place-3", "place-4", "place-5", "place-6"}
    assert already_known == {"place-0", "place-1"}, "chamador não pode ter seu set mutado"
