"""Testes do webhook outbound genérico.

Cobre as funções puras do `webhook_outbound_service` (payload/headers).
A entrega HTTP (`_post_webhook`) é testada indiretamente em smoke E2E.
"""
from src.services.webhook_outbound_service import (
    build_webhook_payload,
    build_webhook_headers,
)


def test_build_payload_inclui_evento_e_data():
    out = build_webhook_payload("lead.created", {"lead_id": "abc"})
    assert out["event"] == "lead.created"
    assert out["data"] == {"lead_id": "abc"}


def test_build_headers_com_segredo():
    h = build_webhook_headers("minha-chave-secreta", "conversion.created")
    assert h["Content-Type"] == "application/json"
    assert h["X-Webhook-Event"] == "conversion.created"
    assert h["X-Webhook-Secret"] == "minha-chave-secreta"


def test_build_headers_sem_segredo_omite_header():
    h = build_webhook_headers(None, "lead.status_changed")
    assert "X-Webhook-Secret" not in h
    assert h["X-Webhook-Event"] == "lead.status_changed"
    assert h["Content-Type"] == "application/json"
