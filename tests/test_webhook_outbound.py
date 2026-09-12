"""Testes do webhook outbound genérico e da política anti-SSRF."""
import pytest

from src.services.webhook_outbound_service import (
    _validate_webhook_url,
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


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/hook",
        "https://localhost/hook",
        "https://localhost.localdomain/hook",
        "https://127.0.0.1/hook",
        "https://10.0.0.4/hook",
        "https://172.16.0.5/hook",
        "https://192.168.1.7/hook",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/hook",
        "https://user:secret@example.com/hook",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ],
)
def test_webhook_rejeita_destinos_inseguros(url):
    ok, _reason = _validate_webhook_url(url)
    assert ok is False


def test_webhook_aceita_https_publico_sem_credenciais():
    ok, reason = _validate_webhook_url("https://hooks.example.com/v1/lead")
    assert ok is True
    assert reason == "ok"


def test_webhook_rejeita_dns_que_resolve_para_ip_privado():
    ok, reason = _validate_webhook_url(
        "https://hooks.example.com/v1/lead",
        resolved_ips=["93.184.216.34", "10.0.0.1"],
    )
    assert ok is False
    assert "não público" in reason


def test_webhook_aceita_dns_composto_apenas_por_ips_publicos():
    ok, reason = _validate_webhook_url(
        "https://hooks.example.com/v1/lead",
        resolved_ips=["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"],
    )
    assert ok is True
    assert reason == "ok"
