"""Estados terminais fora da cadência.

Invariante sob teste: lead em `PERDIDO` ou `DESQUALIFICADO` não recebe outreach
por nenhum caminho da cadência — nem pelo envio de etapa (`send_step`), nem pela
seleção automática de vencidos (`run_due`) — e a transição para estado terminal
não deixa etapa pendente para trás.

Três pontos cobertos:

- `send_step` para lead terminal: zero chamada de SMTP, zero `Message`, etapa
  `SKIPPED` com o motivo do bloqueio registrado;
- `run_due` com população mista: o conjunto selecionado é disjunto dos
  follow-ups de leads terminais;
- transição terminal: nenhuma etapa fica `PENDING` depois dela.

O harness reaproveita a consulta em memória de `sqlalchemy_memory`: os critérios
SQLAlchemy montados pelo próprio serviço são avaliados contra linhas de teste,
então é o filtro de produção que decide o resultado. Sem Postgres, sem SMTP e
sem rede — o envio de e-mail é stubado e conta as chamadas.
"""
import inspect
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy_memory import ConsultaMemoria

import src.services.cadence_service as cadence_service
import src.services.email_service as email_service
from src.db.models import (
    FollowUpStatus,
    FollowUpStep,
    LeadActivity,
    LeadActivityAction,
    LeadStatus,
    Message,
)
from src.services.email_service import EmailSendResult

ORG = uuid.UUID("33333333-3333-4333-8333-333333333333")

ESTADOS_TERMINAIS = [LeadStatus.PERDIDO, LeadStatus.DESQUALIFICADO]


# --------------------------------------------------------------------------
# Sessão em memória sobre a consulta compartilhada de `sqlalchemy_memory`
# --------------------------------------------------------------------------


def _tabela_e_coluna(entidade):
    """Descobre a tabela consultada e, para `query(Model.coluna)`, a coluna."""
    if inspect.isclass(entidade):
        return getattr(entidade, "__tablename__", None), None
    tabela = getattr(entidade, "table", None)
    coluna = getattr(entidade, "key", None)
    if tabela is not None and coluna:
        return tabela.name, coluna
    return None, None


class _ConsultaFollowUp(ConsultaMemoria):
    """Consulta de follow-ups que registra a seleção devolvida.

    A seleção é o dado central da propriedade de disjunção: precisamos saber
    quais follow-ups o filtro de `run_due` escolheu, não apenas quais chegaram
    ao envio.
    """

    def __init__(self, linhas, registro, colunas=None):
        super().__init__("follow_ups", linhas, colunas=colunas)
        self._registro = registro

    def all(self):
        resultado = super().all()
        if self._colunas is None:
            self._registro.append(list(resultado))
        return resultado


