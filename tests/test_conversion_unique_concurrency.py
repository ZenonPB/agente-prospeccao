"""Conversão única por lead e oferta, inclusive sob requisições concorrentes.

Invariante sob teste: uma venda é um fato único. Duas ou mais requisições de
conversão para o mesmo `lead_id` + `offer_key` — duplo clique, retry do cliente,
duas abas — devem deixar exatamente um registro `Conversion`, uma única resposta
de sucesso e `409` para as demais, sem vazar nome de constraint, nome de tabela
nem texto de exceção do banco no corpo da resposta.

O arquivo tem duas camadas:

- **Determinística, sem banco** — a garantia declarada no modelo
  (`Conversion.__table_args__`) e o escopo do filtro de `find_duplicate_conversion`.
  O filtro é exercitado pela consulta em memória de `sqlalchemy_memory`, que
  avalia os critérios SQLAlchemy reais montados pela produção contra linhas de
  teste: quem decide o resultado é o filtro do próprio código.
- **Concorrência real, com Postgres** — n transações paralelas de verdade contra
  a rota `POST /api/leads/{id}/conversion`. Exige `E2E_DATABASE_URL` (ou uma
  `DATABASE_URL` alcançável) e é pulada automaticamente sem banco, no mesmo
  padrão de `tests/e2e_outreach_cycle.py`.

Rodar da raiz:

    python -m pytest tests/test_conversion_unique_concurrency.py -q
"""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import Index

from database.models import Conversion
from db_reachable import database_url, is_database_reachable
from sqlalchemy_memory import ConsultaMemoria

from src.routes import leads as leads_module
from src.routes.leads import find_duplicate_conversion

LEAD_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OUTRO_LEAD_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
OPORTUNIDADE_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OPORTUNIDADE_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

# Sentinel que a rota já usa para "sem oferta" (`if body.offer_key != "unknown"`).
# O banco tem de concordar com esse significado, senão duas conversões com
# `offer_key` nulo passam pelo índice único (NULLs são distintos entre si).
SENTINEL_SEM_OFERTA = "unknown"
NOME_INDICE_UNICO = "uq_conversions_lead_offer"

# Palavras que denunciam vazamento de detalhe interno do banco no corpo HTTP.
VAZAMENTOS_PROIBIDOS = (
    NOME_INDICE_UNICO,
    "conversions",
    "constraint",
    "duplicate key",
    "integrityerror",
    "psycopg",
    "sqlalchemy",
    "traceback",
    "unique index",
)


# --------------------------------------------------------------------------
# Camada 1 — garantia declarada no modelo (sem banco)
# --------------------------------------------------------------------------


def _indices_declarados():
    """Índices declarados em `Conversion.__table_args__`."""
    return [arg for arg in Conversion.__table_args__ if isinstance(arg, Index)]


def _indice_por_nome(nome):
    for indice in _indices_declarados():
        if indice.name == nome:
            return indice
    return None


def _texto_das_expressoes(indice) -> str:
    """Expressões do índice como SQL legível, com literais renderizados."""
    partes = []
    for expressao in indice.expressions:
        try:
            partes.append(
                str(expressao.compile(compile_kwargs={"literal_binds": True})),
            )
        except Exception:
            partes.append(str(expressao))
    return " ".join(partes).lower()


def test_modelo_declara_indice_unico_por_lead_e_oferta():
    """Sem constraint no banco, o check-then-insert da rota é só uma corrida."""
    indice = _indice_por_nome(NOME_INDICE_UNICO)
    assert indice is not None, (
        "Conversion.__table_args__ não declara o índice "
        f"'{NOME_INDICE_UNICO}'; a unicidade de lead+oferta depende só do "
        "check da aplicação, que duas transações paralelas atravessam juntas. "
        f"Índices declarados: {[i.name for i in _indices_declarados()]}"
    )
    assert indice.unique is True, (
        f"'{NOME_INDICE_UNICO}' existe mas não é único — não impede a duplicata."
    )


def test_indice_unico_cobre_lead_e_oferta_com_sentinel():
    """A chave é lead + oferta, com oferta nula colapsada no sentinel."""
    indice = _indice_por_nome(NOME_INDICE_UNICO)
    assert indice is not None, f"índice '{NOME_INDICE_UNICO}' não declarado"
    texto = _texto_das_expressoes(indice)
    assert "lead_id" in texto, f"índice não cobre lead_id: {texto}"
    assert "offer_key" in texto, f"índice não cobre offer_key: {texto}"
    assert "coalesce" in texto, (
        "índice único simples não serve: `offer_key` é nullable e NULLs são "
        f"distintos entre si — é preciso coalesce sobre a coluna: {texto}"
    )
    assert SENTINEL_SEM_OFERTA in texto, (
        f"o sentinel de 'sem oferta' deve ser '{SENTINEL_SEM_OFERTA}', o mesmo "
        f"que a rota usa: {texto}"
    )


