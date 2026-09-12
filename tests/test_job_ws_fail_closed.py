"""Falha fechada na autorização do WebSocket de job.

O endpoint `/api/pipeline/ws/{job_id}` só pode aceitar a conexão quando o job
tem `organization_id` preenchido e igual à organização ativa do usuário. Três
cenários precisam terminar em recusa idêntica, sem revelar se o job existe:

- job com `organization_id` nulo (job órfão);
- job de outra organização;
- job inexistente.

Os testes exercitam a corrotina real do endpoint com um stub de WebSocket e uma
sessão de banco falsa — sem Postgres, sem rede.

**Validates: Requirements 3.6, 21.1**
"""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from src.db.models import Job, User
from src.routes import pipeline

# Recusa esperada nos três cenários: mesmo código e mesma razão.
RECUSA_ESPERADA = (403, "Acesso negado a este job")

ORG_ATIVA = "11111111-1111-1111-1111-111111111111"
ORG_ALHEIA = "22222222-2222-2222-2222-222222222222"
JOB_ID = "job-fail-closed"


class _WebSocketStub:
    """Stub assíncrono de WebSocket que registra as chamadas do endpoint."""

    def __init__(self, auth_message: str, on_idle=None):
        self._pending = [auth_message]
        self.accepted = False
        self.closed: tuple[int, str | None] | None = None
        self.sent: list[dict] = []
        self._on_idle = on_idle

    async def accept(self):
        self.accepted = True

    async def receive_text(self) -> str:
        if self._pending:
            return self._pending.pop(0)
        # Sem mais mensagens: o client "desconecta". Antes de sair, deixa o
        # observador inspecionar o estado do endpoint.
        if self._on_idle is not None:
            self._on_idle()
        raise WebSocketDisconnect(code=1000)

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str | None = None):
        self.closed = (code, reason)


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeSession:
    """Sessão mínima: resolve `User` e `Job` por classe consultada."""

    def __init__(self, user, job):
        self._user = user
        self._job = job

    def query(self, model, *rest):
        if model is User:
            return _FakeQuery(self._user)
        if model is Job:
            return _FakeQuery(self._job)
        return _FakeQuery(None)

    def close(self):
        return None


@pytest.fixture(autouse=True)
def _conexoes_limpas():
    pipeline.active_connections.clear()
    yield
    pipeline.active_connections.clear()


def _conectar(monkeypatch, job) -> _WebSocketStub:
    """Executa o endpoint WS com o job informado e devolve o stub do socket."""
    user = SimpleNamespace(id="user-1")
    org = SimpleNamespace(id=ORG_ATIVA)
    session = _FakeSession(user, job)

    monkeypatch.setattr(pipeline, "get_db", lambda: iter([session]))
    monkeypatch.setattr(pipeline, "decode_access_token", lambda _t: {"sub": user.id})
    monkeypatch.setattr(pipeline, "user_organization", lambda _db, _user: org)

    registros: list[bool] = []
    ws = _WebSocketStub(
        json.dumps({"type": "auth", "token": "token-valido"}),
        # Momento em que o endpoint já registrou (ou não) a conexão no canal de
        # broadcast de progresso — antes do finally que limpa o registro.
        on_idle=lambda: registros.append(JOB_ID in pipeline.active_connections),
    )

    asyncio.run(pipeline.websocket_pipeline(ws, JOB_ID))

    ws.registrado_no_broadcast = any(registros)
    return ws


def _job(organization_id):
    return SimpleNamespace(id=JOB_ID, organization_id=organization_id)


def test_job_orfao_e_recusado_com_403():
    """Job com `organization_id` nulo nunca é autorizado.

    **Validates: Requirements 3.6** (Property 4)
    """
    with pytest.MonkeyPatch.context() as mp:
        ws = _conectar(mp, _job(None))

    assert ws.closed == RECUSA_ESPERADA
    assert ws.sent == []
    assert ws.registrado_no_broadcast is False


def test_job_de_outra_organizacao_e_recusado_com_403():
    """Job de outro tenant nunca é autorizado.

    **Validates: Requirements 3.6** (Property 4)
    """
    with pytest.MonkeyPatch.context() as mp:
        ws = _conectar(mp, _job(ORG_ALHEIA))

    assert ws.closed == RECUSA_ESPERADA
    assert ws.sent == []
    assert ws.registrado_no_broadcast is False


def test_job_inexistente_e_recusado_com_403():
    """Job ausente é recusado com o mesmo 403.

    **Validates: Requirements 3.6** (Property 4)
    """
    with pytest.MonkeyPatch.context() as mp:
        ws = _conectar(mp, None)

    assert ws.closed == RECUSA_ESPERADA
    assert ws.sent == []
    assert ws.registrado_no_broadcast is False


def test_recusa_de_inexistente_e_de_outra_organizacao_sao_indistinguiveis():
    """A recusa não revela a existência do job.

    **Validates: Requirements 3.6** (Property 5)
    """
    with pytest.MonkeyPatch.context() as mp:
        inexistente = _conectar(mp, None)
    with pytest.MonkeyPatch.context() as mp:
        alheio = _conectar(mp, _job(ORG_ALHEIA))

    assert inexistente.closed == alheio.closed
    assert inexistente.closed == RECUSA_ESPERADA


def test_nenhum_cenario_recusado_emite_mensagem_de_progresso():
    """Recusa produz zero mensagens no socket.

    **Validates: Requirements 3.6, 21.1** (Property 4)
    """
    for job in (_job(None), _job(ORG_ALHEIA), None):
        with pytest.MonkeyPatch.context() as mp:
            ws = _conectar(mp, job)
        assert ws.sent == []
        assert ws.registrado_no_broadcast is False
