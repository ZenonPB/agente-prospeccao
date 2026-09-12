"""Isolamento multi-tenant do inbound de e-mail.

Invariante sob teste: o inbound resolve **uma** organização antes de qualquer
consulta de domínio e confina leitura e escrita a essa organização.

Cenário central: duas organizações têm um lead com o **mesmo** endereço de
remetente. O inbound autenticado para a organização A só pode afetar o lead de
A; o lead de B não recebe `Message`, `LeadActivity`, `Notification` nem
alteração de `FollowUp`.

O harness não usa banco: a consulta em memória de `sqlalchemy_memory` avalia os
critérios SQLAlchemy reais montados pelo serviço contra linhas de teste. Isso
preserva a semântica do filtro (é o filtro do serviço que decide o resultado) e
mantém o teste determinístico e sem dependência de Postgres.

Ordem das linhas: o lead da organização B vem primeiro na lista, reproduzindo o
pior caso de uma consulta sem escopo de tenant que usa `.first()` — a ordem de
retorno depende do planner.
"""
import inspect
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy_memory import ConsultaMemoria as _Consulta

import src.routes.webhooks as webhooks_module
from src.db.dependencies import get_db
from src.db.models import (
    Contact,
    FollowUp,
    FollowUpStatus,
    Lead,
    LeadActivity,
    LeadStatus,
    Message,
    Notification,
    Organization,
)
from src.services import inbound_email_service

REMETENTE = "decisor@empresa-homonima.com.br"


# --------------------------------------------------------------------------
# Sessão em memória sobre a consulta compartilhada de `sqlalchemy_memory`
# --------------------------------------------------------------------------


class _Sessao:
    """Sessão fake: guarda o que foi adicionado e conta commit/rollback."""

    def __init__(self, leads=(), contatos=(), followups=(), mensagens=(), organizacoes=()):
        self.leads = list(leads)
        self.contatos = list(contatos)
        self.followups = list(followups)
        self.mensagens = list(mensagens)
        self.organizacoes = list(organizacoes)
        self.adicionados = []
        self.commits = 0
        self.rollbacks = 0

    # --- linhas por modelo ---

    def _linhas_lead(self):
        linhas = []
        for lead in self.leads:
            contatos = [c for c in self.contatos if str(c.lead_id) == str(lead.id)]
            if not contatos:
                linhas.append({"leads": lead, "contacts": None})
                continue
            for contato in contatos:
                linhas.append({"leads": lead, "contacts": contato})
        return linhas

    def query(self, *entidades):
        modelo = entidades[0]
        if modelo is Lead:
            return _Consulta("leads", self._linhas_lead())
        if modelo is Contact:
            return _Consulta("contacts", [{"contacts": c} for c in self.contatos])
        if modelo is FollowUp:
            return _Consulta("follow_ups", [{"follow_ups": f} for f in self.followups])
        if modelo is Message:
            return _Consulta("messages", [{"messages": m} for m in self.mensagens])
        if modelo is Organization:
            return _Consulta("organizations", [{"organizations": o} for o in self.organizacoes])
        return _Consulta(getattr(modelo, "__tablename__", "desconhecido"), [])

    # --- escrita ---

    def add(self, obj):
        self.adicionados.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


# --------------------------------------------------------------------------
# Fixtures de dados
# --------------------------------------------------------------------------

ORG_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
ORG_B = uuid.UUID("22222222-2222-4222-8222-222222222222")


def _lead(organization_id, email=REMETENTE, nome="Empresa Homônima"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id,
        email=email,
        company_name=nome,
        status=LeadStatus.CONTATADO,
        opt_out=False,
        last_contacted_at=None,
        assigned_to_id=uuid.uuid4(),
    )


def _mensagem_enviada(lead, minutos_atras=30, variante="A"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        lead_id=lead.id,
        sent_at=datetime.now(timezone.utc) - timedelta(minutes=minutos_atras),
        responded_at=None,
        is_response=False,
        variant=variante,
        tracking_token=f"tok-{lead.id}",
    )


def _followup_pendente(lead):
    return SimpleNamespace(
        id=uuid.uuid4(),
        lead_id=lead.id,
        status=FollowUpStatus.PENDING,
    )


def _sessao_duas_orgs():
    """Lead de B primeiro: pior caso de `.first()` em consulta sem tenant."""
    lead_a = _lead(ORG_A, nome="Empresa A")
    lead_b = _lead(ORG_B, nome="Empresa B")
    sessao = _Sessao(
        leads=[lead_b, lead_a],
        followups=[_followup_pendente(lead_b), _followup_pendente(lead_a)],
        mensagens=[_mensagem_enviada(lead_b, variante="B"), _mensagem_enviada(lead_a, variante="A")],
    )
    return sessao, lead_a, lead_b


