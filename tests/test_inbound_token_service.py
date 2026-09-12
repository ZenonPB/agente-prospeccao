"""Serviço de token de inbound — resolução determinística de organização.

O harness não usa banco: `sqlalchemy_memory` avalia o critério SQLAlchemy real
montado pelo serviço contra linhas de teste, então é o próprio filtro do
serviço que decide o resultado.
"""
import logging
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy_memory import ConsultaMemoria

from src.db.models import Organization
from src.services.inbound_token_service import (
    MAX_TOKEN_LENGTH,
    generate_inbound_token,
    hash_inbound_token,
    resolve_organization_by_token,
)

ORG_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
ORG_B = uuid.UUID("22222222-2222-4222-8222-222222222222")


class _Sessao:
    """Sessão fake que só sabe consultar `organizations`."""

    def __init__(self, organizacoes=()):
        self.organizacoes = list(organizacoes)

    def query(self, *entidades):
        assert entidades[0] is Organization, (
            "o serviço de token não deve consultar nenhuma outra tabela"
        )
        return ConsultaMemoria(
            "organizations",
            [{"organizations": o} for o in self.organizacoes],
        )


def _org(organization_id, token_hash):
    return SimpleNamespace(
        id=organization_id,
        name=f"Org {organization_id}",
        inbound_token_hash=token_hash,
    )


# --------------------------------------------------------------------------
# hash_inbound_token
# --------------------------------------------------------------------------


def test_hash_e_deterministico_e_tem_64_hex():
    primeiro = hash_inbound_token("token-de-inbound")
    segundo = hash_inbound_token("token-de-inbound")

    assert primeiro == segundo
    assert len(primeiro) == 64
    assert all(c in "0123456789abcdef" for c in primeiro)


def test_hash_ignora_espacos_em_volta():
    assert hash_inbound_token("  abc  ") == hash_inbound_token("abc")


def test_hash_difere_por_token():
    assert hash_inbound_token("token-a") != hash_inbound_token("token-b")


def test_hash_nao_contem_o_token_em_claro():
    token = "segredo-do-inbound"
    assert token not in hash_inbound_token(token)


# --------------------------------------------------------------------------
# generate_inbound_token
# --------------------------------------------------------------------------


def test_generate_devolve_par_coerente_dentro_do_limite():
    token, token_hash = generate_inbound_token()

    assert token
    assert 0 < len(token) <= MAX_TOKEN_LENGTH
    assert token_hash == hash_inbound_token(token)
    assert len(token_hash) == 64


def test_generate_nao_repete_token():
    assert generate_inbound_token()[0] != generate_inbound_token()[0]


# --------------------------------------------------------------------------
# resolve_organization_by_token
# --------------------------------------------------------------------------


def test_resolve_devolve_a_organizacao_do_token_entre_duas():
    token_a, hash_a = generate_inbound_token()
    _token_b, hash_b = generate_inbound_token()
    # Org B vem primeiro: um lookup sem filtro correto pegaria a errada.
    sessao = _Sessao([_org(ORG_B, hash_b), _org(ORG_A, hash_a)])

    org = resolve_organization_by_token(sessao, token_a)

    assert org is not None
    assert org.id == ORG_A


def test_resolve_devolve_no_maximo_uma_organizacao():
    token, token_hash = generate_inbound_token()
    sessao = _Sessao([_org(ORG_A, token_hash), _org(ORG_B, token_hash)])

    consulta = sessao.query(Organization).filter(
        Organization.inbound_token_hash == hash_inbound_token(token)
    )
    assert len(consulta.all()) == 2, "cenário só possível sem o índice único"
    # Ainda assim o serviço resolve uma só organização.
    assert resolve_organization_by_token(sessao, token) is not None


def test_resolve_devolve_none_para_token_inexistente():
    _token_a, hash_a = generate_inbound_token()
    sessao = _Sessao([_org(ORG_A, hash_a)])

    assert resolve_organization_by_token(sessao, "token-que-nao-existe") is None


@pytest.mark.parametrize("token", ["", None])
def test_resolve_devolve_none_para_token_ausente(token):
    _token_a, hash_a = generate_inbound_token()
    sessao = _Sessao([_org(ORG_A, hash_a)])

    assert resolve_organization_by_token(sessao, token) is None


def test_resolve_devolve_none_acima_do_limite_de_tamanho():
    token_longo = "a" * (MAX_TOKEN_LENGTH + 1)
    sessao = _Sessao([_org(ORG_A, hash_inbound_token(token_longo))])

    assert resolve_organization_by_token(sessao, token_longo) is None


def test_resolve_ignora_organizacao_sem_token_configurado():
    sessao = _Sessao([_org(ORG_A, None), _org(ORG_B, None)])

    assert resolve_organization_by_token(sessao, "qualquer-token") is None


def test_resolve_nao_registra_o_token_em_log(caplog):
    token, token_hash = generate_inbound_token()
    sessao = _Sessao([_org(ORG_A, token_hash)])

    with caplog.at_level(logging.DEBUG):
        resolve_organization_by_token(sessao, token)
        resolve_organization_by_token(sessao, "token-invalido-qualquer")
        resolve_organization_by_token(sessao, "a" * (MAX_TOKEN_LENGTH + 1))

    registrado = caplog.text
    assert token not in registrado
    assert "token-invalido-qualquer" not in registrado
