"""Contrato de normalização temporal das oportunidades de evento."""
from datetime import datetime, timezone


def test_parse_event_datetime_converte_iso_com_timezone():
    from services.prospecting.event_opportunity_service import parse_event_datetime

    parsed = parse_event_datetime("2030-06-15T12:30:00Z")

    assert parsed == datetime(2030, 6, 15, 12, 30, tzinfo=timezone.utc)


def test_parse_event_datetime_normaliza_datetime_sem_timezone():
    from services.prospecting.event_opportunity_service import parse_event_datetime

    parsed = parse_event_datetime(datetime(2030, 6, 15, 12, 30))

    assert parsed == datetime(2030, 6, 15, 12, 30, tzinfo=timezone.utc)


def test_parse_event_datetime_rejeita_valor_invalido():
    from services.prospecting.event_opportunity_service import parse_event_datetime

    assert parse_event_datetime("não é uma data") is None