def _processar(sessao, *, organization_id, from_email, subject="", body=""):
    """Chama o inbound com a assinatura tenant-aware exigida pelos requisitos.

    Enquanto `process_inbound_email` não aceitar `organization_id`, o fallback
    executa a assinatura legada para que a evidência de falha seja a asserção de
    isolamento — o vazamento real — e não apenas o `TypeError` da assinatura.
    """
    try:
        return inbound_email_service.process_inbound_email(
            sessao,
            organization_id=organization_id,
            from_email=from_email,
            subject=subject,
            body=body,
        )
    except TypeError as erro:
        if "organization_id" not in str(erro):
            raise
        return inbound_email_service.process_inbound_email(
            sessao, from_email=from_email, subject=subject, body=body,
        )


def _por_tipo(sessao, tipo):
    return [o for o in sessao.adicionados if isinstance(o, tipo)]


# --------------------------------------------------------------------------
# P1 — leitura confinada à organização resolvida (Requisitos 1.3, 1.4)
# --------------------------------------------------------------------------


def test_inbound_da_org_a_afeta_somente_o_lead_da_org_a():
    sessao, lead_a, lead_b = _sessao_duas_orgs()

    resultado = _processar(
        sessao,
        organization_id=ORG_A,
        from_email=REMETENTE,
        subject="Re: proposta",
        body="Podemos conversar amanhã?",
    )

    assert resultado["matched"] is True
    assert lead_a.status == LeadStatus.RESPONDIDO
    assert lead_a.last_contacted_at is not None
    # O lead da organização B não pode ser tocado pelo inbound de A.
    assert lead_b.status == LeadStatus.CONTATADO
    assert lead_b.last_contacted_at is None
    assert lead_b.opt_out is False


def test_process_inbound_email_exige_organization_id():
    """A organização é resolvida antes de qualquer consulta de domínio (1.1)."""
    assinatura = inspect.signature(inbound_email_service.process_inbound_email)
    parametro = assinatura.parameters.get("organization_id")

    assert parametro is not None, (
        "process_inbound_email precisa receber organization_id — sem ele a "
        "consulta de lead não tem escopo de tenant"
    )
    assert parametro.default is inspect.Parameter.empty, (
        "organization_id precisa ser obrigatório; um default deixa a chamada "
        "voltar ao comportamento global"
    )


# --------------------------------------------------------------------------
# P2 — escrita confinada ao lead da organização (Requisitos 2.1, 2.2, 2.4)
# --------------------------------------------------------------------------


def test_zero_message_criada_no_lead_da_outra_organizacao():
    sessao, lead_a, lead_b = _sessao_duas_orgs()

    _processar(
        sessao,
        organization_id=ORG_A,
        from_email=REMETENTE,
        subject="Re: proposta",
        body="Interessado.",
    )

    mensagens = _por_tipo(sessao, Message)
    assert mensagens, "a resposta deveria gerar a Message espelho do lead de A"
    assert [str(m.lead_id) for m in mensagens] == [str(lead_a.id)]
    assert not [m for m in mensagens if str(m.lead_id) == str(lead_b.id)]


def test_trilha_e_notificacao_ficam_no_lead_da_organizacao_resolvida():
    sessao, lead_a, lead_b = _sessao_duas_orgs()

    _processar(
        sessao,
        organization_id=ORG_A,
        from_email=REMETENTE,
        subject="Re: proposta",
        body="Interessado.",
    )

    atividades = _por_tipo(sessao, LeadActivity)
    assert atividades
    assert all(str(a.lead_id) == str(lead_a.id) for a in atividades)

    notificacoes = _por_tipo(sessao, Notification)
    assert all(str(n.lead_id) == str(lead_a.id) for n in notificacoes)
    assert all(str(n.organization_id) == str(ORG_A) for n in notificacoes)


def test_followup_pendente_da_outra_organizacao_permanece_intocado():
    sessao, lead_a, lead_b = _sessao_duas_orgs()

    _processar(
        sessao,
        organization_id=ORG_A,
        from_email=REMETENTE,
        subject="Re: proposta",
        body="Interessado.",
    )

    por_lead = {str(f.lead_id): f.status for f in sessao.followups}
    assert por_lead[str(lead_a.id)] == FollowUpStatus.CANCELLED
    assert por_lead[str(lead_b.id)] == FollowUpStatus.PENDING


def test_stop_da_org_a_nao_marca_opt_out_no_lead_da_org_b():
    sessao, lead_a, lead_b = _sessao_duas_orgs()

    resultado = _processar(
        sessao,
        organization_id=ORG_A,
        from_email=REMETENTE,
        subject="STOP",
        body="Pare de enviar e-mails.",
    )

    assert resultado["stop_requested"] is True
    assert lead_a.opt_out is True
    assert lead_b.opt_out is False