class _Contagem:
    """Substitui `query(func.count(...))`: nenhum envio contabilizado hoje."""

    def join(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def scalar(self):
        return 0


class _Sessao:
    """Sessão fake: roteia consultas por tabela e guarda o que foi escrito."""

    def __init__(self, leads=(), organizacoes=(), followups=(), supressoes=()):
        self.leads = list(leads)
        self.organizacoes = list(organizacoes)
        self.followups = list(followups)
        self.supressoes = list(supressoes)
        self.adicionados = []
        self.commits = 0
        self.rollbacks = 0
        self.selecoes_followup = []

    # --- linhas por modelo ---

    def _linhas_followup(self):
        leads = {str(l.id): l for l in self.leads}
        orgs = {str(o.id): o for o in self.organizacoes}
        linhas = []
        for fu in self.followups:
            lead = leads.get(str(fu.lead_id))
            org = orgs.get(str(lead.organization_id)) if lead else None
            linhas.append({"follow_ups": fu, "leads": lead, "organizations": org})
        return linhas

    def query(self, *entidades):
        tabela, coluna = _tabela_e_coluna(entidades[0])
        colunas = [coluna] if coluna else None
        if tabela == "follow_ups":
            return _ConsultaFollowUp(
                self._linhas_followup(), self.selecoes_followup, colunas=colunas,
            )
        if tabela == "leads":
            return ConsultaMemoria("leads", [{"leads": l} for l in self.leads], colunas=colunas)
        if tabela == "organizations":
            return ConsultaMemoria(
                "organizations",
                [{"organizations": o} for o in self.organizacoes],
                colunas=colunas,
            )
        if tabela == "email_suppressions":
            return ConsultaMemoria(
                "email_suppressions",
                [{"email_suppressions": s} for s in self.supressoes],
                colunas=colunas,
            )
        if tabela is None:
            return _Contagem()
        return ConsultaMemoria(tabela, [], colunas=colunas)

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


def _organizacao():
    """Org com janela aberta e teto alto: nada é postergado por throttling."""
    return SimpleNamespace(
        id=ORG,
        auto_send_email=True,
        daily_email_limit=1000,
        send_window_start="00:00",
        send_window_end="24:00",
        email_from=None,
    )


def _lead(status, email="decisor@empresa.com.br"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=ORG,
        email=email,
        company_name="Empresa Teste",
        status=status,
        opt_out=False,
        assigned_to_id=None,
        contacts=[],
    )


def _followup(lead, step=FollowUpStep.OPENING, status=FollowUpStatus.PENDING, atrasado_dias=1):
    fu = SimpleNamespace(
        id=uuid.uuid4(),
        lead_id=lead.id,
        lead=lead,
        step=step,
        channel=None,
        subject="Proposta de manutenção preditiva",
        content="Olá, temos uma proposta para a sua operação.",
        status=status,
        scheduled_at=datetime.now(timezone.utc) - timedelta(days=atrasado_dias),
        sent_at=None,
        recipient=None,
        message_id=None,
        tracking_token=None,
        variant=None,
        attempts=0,
    )
    return fu


@pytest.fixture
def envios(monkeypatch):
    """Stub de SMTP: registra cada chamada e nunca toca a rede."""
    chamadas = []

    def _stub(to_email, subject, body, **kwargs):
        chamadas.append({"to_email": to_email, "subject": subject, "body": body})
        return EmailSendResult(sent=True, message_id=f"<stub-{uuid.uuid4().hex}@teste>")

    monkeypatch.setattr(email_service, "send_email", _stub)
    return chamadas


@pytest.fixture
def eventos(monkeypatch):
    """Captura os eventos de observabilidade emitidos pela cadência."""
    registrados = []

    def _stub(event, **campos):
        registrados.append({"event": event, **campos})

    monkeypatch.setattr(cadence_service, "log_event", _stub)
    return registrados


def _por_tipo(sessao, tipo):
    return [o for o in sessao.adicionados if isinstance(o, tipo)]


# --------------------------------------------------------------------------
# P7 — estado terminal absorve a cadência (Requisitos 4.1, 4.4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status", ESTADOS_TERMINAIS, ids=lambda s: s.value)
@pytest.mark.parametrize("user_id", [None, "11111111-1111-4111-8111-111111111111"],
                         ids=["scheduler", "consultor"])
def test_send_step_em_lead_terminal_nao_envia_email(status, user_id, envios, eventos):
    lead = _lead(status)
    fu = _followup(lead)
    sessao = _Sessao(leads=[lead], organizacoes=[_organizacao()], followups=[fu])

    enviado = cadence_service.send_step(sessao, fu, user_id=user_id)

    assert envios == [], (
        f"lead {status.value} recebeu e-mail: a cadência precisa parar antes do SMTP"
    )
    assert enviado is False
    assert fu.sent_at is None
    assert fu.message_id is None


@pytest.mark.parametrize("status", ESTADOS_TERMINAIS, ids=lambda s: s.value)
def test_send_step_em_lead_terminal_nao_cria_message(status, envios, eventos):
    lead = _lead(status)
    fu = _followup(lead)
    sessao = _Sessao(leads=[lead], organizacoes=[_organizacao()], followups=[fu])

    cadence_service.send_step(sessao, fu)

    assert _por_tipo(sessao, Message) == [], (
        f"lead {status.value} ganhou Message de outreach"
    )
    contatos = [
        a for a in _por_tipo(sessao, LeadActivity)
        if a.action == LeadActivityAction.CONTACTED
    ]
    assert contatos == [], "trilha registrou contato em lead terminal"


@pytest.mark.parametrize("status", ESTADOS_TERMINAIS, ids=lambda s: s.value)
def test_send_step_em_lead_terminal_marca_skipped_com_motivo(status, envios, eventos):
    lead = _lead(status)
    fu = _followup(lead)
    sessao = _Sessao(leads=[lead], organizacoes=[_organizacao()], followups=[fu])

    cadence_service.send_step(sessao, fu)

    assert fu.status == FollowUpStatus.SKIPPED, (
        "etapa bloqueada por estado terminal precisa ficar SKIPPED"
    )
    pulados = [e for e in eventos if e["event"] == "cadence_skipped"]
    assert pulados, "o bloqueio por estado terminal não foi registrado"
    motivos = [str(e.get("reason") or "") for e in pulados]
    assert any("terminal" in m for m in motivos), (
        f"motivo do bloqueio não identifica o estado terminal: {motivos}"
    )


@pytest.mark.parametrize("status", ESTADOS_TERMINAIS, ids=lambda s: s.value)
def test_send_step_em_lead_terminal_preserva_o_status_do_lead(status, envios, eventos):
    """Bloqueio não reabre o funil: o lead continua no estado terminal."""
    lead = _lead(status)
    fu = _followup(lead)
    sessao = _Sessao(leads=[lead], organizacoes=[_organizacao()], followups=[fu])

    cadence_service.send_step(sessao, fu)

    assert lead.status == status


# --------------------------------------------------------------------------
# P8 — seleção de vencidos exclui terminais (Requisito 4.2)
# --------------------------------------------------------------------------


@pytest.fixture
def populacao_mista():
    """Cinco leads vencidos na mesma org: dois terminais, três elegíveis.

    Cada lead tem endereço próprio, o que permite verificar o destino real de
    cada envio. Os terminais vêm primeiro na lista: pior caso de uma seleção que
    devolve o que o planner entregar antes.
    """
    org = _organizacao()
    terminais = [
        _lead(LeadStatus.PERDIDO, email="perdido@empresa.com.br"),
        _lead(LeadStatus.DESQUALIFICADO, email="desqualificado@empresa.com.br"),
    ]
    elegiveis = [
        _lead(LeadStatus.CONTATADO, email="contatado@empresa.com.br"),
        _lead(LeadStatus.QUALIFICADO, email="qualificado@empresa.com.br"),
        _lead(LeadStatus.RESPONDIDO, email="respondido@empresa.com.br"),
    ]
    leads = terminais + elegiveis
    followups = [_followup(lead) for lead in leads]
    sessao = _Sessao(leads=leads, organizacoes=[org], followups=followups)
    return SimpleNamespace(
        sessao=sessao,
        followups=followups,
        terminais=terminais,
        elegiveis=elegiveis,
        terminais_ids={str(fu.id) for fu in followups if fu.lead in terminais},
    )


@pytest.fixture
def etapas_enviadas(monkeypatch):
    """Substitui o envio de etapa dentro de `run_due` por um registrador."""
    registradas = []

    def _stub(db, follow_up, user_id=None):
        registradas.append(follow_up)
        follow_up.status = FollowUpStatus.SENT
        return True

    monkeypatch.setattr(cadence_service, "send_step", _stub)
    return registradas


def test_run_due_seleciona_conjunto_disjunto_dos_leads_terminais(
    populacao_mista, etapas_enviadas, envios,
):
    dados = populacao_mista

    enviadas, postergadas = cadence_service.run_due(dados.sessao)

    assert dados.sessao.selecoes_followup, "run_due não executou a seleção de vencidos"
    selecionados = {str(fu.id) for fu in dados.sessao.selecoes_followup[0]}
    assert selecionados & dados.terminais_ids == set(), (
        "run_due selecionou follow-up de lead em estado terminal"
    )
    # Sem postergação, a disjunção acima não pode ser efeito de throttling.
    assert postergadas == 0
    assert enviadas == len(dados.elegiveis)


def test_run_due_nao_chama_o_envio_para_etapa_de_lead_terminal(
    populacao_mista, etapas_enviadas,
):
    dados = populacao_mista

    cadence_service.run_due(dados.sessao)

    enviados_ids = {str(fu.id) for fu in etapas_enviadas}
    assert enviados_ids & dados.terminais_ids == set()
    assert len(enviados_ids) == len(dados.elegiveis)


def test_run_due_nao_manda_email_para_lead_terminal(populacao_mista, envios, eventos):
    """Caminho completo, só o SMTP stubado: nenhum endereço terminal recebe."""
    dados = populacao_mista

    cadence_service.run_due(dados.sessao)

    destinatarios = {e["to_email"] for e in envios}
    terminais_emails = {lead.email for lead in dados.terminais}
    assert destinatarios & terminais_emails == set(), (
        "run_due enviou e-mail para lead em estado terminal"
    )
    assert destinatarios == {lead.email for lead in dados.elegiveis}

    ids_terminais = {str(lead.id) for lead in dados.terminais}
    mensagens = [
        m for m in _por_tipo(dados.sessao, Message) if str(m.lead_id) in ids_terminais
    ]
    assert mensagens == [], "Message de outreach criada para lead terminal"


def test_run_due_nao_altera_etapa_de_lead_terminal(
    populacao_mista, etapas_enviadas, envios,
):
    dados = populacao_mista

    cadence_service.run_due(dados.sessao)

    terminais = [fu for fu in dados.followups if str(fu.id) in dados.terminais_ids]
    assert all(fu.status == FollowUpStatus.PENDING for fu in terminais)
    assert all(fu.sent_at is None for fu in terminais)


# --------------------------------------------------------------------------
# P9 — sem pendências após a transição terminal (Requisito 4.3)
# --------------------------------------------------------------------------


def _cancelamento_terminal():
    funcao = getattr(cadence_service, "cancel_pending_for_terminal", None)
    assert funcao is not None, (
        "cadence_service precisa expor cancel_pending_for_terminal(db, lead, "
        "reason) — sem ponto único, cada caminho de transição terminal deixa "
        "follow-up pendente para trás"
    )
    return funcao


@pytest.mark.parametrize("status", ESTADOS_TERMINAIS, ids=lambda s: s.value)
def test_transicao_terminal_zera_followup_pendente(status):
    cancelar = _cancelamento_terminal()
    lead = _lead(status)
    pendentes = [
        _followup(lead, step=FollowUpStep.FOLLOWUP_1),
        _followup(lead, step=FollowUpStep.FOLLOWUP_2),
    ]
    enviado = _followup(lead, step=FollowUpStep.OPENING, status=FollowUpStatus.SENT)
    sessao = _Sessao(leads=[lead], organizacoes=[_organizacao()],
                     followups=pendentes + [enviado])

    encerradas = cancelar(sessao, lead, reason=status.value)

    assert encerradas == len(pendentes)
    assert [fu for fu in sessao.followups if fu.status == FollowUpStatus.PENDING] == []
    # Histórico preservado: etapa já enviada não é reescrita.
    assert enviado.status == FollowUpStatus.SENT


def test_cancelamento_terminal_nao_commita_por_conta_propria():
    """A transação é do chamador (a rota que grava o status terminal)."""
    cancelar = _cancelamento_terminal()
    lead = _lead(LeadStatus.PERDIDO)
    sessao = _Sessao(leads=[lead], organizacoes=[_organizacao()],
                     followups=[_followup(lead)])

    cancelar(sessao, lead, reason="PERDIDO")

    assert sessao.commits == 0
    assert sessao.rollbacks == 0


def test_cancelamento_terminal_sem_pendencia_e_inocuo():
    cancelar = _cancelamento_terminal()
    lead = _lead(LeadStatus.DESQUALIFICADO)
    enviado = _followup(lead, status=FollowUpStatus.SENT)
    sessao = _Sessao(leads=[lead], organizacoes=[_organizacao()], followups=[enviado])

    assert cancelar(sessao, lead, reason="DESQUALIFICADO") == 0
    assert enviado.status == FollowUpStatus.SENT
    assert sessao.commits == 0
