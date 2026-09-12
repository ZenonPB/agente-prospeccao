"""Motivo obrigatório em `PERDIDO` nas rotas de lead.

Invariante sob teste: nenhuma rota exposta pela API consegue gravar
`Lead.status = PERDIDO` sem `Lead.lost_reason`, e a perda deixa trilha própria
(`LeadActivity` de ação `LOST` com o motivo) — distinta da trilha de
desqualificação, que não é perda comercial.

O harness não usa Postgres: reaproveita a consulta em memória de
`sqlalchemy_memory`, que avalia os critérios SQLAlchemy reais montados pela rota
contra linhas de teste, e guarda tudo o que foi adicionado à sessão — o que
permite asserir estado preservado, trilha gravada e ausência de commit. As rotas
são exercitadas de verdade por `TestClient`, então a validação de schema, a
resolução de dependências e a ordem entre validar e consultar o banco ficam sob
teste.
"""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy_memory import ConsultaMemoria

from src.auth.dependencies import (
    get_current_user,
    get_user_membership,
    get_user_organization,
)
from src.db.dependencies import get_db
from src.db.models import (
    Lead,
    LeadActivity,
    LeadActivityAction,
    LeadStatus,
    LostReason,
    OrganizationRole,
)
from src.middleware.rate_limit import limiter
from src.routes.leads import router as leads_router

ORG_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
USER_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")


# --------------------------------------------------------------------------
# Sessão em memória sobre a consulta compartilhada de `sqlalchemy_memory`
# --------------------------------------------------------------------------


class _Sessao:
    """Sessão fake: só povoa `Lead`; conta consultas, commits e rollbacks.

    As demais tabelas respondem vazio — é o que a organização sem `webhook_url`
    e o registro de outcome precisam para não interferir na transição.
    """

    def __init__(self, leads=()):
        self.leads = list(leads)
        self.consultas = []
        self.adicionados = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, *entidades):
        modelo = entidades[0]
        self.consultas.append(modelo)
        tabela = getattr(modelo, "__tablename__", "desconhecido")
        if modelo is Lead:
            return ConsultaMemoria("leads", [{"leads": l} for l in self.leads])
        return ConsultaMemoria(tabela, [])

    def add(self, obj):
        self.adicionados.append(obj)

    def flush(self):
        pass

    def refresh(self, _obj):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


# --------------------------------------------------------------------------
# Fixtures de dados e cliente
# --------------------------------------------------------------------------


def _lead(status=LeadStatus.PROPOSTA_ENVIADA, lost_reason=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        company_name="Metalúrgica Exemplo",
        status=status,
        lost_reason=lost_reason,
        assigned_to_id=None,
        updated_at=None,
    )


def _membro():
    return SimpleNamespace(
        id="m-1",
        role=OrganizationRole.OWNER,
        sales_role=None,
        user_id=USER_ID,
        organization_id=ORG_ID,
    )


def _cliente(sessao, monkeypatch) -> TestClient:
    # O limitador é global ao processo; desligado aqui para o teste não depender
    # de quota consumida por outros arquivos da suíte.
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(leads_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: sessao
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID)
    app.dependency_overrides[get_user_organization] = lambda: SimpleNamespace(id=ORG_ID)
    app.dependency_overrides[get_user_membership] = _membro
    return TestClient(app, raise_server_exceptions=False)


def _atividades(sessao, acao=None):
    atividades = [o for o in sessao.adicionados if isinstance(o, LeadActivity)]
    if acao is None:
        return atividades
    return [a for a in atividades if a.action == acao]


@pytest.fixture
def cenario(monkeypatch):
    lead = _lead()
    sessao = _Sessao(leads=[lead])
    return _cliente(sessao, monkeypatch), sessao, lead


# --------------------------------------------------------------------------
# P11 — rejeição preserva estado (Requisito 5.1)
# --------------------------------------------------------------------------


def test_patch_status_perdido_sem_motivo_responde_422(cenario):
    cliente, sessao, lead = cenario

    resp = cliente.patch(f"/api/leads/{lead.id}/status", json={"status": "PERDIDO"})

    assert resp.status_code == 422, (
        "PERDIDO sem lost_reason precisa ser rejeitado no schema — hoje o campo "
        "é opcional e a transição é aceita"
    )
    assert lead.status == LeadStatus.PROPOSTA_ENVIADA
    assert lead.lost_reason is None
    assert _atividades(sessao) == []
    assert sessao.commits == 0