# --------------------------------------------------------------------------
# P3 — ausência de efeito sem correspondência na org (Requisito 1.5)
# --------------------------------------------------------------------------


def test_sem_lead_na_organizacao_resolvida_retorna_matched_false_sem_persistir():
    """O remetente existe apenas na organização B; o inbound é de A."""
    lead_b = _lead(ORG_B, nome="Empresa B")
    sessao = _Sessao(
        leads=[lead_b],
        followups=[_followup_pendente(lead_b)],
        mensagens=[_mensagem_enviada(lead_b, variante="B")],
    )

    resultado = _processar(
        sessao,
        organization_id=ORG_A,
        from_email=REMETENTE,
        subject="Re: proposta",
        body="Interessado.",
    )

    assert resultado == {"matched": False, "stop_requested": False}
    assert sessao.adicionados == []
    assert sessao.commits == 0
    assert lead_b.status == LeadStatus.CONTATADO
    assert lead_b.opt_out is False
    assert sessao.followups[0].status == FollowUpStatus.PENDING


def test_remetente_vazio_nao_persiste_nada():
    sessao, _lead_a, _lead_b = _sessao_duas_orgs()

    resultado = _processar(sessao, organization_id=ORG_A, from_email="   ")

    assert resultado == {"matched": False, "stop_requested": False}
    assert sessao.adicionados == []
    assert sessao.commits == 0


# --------------------------------------------------------------------------
# Contrato HTTP — 401 e zero persistência sem credencial de organização
# (Requisitos 1.1, 1.2)
# --------------------------------------------------------------------------

PAYLOAD_INBOUND = {
    "from_email": REMETENTE,
    "subject": "Re: proposta",
    "body": "Interessado.",
}


def _cliente(sessao, monkeypatch, segredo="segredo-teste"):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(webhooks_module.settings, "EMAIL_WEBHOOK_SECRET", segredo)
    app = FastAPI()
    app.include_router(webhooks_module.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: sessao
    return TestClient(app, raise_server_exceptions=False)


def test_rota_por_token_com_token_invalido_responde_401_sem_persistir(monkeypatch):
    sessao, lead_a, lead_b = _sessao_duas_orgs()
    cliente = _cliente(sessao, monkeypatch)

    resp = cliente.post(
        "/api/webhooks/email/inbound/token-que-nao-existe",
        json=PAYLOAD_INBOUND,
    )

    assert resp.status_code == 401
    assert sessao.adicionados == []
    assert sessao.commits == 0
    assert lead_a.status == LeadStatus.CONTATADO
    assert lead_b.status == LeadStatus.CONTATADO


def test_rota_legada_sem_identificacao_de_organizacao_responde_401(monkeypatch):
    """Segredo global correto não basta: sem organização resolvível é 401."""
    sessao, lead_a, lead_b = _sessao_duas_orgs()
    cliente = _cliente(sessao, monkeypatch)

    resp = cliente.post(
        "/api/webhooks/email/inbound",
        headers={"X-Webhook-Secret": "segredo-teste"},
        json=PAYLOAD_INBOUND,
    )

    assert resp.status_code == 401
    assert sessao.adicionados == []
    assert sessao.commits == 0
    assert lead_a.status == LeadStatus.CONTATADO
    assert lead_b.status == LeadStatus.CONTATADO


def test_rota_legada_sem_credencial_alguma_responde_401_sem_persistir(monkeypatch):
    """Credencial ausente é tão recusada quanto credencial inválida."""
    sessao, lead_a, lead_b = _sessao_duas_orgs()
    cliente = _cliente(sessao, monkeypatch)

    resp = cliente.post("/api/webhooks/email/inbound", json=PAYLOAD_INBOUND)

    assert resp.status_code == 401
    assert sessao.adicionados == []
    assert sessao.commits == 0
    assert lead_a.status == LeadStatus.CONTATADO
    assert lead_b.status == LeadStatus.CONTATADO


def test_rota_legada_com_segredo_invalido_responde_401_sem_persistir(monkeypatch):
    sessao, lead_a, lead_b = _sessao_duas_orgs()
    cliente = _cliente(sessao, monkeypatch)

    resp = cliente.post(
        "/api/webhooks/email/inbound",
        headers={
            "X-Webhook-Secret": "segredo-errado",
            "X-Organization-Id": str(ORG_A),
        },
        json=PAYLOAD_INBOUND,
    )

    assert resp.status_code == 401
    assert sessao.adicionados == []
    assert sessao.commits == 0
    assert lead_a.status == LeadStatus.CONTATADO
    assert lead_b.status == LeadStatus.CONTATADO