def test_indice_de_busca_por_lead_permanece():
    """Regressão: a mudança é aditiva, não substitui o índice de leitura."""
    assert _indice_por_nome("ix_conversions_lead_id") is not None, (
        "ix_conversions_lead_id foi removido — a mudança devia ser aditiva"
    )


# --------------------------------------------------------------------------
# Camada 1 — escopo do filtro de duplicata (sem banco)
# --------------------------------------------------------------------------


class _SessaoMemoria:
    """Sessão fake que devolve as conversões de teste para `query(Conversion)`."""

    def __init__(self, conversoes=()):
        self.conversoes = list(conversoes)

    def query(self, *entidades):
        modelo = entidades[0]
        tabela = getattr(modelo, "__tablename__", "desconhecido")
        if modelo is Conversion:
            return ConsultaMemoria(
                "conversions", [{"conversions": c} for c in self.conversoes],
            )
        return ConsultaMemoria(tabela, [])


def _conversao(lead_id=LEAD_ID, offer_key="trophies", lead_opportunity_id=None):
    return Conversion(
        id=uuid.uuid4(),
        lead_id=lead_id,
        offer_key=offer_key,
        lead_opportunity_id=lead_opportunity_id,
        service_sold="Troféus personalizados",
    )


def test_duplicata_ignora_a_oportunidade_de_origem():
    """O check tem de ter o mesmo escopo da constraint: lead + oferta.

    Se a oportunidade estreitar a busca, o check aceita o que o banco rejeita.
    """
    sessao = _SessaoMemoria([
        _conversao(offer_key="trophies", lead_opportunity_id=OPORTUNIDADE_A),
    ])
    duplicata = find_duplicate_conversion(
        sessao,
        lead_id=LEAD_ID,
        offer_key="trophies",
        lead_opportunity_id=OPORTUNIDADE_B,
    )
    assert duplicata is not None, (
        "conversão da mesma oferta em outra oportunidade não foi vista como "
        "duplicata — o filtro é mais estreito que a unicidade de lead+oferta"
    )


def test_oferta_nula_conta_como_sem_oferta():
    """Conversão antiga com `offer_key` nulo é a mesma coisa que 'unknown'."""
    sessao = _SessaoMemoria([_conversao(offer_key=None)])
    duplicata = find_duplicate_conversion(
        sessao,
        lead_id=LEAD_ID,
        offer_key=SENTINEL_SEM_OFERTA,
        lead_opportunity_id=None,
    )
    assert duplicata is not None, (
        "conversão com offer_key nulo não foi vista como duplicata de "
        f"'{SENTINEL_SEM_OFERTA}' — app e banco discordam sobre 'sem oferta'"
    )


def test_conversao_sem_oferta_repetida_e_duplicata():
    """Regressão: sentinel igual ao sentinel já é reconhecido hoje."""
    sessao = _SessaoMemoria([_conversao(offer_key=SENTINEL_SEM_OFERTA)])
    duplicata = find_duplicate_conversion(
        sessao,
        lead_id=LEAD_ID,
        offer_key=SENTINEL_SEM_OFERTA,
        lead_opportunity_id=None,
    )
    assert duplicata is not None


def test_outra_oferta_no_mesmo_lead_nao_e_duplicata():
    """Regressão: o alinhamento não pode alargar a unicidade além da oferta."""
    sessao = _SessaoMemoria([_conversao(offer_key="trophies")])
    duplicata = find_duplicate_conversion(
        sessao,
        lead_id=LEAD_ID,
        offer_key="erp",
        lead_opportunity_id=None,
    )
    assert duplicata is None


def test_mesma_oferta_em_outro_lead_nao_e_duplicata():
    """Regressão: a unicidade é por lead, nunca global por oferta."""
    sessao = _SessaoMemoria([_conversao(lead_id=OUTRO_LEAD_ID, offer_key="trophies")])
    duplicata = find_duplicate_conversion(
        sessao,
        lead_id=LEAD_ID,
        offer_key="trophies",
        lead_opportunity_id=None,
    )
    assert duplicata is None


# --------------------------------------------------------------------------
# Camada 2 — concorrência real contra Postgres
# --------------------------------------------------------------------------

DB_URL = database_url()
_concorrencia = pytest.mark.skipif(
    not is_database_reachable(DB_URL),
    reason="Postgres indisponivel - concorrencia real requer banco real",
)


@pytest.fixture()
def fabrica_sessao():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from database.models import Base

    engine = create_engine(DB_URL)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()


