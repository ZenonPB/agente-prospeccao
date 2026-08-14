"""Testes do TTL do enriquecimento (carimbos de tempo por fonte).

Cobrem as funções puras de `enrichment_ts`: leitura/gravação dos timestamps,
a regra `is_fresh` (dentro/fora do TTL, sem carimbo ou inválido) e o snapshot
de frescor por fonte usado pela API e pelo aviso de "dados antigos" da UI.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services.enrichment_ts import (
    TTL_HOURS,
    freshness_snapshot,
    get_stamp,
    is_fresh,
    read_stamps,
    stamp,
)


def _lead(stamps=None):
    return SimpleNamespace(enrichment_timestamps=stamps)


def test_ttl_valores_esperados():
    assert TTL_HOURS["linkedin"] == 30 * 24
    assert TTL_HOURS["site"] == 7 * 24
    assert TTL_HOURS["reviews"] == 24


def test_is_fresh_dentro_e_fora_do_ttl():
    now = datetime.now(timezone.utc)
    recente = (now - timedelta(hours=1)).isoformat()
    antigo = (now - timedelta(days=40)).isoformat()
    assert is_fresh(recente, "linkedin", now) is True
    assert is_fresh(antigo, "linkedin", now) is False
    assert is_fresh(antigo, "site", now) is False


def test_is_fresh_sem_carimbo_ou_invalido():
    assert is_fresh(None, "linkedin") is False
    assert is_fresh("", "linkedin") is False
    assert is_fresh("nao-e-data", "linkedin") is False


def test_stamp_e_read():
    lead = _lead()
    stamp(lead, "linkedin", when=datetime(2026, 1, 1, tzinfo=timezone.utc))
    stamp(lead, "site")
    stamps = read_stamps(lead)
    assert stamps["linkedin"] == "2026-01-01T00:00:00+00:00"
    assert "site" in stamps
    assert get_stamp(lead, "linkedin") == stamps["linkedin"]
    assert get_stamp(lead, "reviews") is None


def test_freshness_snapshot():
    now = datetime.now(timezone.utc)
    stamps = {
        "linkedin": (now - timedelta(days=5)).isoformat(),
        "site": (now - timedelta(days=10)).isoformat(),
    }
    snap = freshness_snapshot(stamps, now)
    assert snap["linkedin"] == "fresh"
    assert snap["site"] == "stale"
    assert snap["reviews"] is None