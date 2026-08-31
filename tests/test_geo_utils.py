"""Testes do geo_utils — cache de cidades + geocoding + normalização."""
from unittest.mock import MagicMock, patch

import pytest

from services.geo_utils import (
    build_location_circle,
    city_matches,
    resolve_city_coords,
    state_matches,
)


def test_resolve_coords_cidade_conhecida_nao_chama_api():
    with patch("services.geo_utils.httpx.Client") as mock_client:
        coords = resolve_city_coords("Araraquara", "SP", api_key="any")
    assert coords == (-21.7943, -48.1756)
    mock_client.assert_not_called()


def test_resolve_coords_normaliza_acentos_e_caixa():
    assert resolve_city_coords("  SÃO CARLOS ", "sp") == (-22.0174, -47.8862)
    assert resolve_city_coords("sao-paulo", "SP") == (-23.5505, -46.6333)
    assert resolve_city_coords("São João Del Rei", "MG") == (-21.1314, -44.2526)


def test_resolve_coords_cidade_desconhecida_sem_api_key_retorna_none():
    assert resolve_city_coords("Cidade Inexistente", "XX", api_key=None) is None
    assert resolve_city_coords("Cidade Inexistente", "XX", api_key="") is None


def test_resolve_coords_cidade_desconhecida_com_api_key_chama_geocoding():
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "status": "OK",
        "results": [{"geometry": {"location": {"lat": -22.5, "lng": -47.1}}}],
    }
    fake_resp.raise_for_status = MagicMock()
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get = MagicMock(return_value=fake_resp)

    with patch("services.geo_utils.httpx.Client", return_value=fake_client):
        coords = resolve_city_coords("Cidade Nova", "SP", api_key="fake-key")

    assert coords == (-22.5, -47.1)
    called_params = fake_client.get.call_args.kwargs["params"]
    assert "Cidade Nova" in called_params["address"]
    assert "Brasil" in called_params["address"]
    assert called_params["key"] == "fake-key"


def test_resolve_coords_geocoding_status_nao_ok_retorna_none():
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"status": "ZERO_RESULTS", "results": []}
    fake_resp.raise_for_status = MagicMock()
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get = MagicMock(return_value=fake_resp)

    with patch("services.geo_utils.httpx.Client", return_value=fake_client):
        coords = resolve_city_coords("Cidade Sem Match", "ZZ", api_key="fake-key")

    assert coords is None


def test_resolve_coords_vazio_retorna_none():
    assert resolve_city_coords(None) is None
    assert resolve_city_coords("") is None
    assert resolve_city_coords("   ") is None


def test_build_location_circle_com_cidade_conhecida():
    circle = build_location_circle("Araraquara", "SP", radius_m=15_000)
    assert circle == {
        "circle": {
            "center": {"latitude": -21.7943, "longitude": -48.1756},
            "radius": 15_000,
        }
    }


def test_build_location_circle_sem_resolucao_retorna_none():
    assert build_location_circle("Cidade Inexistente", "XX") is None
    assert build_location_circle(None) is None


def test_city_matches_normaliza():
    assert city_matches("Araraquara", "araraquara") is True
    assert city_matches("São Carlos", "SAO CARLOS") is True
    assert city_matches("São Paulo", "sao paulo") is True
    assert city_matches("Campinas", "Araraquara") is False


def test_city_matches_filtro_vazio_sempre_true():
    assert city_matches("Qualquer", None) is True
    assert city_matches("Qualquer", "") is True
    assert city_matches(None, None) is True


def test_city_matches_haystack_vazio_com_filtro_retorna_false():
    assert city_matches(None, "Araraquara") is False
    assert city_matches("", "Araraquara") is False


def test_state_matches_normaliza():
    assert state_matches("SP", "sp") is True
    assert state_matches("MG", "Mg") is True
    assert state_matches("SP", "RJ") is False
