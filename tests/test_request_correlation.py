"""Contratos da correlação de requests HTTP (Task 1 — baseline observável).

Cobrem o middleware (`CorrelationIdMiddleware`) e a integração automática com
o logger estruturado (`observability.log_event`).
"""
import re
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.correlation import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    CorrelationIdMiddleware,
    get_request_id,
    reset_request_id,
    set_request_id,
)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/echo")
    def echo():
        # O id fica disponível no contexto durante o handler.
        return {"request_id": get_request_id()}

    @app.get("/erro")
    def erro():
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="erro tratado")

    return app


def test_gera_request_id_quando_ausente():
    client = TestClient(_app())
    resp = client.get("/echo")
    assert resp.status_code == 200
    header_id = resp.headers[REQUEST_ID_HEADER]
    assert _UUID_RE.match(header_id)
    # O id visto pelo handler é o mesmo devolvido no header.
    assert resp.json()["request_id"] == header_id


def test_reaproveita_request_id_recebido():
    client = TestClient(_app())
    fornecido = "req-abc-123"
    resp = client.get("/echo", headers={REQUEST_ID_HEADER: fornecido})
    assert resp.headers[REQUEST_ID_HEADER] == fornecido
    assert resp.json()["request_id"] == fornecido


def test_aceita_alias_x_correlation_id():
    client = TestClient(_app())
    resp = client.get("/echo", headers={CORRELATION_ID_HEADER: "corr-999"})
    assert resp.headers[REQUEST_ID_HEADER] == "corr-999"


def test_ids_diferentes_entre_requests():
    client = TestClient(_app())
    a = client.get("/echo").headers[REQUEST_ID_HEADER]
    b = client.get("/echo").headers[REQUEST_ID_HEADER]
    assert a != b


def test_id_gerado_quando_recebido_vazio_ou_longo():
    client = TestClient(_app())
    vazio = client.get("/echo", headers={REQUEST_ID_HEADER: "   "})
    assert _UUID_RE.match(vazio.headers[REQUEST_ID_HEADER])
    longo = client.get("/echo", headers={REQUEST_ID_HEADER: "x" * 500})
    assert _UUID_RE.match(longo.headers[REQUEST_ID_HEADER])


def test_header_presente_em_erro_tratado():
    # Respostas de erro tratadas (HTTPException) fluem de volta pelo middleware
    # e carregam o id de correlacao — util para rastrear falhas 4xx.
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/erro", headers={REQUEST_ID_HEADER: "erro-1"})
    assert resp.status_code == 400
    assert resp.headers[REQUEST_ID_HEADER] == "erro-1"


def test_contexto_nao_vaza_entre_requests():
    # Fora de qualquer request, o contexto é vazio.
    assert get_request_id() is None
    client = TestClient(_app())
    client.get("/echo")
    assert get_request_id() is None


def test_log_event_inclui_request_id_do_contexto(caplog):
    from src.services.observability import log_event

    token = set_request_id("corr-log-42")
    try:
        with caplog.at_level("INFO", logger="prospeccao.events"):
            log_event("cadence_sent", lead_id="lead-1")
    finally:
        reset_request_id(token)

    message = caplog.records[-1].message
    assert "request_id=corr-log-42" in message
    assert "event=cadence_sent" in message


def test_log_event_sem_contexto_nao_inclui_request_id(caplog):
    from src.services.observability import log_event

    with caplog.at_level("INFO", logger="prospeccao.events"):
        log_event("cadence_sent", lead_id="lead-1")

    assert "request_id=" not in caplog.records[-1].message


def test_log_event_respeita_request_id_explicito(caplog):
    from src.services.observability import log_event

    token = set_request_id("do-contexto")
    try:
        with caplog.at_level("INFO", logger="prospeccao.events"):
            log_event("cadence_sent", request_id="explicito")
    finally:
        reset_request_id(token)

    message = caplog.records[-1].message
    assert "request_id=explicito" in message
    assert "do-contexto" not in message