@pytest.fixture()
def cenario(fabrica_sessao):
    """Organização + lead descartáveis; limpa tudo o que a rota escreve."""
    from database.models import (
        CommercialOutcomeRow,
        Lead,
        LeadActivity,
        LeadStatus,
        Organization,
    )

    sessao = fabrica_sessao()
    sufixo = uuid.uuid4().hex[:8]
    org = Organization(
        id=uuid.uuid4(),
        name=f"Conversao Concorrente {sufixo}",
        slug=f"conversao-concorrente-{sufixo}",
    )
    sessao.add(org)
    sessao.flush()
    lead = Lead(
        id=uuid.uuid4(),
        organization_id=org.id,
        company_name="Metalúrgica Concorrente",
        city="Curitiba",
        status=LeadStatus.PROPOSTA_ENVIADA,
    )
    sessao.add(lead)
    sessao.commit()
    dados = SimpleNamespace(org_id=org.id, lead_id=lead.id, sessao=sessao)
    try:
        yield dados
    finally:
        sessao.rollback()
        for modelo in (Conversion, LeadActivity, CommercialOutcomeRow):
            sessao.query(modelo).filter(
                modelo.lead_id == lead.id,
            ).delete(synchronize_session=False)
        sessao.query(Lead).filter(Lead.id == lead.id).delete(synchronize_session=False)
        sessao.query(Organization).filter(
            Organization.id == org.id,
        ).delete(synchronize_session=False)
        sessao.commit()
        sessao.close()


def _app_com_sessoes_reais(fabrica_sessao, org_id, monkeypatch):
    """App mínimo com a rota real e uma sessão de banco por requisição.

    Sessão por requisição é o ponto: transações paralelas de verdade, não n
    chamadas na mesma unidade de trabalho.
    """
    from src.auth.dependencies import (
        get_current_user,
        get_user_membership,
        get_user_organization,
    )
    from src.db.dependencies import get_db
    from src.db.models import OrganizationRole
    from src.middleware.rate_limit import limiter
    from src.routes.leads import router as leads_router

    monkeypatch.setattr(limiter, "enabled", False)
    user_id = uuid.uuid4()

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(leads_router, prefix="/api")

    def _sessao_por_requisicao():
        db = fabrica_sessao()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _sessao_por_requisicao
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id, email="stub@test.local",
    )
    app.dependency_overrides[get_user_organization] = lambda: SimpleNamespace(id=org_id)
    app.dependency_overrides[get_user_membership] = lambda: SimpleNamespace(
        id="m-1", user_id=user_id, organization_id=org_id,
        role=OrganizationRole.OWNER, sales_role=None,
    )
    return app


def _forcar_corrida(monkeypatch, n):
    """Faz as n requisições atravessarem o check de duplicata juntas.

    Sem isso a corrida depende do escalonador e o teste ficaria intermitente.
    A barreira não altera a lógica: o check roda de verdade e devolve o
    resultado real, só espera os pares antes de seguir para a inserção.
    """
    barreira = threading.Barrier(n, timeout=30)
    original = leads_module.find_duplicate_conversion

    def com_barreira(*args, **kwargs):
        resultado = original(*args, **kwargs)
        try:
            barreira.wait()
        except threading.BrokenBarrierError:
            pass
        return resultado

    monkeypatch.setattr(leads_module, "find_duplicate_conversion", com_barreira)


def _disparar(app, lead_id, n, offer_key=SENTINEL_SEM_OFERTA, paralelo=True):
    """Dispara n requisições de conversão e devolve (status, corpo) de cada uma.

    Um `TestClient` por thread: o cliente carrega estado de portal assíncrono e
    compartilhá-lo entre threads mediria o cliente, não a rota.
    """
    corpo = {"offer_key": offer_key, "service_sold": "Troféus", "contract_value": 1000.0}

    def requisitar(_indice):
        with TestClient(app, raise_server_exceptions=False) as client:
            resposta = client.post(f"/api/leads/{lead_id}/conversion", json=corpo)
            return resposta.status_code, resposta.text

    if not paralelo:
        return [requisitar(i) for i in range(n)]
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(requisitar, range(n)))


def _contar_conversoes(sessao, lead_id, offer_key=SENTINEL_SEM_OFERTA):
    from sqlalchemy import func

    sessao.expire_all()
    return sessao.query(Conversion).filter(
        (Conversion.lead_id == lead_id)
        & (func.coalesce(Conversion.offer_key, SENTINEL_SEM_OFERTA) == offer_key),
    ).count()


