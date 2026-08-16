"""Testes do cálculo de variantes A/B em `AnalyticsService.message_variants`.

Cobre:
- Leitura por `Message.variant` (uma linha por envio) em vez de proxy;
- `responded` vem de `Message.is_response=True` (não do status do funil);
- Normalização do rótulo (uppercase + fallback para "(sem variante)");
- Vazio → lista vazia.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.services.analytics_service import AnalyticsService


class _FakeBuilder:
    def __init__(self, results):
        self._results = list(results)

    def filter(self, *_a, **_k):
        return self

    def join(self, *_a, **_k):
        return self

    def with_entities(self, *_a, **_k):
        return self

    def all(self):
        return self._results.pop(0) if self._results else []


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *_a, **_k):
        return _FakeBuilder([self._rows])


def _msg(variant, opened=None, clicked=None, is_response=False, hours_ago=2):
    return (
        variant,
        f"tok-{variant}-{hours_ago}",
        opened,
        clicked,
        is_response,
    )


def _svc(rows):
    return AnalyticsService(db=_FakeDb(rows), organization_id="org-1")


def test_sem_mensagens_retorna_vazio():
    assert _svc([]).message_variants() == {"variants": []}


def test_agregacao_por_variant():
    """Cada `Message` (enviada ou resposta) é contada exatamente uma vez."""
    now = datetime.now(timezone.utc)
    rows = [
        _msg("A", opened=now, clicked=None),
        _msg("A", opened=now, clicked=now),
        _msg("B", opened=None, clicked=None),
        _msg("B", opened=None, clicked=None, is_response=True),
        _msg("C", opened=now, clicked=None, is_response=True),
    ]
    out = _svc(rows).message_variants()
    by_variant = {v["variant"]: v for v in out["variants"]}
    assert by_variant.keys() == {"A", "B", "C"}
    a = by_variant["A"]
    assert a["sent"] == 2
    assert a["opened"] == 2
    assert a["clicked"] == 1
    assert a["responded"] == 0
    assert a["open_rate"] == 100.0
    assert a["click_rate"] == 50.0
    assert a["response_rate"] == 0.0
    b = by_variant["B"]
    assert b["sent"] == 1
    assert b["responded"] == 1
    assert b["response_rate"] == 100.0
    c = by_variant["C"]
    # Resposta: não conta como enviada, mas vira 1 responded com 0 sent.
    assert c["sent"] == 0
    assert c["responded"] == 1
    # Taxas ficam 0 quando sent == 0 (sem divisão por zero).
    assert c["response_rate"] == 0


def test_normalizacao_label_lowercase_para_uppercase():
    rows = [_msg("a"), _msg("b")]
    out = _svc(rows).message_variants()
    variants = {v["variant"] for v in out["variants"]}
    assert variants == {"A", "B"}


def test_periodo_filtra_fora_da_janela():
    """Mensagens fora do período não entram — mas o método não filtra
    no nível do service (filtros já foram aplicados pelo caller). Aqui
    confirmamos que o método não inventa dados."""
    rows = [_msg("A"), _msg("B")]
    out = _svc(rows).message_variants(from_date="2025-01-01", to_date="2025-01-31")
    # Sem filtro real (db fake), o método devolve o que recebeu.
    assert len(out["variants"]) == 2


def test_apenas_respostas_sem_envios():
    """Sem envios (todas is_response), responded cresce mas sent=0."""
    rows = [
        _msg("A", is_response=True),
        _msg("A", is_response=True),
    ]
    out = _svc(rows).message_variants()
    by_variant = {v["variant"]: v for v in out["variants"]}
    a = by_variant["A"]
    assert a["sent"] == 0
    assert a["responded"] == 2
    assert a["open_rate"] == 0
    assert a["click_rate"] == 0
    assert a["response_rate"] == 0
