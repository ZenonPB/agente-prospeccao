"""Contrato determinístico do Filter DTO compartilhado de analytics."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.services.analytics_filters import (
    CommercialFilterDTO,
    get_commercial_filters,
    normalize_commercial_filters,
)


def _request(query: str) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/analytics/overview",
        "query_string": query.encode(),
        "headers": [],
    })


def test_dto_normaliza_snapshot_multivalorado_e_limites():
    dto = normalize_commercial_filters({
        "from": "2026-01-01",
        "to": "2026-01-31",
        "channel": ["email", "WHATSAPP,email"],
        "status": ["qualificado"],
        "score_bucket": ["60-79"],
        "outcome": ["won"],
        "attribution": "ATTRIBUTED",
        "search": "  AlphaMec  ",
        "limit": 1000,
    })

    assert dto.from_date == "2026-01-01"
    assert dto.channel == ["EMAIL", "WHATSAPP"]
    assert dto.status == ["QUALIFICADO"]
    assert dto.outcome == ["WON"]
    assert dto.attribution == "attributed"
    assert dto.search == "AlphaMec"
    assert dto.limit == 1000


@pytest.mark.parametrize(
    "payload",
    [
        {"status": ["NAO_EXISTE"]},
        {"channel": ["SMS"]},
        {"score_bucket": ["50-60"]},
        {"outcome": ["UNKNOWN_OUTCOME"]},
        {"attribution": "maybe"},
        {"search": "x" * 201},
        {"cursor": "x" * 2049},
        {"limit": 0},
        {"limit": 1001},
        {"from": "2026-02-01", "to": "2026-01-01"},
    ],
)
def test_dto_rejeita_valores_desconhecidos_e_limites(payload):
    with pytest.raises(ValueError):
        normalize_commercial_filters(payload)


def test_query_rejeita_campo_desconhecido_com_422():
    with pytest.raises(HTTPException) as exc:
        get_commercial_filters(_request("from=2026-01-01&typo=1"))
    assert exc.value.status_code == 422
    assert "typo" in str(exc.value.detail)


def test_query_preserva_parametros_atuais_sem_trata_los_como_filtro_novo():
    dto = get_commercial_filters(_request("from=2026-01-01&to=2026-01-31&k=10&sort_by=score"))
    assert dto.from_date == "2026-01-01"
    assert dto.to_date == "2026-01-31"


def test_dto_extra_forbid_no_normalizador():
    with pytest.raises(ValueError, match="filtros desconhecidos"):
        normalize_commercial_filters({"status": ["NOVO"], "not_allowed": "x"})


class _CapturedQuery:
    def __init__(self):
        self.criteria = []

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self


class _AnalyticsDB:
    def __init__(self):
        self.query_result = _CapturedQuery()

    def query(self, model):
        from src.db.models import Lead

        assert model is Lead
        return self.query_result


def test_parse_period_retorna_datetime_utc_e_fim_do_dia():
    from datetime import datetime, timezone

    from src.services.analytics_service import _parse_period

    assert _parse_period("2026-01-15") == datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert _parse_period("2026-01-31", end_of_day=True) == datetime(
        2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc,
    )
    assert _parse_period("data-invalida") is None


def test_leads_mantem_tenant_first_e_periodo_legado_com_dto_vazio():
    from src.db.models import Lead
    from src.services.analytics_service import AnalyticsService

    db = _AnalyticsDB()
    query = AnalyticsService(db, "org-a")._leads(
        from_date="2026-01-01",
        to_date="2026-01-31",
        filters=CommercialFilterDTO(),
    )

    assert query is db.query_result
    assert len(query.criteria) == 3
    assert str(query.criteria[0]) == "leads.organization_id = :organization_id_1"
    assert str(query.criteria[1]) == "leads.created_at >= :created_at_1"
    assert str(query.criteria[2]) == "leads.created_at <= :created_at_1"


def test_leads_nao_duplica_periodo_quando_dto_ja_o_carrega():
    from src.services.analytics_service import AnalyticsService

    db = _AnalyticsDB()
    query = AnalyticsService(db, "org-a")._leads(
        from_date="2026-01-01",
        to_date="2026-01-31",
        filters=CommercialFilterDTO.model_validate({
            "from": "2026-01-01",
            "to": "2026-01-31",
        }),
    )

    assert len(query.criteria) == 3
    assert [str(criteria) for criteria in query.criteria[1:]] == [
        "leads.created_at >= :created_at_1",
        "leads.created_at <= :created_at_1",
    ]