def _assertar_sem_vazamento(respostas):
    for status, texto in respostas:
        if status < 400:
            continue
        minusculo = texto.lower()
        for termo in VAZAMENTOS_PROIBIDOS:
            assert termo not in minusculo, (
                f"corpo da resposta {status} expõe detalhe interno do banco "
                f"('{termo}'): {texto}"
            )


@_concorrencia
@pytest.mark.e2e
@pytest.mark.parametrize("n", [2, 5])
def test_conversoes_concorrentes_geram_um_unico_registro(
    fabrica_sessao, cenario, monkeypatch, n,
):
    """n transações paralelas do mesmo lead+oferta ⇒ contagem final igual a 1."""
    app = _app_com_sessoes_reais(fabrica_sessao, cenario.org_id, monkeypatch)
    _forcar_corrida(monkeypatch, n)

    _disparar(app, cenario.lead_id, n, offer_key="trophies")

    registros = _contar_conversoes(cenario.sessao, cenario.lead_id, "trophies")
    assert registros == 1, (
        f"{n} requisições concorrentes duplicaram a venda no BI: "
        f"{registros} registros"
    )


@_concorrencia
@pytest.mark.e2e
@pytest.mark.parametrize("n", [2, 5])
def test_concorrencia_tem_exatamente_um_sucesso_e_o_resto_409(
    fabrica_sessao, cenario, monkeypatch, n,
):
    """Distribuição de status: um sucesso, n-1 conflitos — nada de 500."""
    app = _app_com_sessoes_reais(fabrica_sessao, cenario.org_id, monkeypatch)
    _forcar_corrida(monkeypatch, n)

    respostas = _disparar(app, cenario.lead_id, n, offer_key="trophies")
    codigos = sorted(status for status, _ in respostas)

    sucessos = [s for s in codigos if 200 <= s < 300]
    assert len(sucessos) == 1, f"esperado exatamente 1 sucesso, obtido {codigos}"
    assert [s for s in codigos if not (200 <= s < 300)] == [409] * (n - 1), (
        f"as demais respostas deviam ser 409, obtido {codigos}"
    )


@_concorrencia
@pytest.mark.e2e
def test_conflito_nao_expoe_detalhe_do_banco(fabrica_sessao, cenario, monkeypatch):
    """A recusa é frase de domínio: o detalhe técnico fica no log."""
    n = 3
    app = _app_com_sessoes_reais(fabrica_sessao, cenario.org_id, monkeypatch)
    _forcar_corrida(monkeypatch, n)

    respostas = _disparar(app, cenario.lead_id, n, offer_key="trophies")
    _assertar_sem_vazamento(respostas)


@_concorrencia
@pytest.mark.e2e
@pytest.mark.parametrize("n", [1, 3])
def test_conversao_com_oferta_nula_nao_duplica(
    fabrica_sessao, cenario, monkeypatch, n,
):
    """Conversão antiga com `offer_key` nulo já ocupa a chave 'sem oferta'.

    A rota só aceita `offer_key` preenchido, então o caso nulo entra pelo dado
    legado: nenhuma requisição de `unknown` pode criar um segundo registro.
    """
    legado = Conversion(
        id=uuid.uuid4(),
        lead_id=cenario.lead_id,
        offer_key=None,
        service_sold="Venda registrada antes da oferta",
    )
    cenario.sessao.add(legado)
    cenario.sessao.commit()

    app = _app_com_sessoes_reais(fabrica_sessao, cenario.org_id, monkeypatch)
    if n > 1:
        _forcar_corrida(monkeypatch, n)

    respostas = _disparar(app, cenario.lead_id, n, offer_key=SENTINEL_SEM_OFERTA)

    assert _contar_conversoes(cenario.sessao, cenario.lead_id) == 1, (
        "conversão com offer_key nulo foi duplicada por requisição 'unknown'"
    )
    assert [status for status, _ in respostas] == [409] * n, (
        f"todas as requisições deviam conflitar, obtido {respostas}"
    )
    _assertar_sem_vazamento(respostas)


@_concorrencia
@pytest.mark.e2e
def test_banco_rejeita_segunda_conversao_do_mesmo_par(fabrica_sessao, cenario):
    """A garantia é do banco, não só da aplicação (Requisito 7.3)."""
    from sqlalchemy.exc import IntegrityError

    primeira = fabrica_sessao()
    segunda = fabrica_sessao()
    try:
        primeira.add(Conversion(
            id=uuid.uuid4(), lead_id=cenario.lead_id, offer_key="trophies",
        ))
        primeira.commit()
        segunda.add(Conversion(
            id=uuid.uuid4(), lead_id=cenario.lead_id, offer_key="trophies",
        ))
        with pytest.raises(IntegrityError):
            segunda.commit()
    finally:
        segunda.rollback()
        segunda.close()
        primeira.close()
