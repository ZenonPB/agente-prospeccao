"""Smoke funcional do healthcheck da API (Task 1 — baseline reproduzível).

Não sobe o app inteiro (evita ligar os loops de background do lifespan): monta
a função real `health` num app mínimo com o middleware de correlação e
monkeypatcha a sessão de banco. Cobre o caminho OK (200) e o degradado (503),
além de garantir que o header de correlação acompanha a resposta.
"""
import importlib.util
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.correlation import REQUEST_ID_HEADER, CorrelationIdMiddleware

REPO_ROOT = Path(__file__).resolve().parents[1]
API_MAIN = REPO_ROOT / "services" / "api" / "main.py"


def _load_main():
    sys.path.insert(0, str(REPO_ROOT / "services" / "api"))
    spec = importlib.util.spec_from_file_location("api_main_health", str(API_MAIN))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client(monkeypatch, *, healthy: bool) -> TestClient:
    main = _load_main()

    class _FakeSession:
        def execute(self, *_a, **_k):
            if not healthy:
                raise RuntimeError("banco indisponível")
            return None

        def close(self):
            pass

    import src.db.session as session_module

    monkeypatch.setattr(session_module, "SessionLocal", lambda: _FakeSession())

    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    app.add_api_route("/health", main.health, methods=["GET"])
    return TestClient(app, raise_server_exceptions=False)


def test_health_ok_quando_banco_responde(monkeypatch):
    client = _client(monkeypatch, healthy=True)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}
    # Baseline observável: toda resposta carrega o id de correlação.
    assert REQUEST_ID_HEADER in resp.headers


def test_health_503_quando_banco_indisponivel(monkeypatch):
    client = _client(monkeypatch, healthy=False)
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "error"
    assert REQUEST_ID_HEADER in resp.headers
