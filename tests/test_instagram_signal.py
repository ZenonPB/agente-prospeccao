"""Testes do sinal de Instagram (4.26).

Cobre os helpers puros de detecção/extração e o comportamento da coleta
Places quando o website é Instagram.
"""
from urllib.parse import urlparse

from services.domain_utils import (
    extract_instagram_url,
    is_instagram_url,
)
from services.places_service import GooglePlacesService


def test_extract_instagram_url_de_url_completa():
    url = extract_instagram_url("Veja em https://www.instagram.com/HabitusAcademia/ nosso perfil")
    assert url == "https://instagram.com/HabitusAcademia"


def test_extract_instagram_url_sem_scheme():
    url = extract_instagram_url("instagram.com/academia.baldan")
    assert url == "https://instagram.com/academia.baldan"


def test_extract_instagram_url_handle_bare():
    url = extract_instagram_url("Siga nosso @habitus_academia para novidades")
    assert url == "https://instagram.com/habitus_academia"


def test_extract_instagram_url_none_quando_sem_handle():
    assert extract_instagram_url("Nada aqui") is None
    assert extract_instagram_url(None) is None


def test_is_instagram_url():
    assert is_instagram_url("https://instagram.com/foo") is True
    assert is_instagram_url("http://www.instagram.com/foo/") is True
    assert is_instagram_url("https://facebook.com/foo") is False
    assert is_instagram_url(None) is False
    assert is_instagram_url("") is False


def test_places_parse_lead_captura_instagram_url():
    svc = GooglePlacesService()
    place = {
        "displayName": {"text": "Habitus Academia"},
        "websiteUri": "https://instagram.com/habitusacademia",
        "primaryTypeDisplayName": {"text": "Academia"},
        "formattedAddress": "Rua X, 123, Matão - SP, Brasil",
        "id": "place-1",
    }
    out = svc._parse_lead(place)
    assert out["instagram_url"] == "https://instagram.com/habitusacademia"
    # website não vira "site próprio" (é social)
    assert out["website"] is None


def test_places_parse_lead_sem_instagram():
    svc = GooglePlacesService()
    place = {
        "displayName": {"text": "Habitus Academia"},
        "websiteUri": "https://www.habitus.com.br",
        "primaryTypeDisplayName": {"text": "Academia"},
        "formattedAddress": "Rua X, 123, Matão - SP, Brasil",
        "id": "place-2",
    }
    out = svc._parse_lead(place)
    assert out["instagram_url"] is None
    assert out["website"] == "https://www.habitus.com.br"
