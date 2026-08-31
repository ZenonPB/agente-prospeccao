"""Geocoding utilitário para o filtro de raio da Places API.

A nova `searchText` (Places API New) aceita `locationRestriction.circle` para
limitar a busca por raio geográfico. Sem isso, a API pode devolver empresas
de qualquer lugar do Brasil quando a query inclui apenas o nome da cidade.

Como não queremos adicionar custo de geocoding em cada coleta, mantemos um
**cache embutido das cidades brasileiras mais comuns** e caímos para a
Geocoding API clássica (barata) só se a cidade não estiver no cache.

Este módulo é puro: nenhum import de settings/db — o chamador injeta a chave.
"""
from __future__ import annotations

import logging
import unicodedata
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


def _normalize(text: Optional[str]) -> str:
    """Lowercase + remove acentos + colapsa separadores. 'São Paulo' → 'sao paulo'.

    Hífens e underscores viram espaço, para que 'sao-paulo' e 'sao paulo' batam.
    """
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFD", text)
    no_accents = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return " ".join(no_accents.lower().replace("-", " ").replace("_", " ").split())


# Cidades brasileiras com mais de ~150k habitantes + capitais + cidades-sede
# de EJ. Centro aproximado (lat, lng) — precisão suficiente para raio 25 km.
_KNOWN_CITIES: dict[str, Tuple[float, float]] = {
    "araraquara": (-21.7943, -48.1756),
    "sao carlos": (-22.0174, -47.8862),
    "ribeirao preto": (-21.1784, -47.8103),
    "campinas": (-22.9056, -47.0608),
    "sao paulo": (-23.5505, -46.6333),
    "rio de janeiro": (-22.9068, -43.1729),
    "belo horizonte": (-19.9167, -43.9345),
    "curitiba": (-25.4284, -49.2733),
    "florianopolis": (-27.5969, -48.5495),
    "porto alegre": (-30.0346, -51.2177),
    "salvador": (-12.9714, -38.5014),
    "fortaleza": (-3.7172, -38.5433),
    "brasilia": (-15.7975, -47.8919),
    "manaus": (-3.1190, -60.0217),
    "belem": (-1.4558, -48.5039),
    "goiania": (-16.6869, -49.2648),
    "recife": (-8.0476, -34.8770),
    "natal": (-5.7945, -35.2110),
    "teresina": (-5.0892, -42.8016),
    "sao luiz": (-2.5297, -44.3028),
    "sao luis": (-2.5297, -44.3028),
    "maceio": (-9.6498, -35.7089),
    "aracaju": (-10.9472, -37.0731),
    "cuiaba": (-15.5989, -56.0949),
    "campo grande": (-20.4486, -54.6295),
    "vitoria": (-20.3155, -40.3128),
    "joao pessoa": (-7.1195, -34.8450),
    "porto velho": (-8.7619, -63.9039),
    "rio branco": (-9.9747, -67.8243),
    "boa vista": (2.8235, -60.6758),
    "macapa": (0.0349, -51.0694),
    "palmas": (-10.1670, -48.3277),
    "lages": (-27.8150, -50.3259),
    "guaramirim": (-26.4731, -48.9981),
    "gaspar": (-26.9344, -48.9586),
    "sao jose": (-27.6136, -48.6366),
    "sao jose dos pinhais": (-25.5316, -49.2064),
    "serra": (-20.1210, -40.3070),
    "catalao": (-18.1656, -47.9442),
    "sao joao del rei": (-21.1314, -44.2526),
    "sao joao del-rei": (-21.1314, -44.2522),
}

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def resolve_city_coords(
    city: Optional[str],
    state: Optional[str] = None,
    *,
    api_key: Optional[str] = None,
) -> Optional[Tuple[float, float]]:
    """Resolve (lat, lng) do centro de uma cidade.

    Ordem:
    1. Cache embutido (chave = city normalizado; ignora UF).
    2. Geocoding API clássica (`api_key` obrigatório nesse caso).

    Retorna None se a cidade for vazia ou se a API falhar/recusar.
    """
    norm = _normalize(city)
    if not norm:
        return None
    if norm in _KNOWN_CITIES:
        return _KNOWN_CITIES[norm]

    if not api_key:
        logger.debug("Cidade '%s' fora do cache e sem GOOGLE_API_KEY — pulando geocoding.", city)
        return None

    try:
        address_parts = [city.strip(), state.strip() if state else "", "Brasil"]
        address = ", ".join(p for p in address_parts if p)
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                _GEOCODE_URL,
                params={"address": address, "key": api_key, "language": "pt-BR"},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "OK":
            logger.debug("Geocoding falhou para '%s': %s", address, data.get("status"))
            return None
        results = data.get("results") or []
        if not results:
            return None
        loc = results[0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("Erro no geocoding de '%s': %s", city, exc)
        return None


def build_location_circle(
    city: Optional[str],
    state: Optional[str] = None,
    *,
    radius_m: int = 25_000,
    api_key: Optional[str] = None,
) -> Optional[dict]:
    """Monta o `locationRestriction.circle` para o payload do `searchText`.

    Retorna None se a cidade não puder ser geocodificada (caller decide
    se segue sem filtro geográfico).
    """
    coords = resolve_city_coords(city, state, api_key=api_key)
    if not coords:
        return None
    lat, lng = coords
    return {
        "circle": {
            "center": {"latitude": lat, "longitude": lng},
            "radius": radius_m,
        }
    }


def city_matches(haystack_city: Optional[str], filter_city: Optional[str]) -> bool:
    """Compara o nome de cidade parseado do `formattedAddress` com o filtro.

    Accent-insensitive e case-insensitive. Retorna True se o filtro for vazio
    (sem filtro) ou se bater.
    """
    if not filter_city:
        return True
    if not haystack_city:
        return False
    return _normalize(haystack_city) == _normalize(filter_city)


def state_matches(haystack_state: Optional[str], filter_state: Optional[str]) -> bool:
    """Mesmo princípio de `city_matches`, mas para UF (string curta, sem acento)."""
    if not filter_state:
        return True
    if not haystack_state:
        return False
    return _normalize(haystack_state) == _normalize(filter_state)