def test_patch_status_perdido_sem_motivo_rejeita_antes_de_consultar_o_banco(cenario):
    cliente, sessao, lead = cenario

    cliente.patch(f"/api/leads/{lead.id}/status", json={"status": "PERDIDO"})

    assert sessao.consultas == [], (
        "a validação do motivo tem de acontecer antes de qualquer consulta de "
        "domínio"
    )


# --------------------------------------------------------------------------
# P10 — perda implica motivo, com trilha própria (Requisitos 5.2, 5.3)
# --------------------------------------------------------------------------


def test_patch_status_perdido_com_motivo_grava_trilha_lost_com_o_motivo(cenario):
    cliente, sessao, lead = cenario

    resp = cliente.patch(
        f"/api/leads/{lead.id}/status",
        json={"status": "PERDIDO", "lost_reason": "CONCORRENTE"},
    )

    assert resp.status_code == 200
    assert lead.status == LeadStatus.PERDIDO
    assert lead.lost_reason == LostReason.CONCORRENTE

    perdas = _atividades(sessao, LeadActivityAction.LOST)
    assert len(perdas) == 1
    assert "CONCORRENTE" in (perdas[0].detail or ""), (
        "a trilha LOST precisa registrar o motivo da perda"
    )
    assert perdas[0].status_to == LeadStatus.PERDIDO
    assert perdas[0].status_from == LeadStatus.PROPOSTA_ENVIADA
    assert sessao.commits == 1


def test_mark_lost_sem_motivo_responde_422_sem_alterar_o_lead(cenario):
    cliente, sessao, lead = cenario

    resp = cliente.post(f"/api/leads/{lead.id}/mark-lost", json={})

    assert resp.status_code == 422
    assert lead.status == LeadStatus.PROPOSTA_ENVIADA
    assert lead.lost_reason is None
    assert _atividades(sessao) == []
    assert sessao.commits == 0


def test_mark_lost_com_motivo_grava_trilha_lost_com_o_motivo(cenario):
    cliente, sessao, lead = cenario

    resp = cliente.post(
        f"/api/leads/{lead.id}/mark-lost", json={"lost_reason": "PRECO"},
    )

    assert resp.status_code == 200
    assert lead.status == LeadStatus.PERDIDO
    assert lead.lost_reason == LostReason.PRECO

    perdas = _atividades(sessao, LeadActivityAction.LOST)
    assert len(perdas) == 1
    assert "PRECO" in (perdas[0].detail or "")


# --------------------------------------------------------------------------
# P13 — perda e desqualificação não colapsam (Requisito 5.4)
# --------------------------------------------------------------------------


def test_patch_status_desqualificado_grava_trilha_distinta_da_perda(cenario):
    cliente, sessao, lead = cenario

    resp = cliente.patch(
        f"/api/leads/{lead.id}/status", json={"status": "DESQUALIFICADO"},
    )

    assert resp.status_code == 200
    assert lead.status == LeadStatus.DESQUALIFICADO
    assert _atividades(sessao, LeadActivityAction.LOST) == [], (
        "desqualificação não é perda comercial e não pode gravar trilha LOST"
    )
    mudancas = _atividades(sessao, LeadActivityAction.STATUS_CHANGED)
    assert len(mudancas) == 1
    assert mudancas[0].status_to == LeadStatus.DESQUALIFICADO


def test_patch_status_desqualificado_nao_grava_lost_reason(cenario):
    cliente, sessao, lead = cenario

    cliente.patch(
        f"/api/leads/{lead.id}/status",
        json={"status": "DESQUALIFICADO", "lost_reason": "OUTRO"},
    )

    assert lead.status == LeadStatus.DESQUALIFICADO
    assert lead.lost_reason is None, (
        "lost_reason é dado de perda; gravá-lo em DESQUALIFICADO colapsa os dois "
        "outcomes"
    )


def test_mark_disqualified_nao_grava_trilha_de_perda(cenario):
    cliente, sessao, lead = cenario

    resp = cliente.post(
        f"/api/leads/{lead.id}/mark-disqualified", json={"reason": "Fora do perfil"},
    )

    assert resp.status_code == 200
    assert lead.status == LeadStatus.DESQUALIFICADO
    assert lead.lost_reason is None
    assert _atividades(sessao, LeadActivityAction.LOST) == []
    mudancas = _atividades(sessao, LeadActivityAction.STATUS_CHANGED)
    assert len(mudancas) == 1
    assert "Fora do perfil" in (mudancas[0].detail or "")
