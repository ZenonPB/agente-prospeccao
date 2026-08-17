"""Testes de acesso: CONSULTOR convidado (não dono) não vê BI/analytics.

Cenário de negócio: um usuário convidado para o workspace com *apenas* o papel
de venda CONSULTOR NÃO tem acesso aos dados, análises, gráficos e ações
exclusivas de diretores (owner/admin) e analistas de vendas (ANALYST/MANAGER).

Cobre os guards usados pelas rotas:
- `require_analyst()` / `require_manager()` (dependências FastAPI) → 403;
- `is_full_access(member)` → False para CONSULTOR não-dono;
- `consultant_lead_scope(...)` → CONSULTOR só vê leads próprios/não atribuídos;
- owner/admin e ANALYST/MANAGER continuam passando (regressão).
"""
import uuid

import pytest
from fastapi import HTTPException

from src.auth.dependencies import require_analyst, require_manager
from src.db.models import OrganizationRole, SalesRole, Lead
from src.services.org_service import consultant_lead_scope, is_full_access


class _Member:
    """Stub minimalista de `OrganizationMember` (só o que os guards leem)."""

    def __init__(self, role: OrganizationRole, sales_role: SalesRole | None, user_id=None):
        self.role = role
        self.sales_role = sales_role
        self.user_id = user_id or uuid.uuid4()


# ---------------------------------------------------------------------------
# Guard de BI: `require_analyst` (usado em analytics.py, leads.py, pdf).
# ---------------------------------------------------------------------------

def test_consultor_convidado_nao_dono_leva_403_no_require_analyst():
    member = _Member(OrganizationRole.MEMBER, SalesRole.CONSULTOR)
    dep = require_analyst()
    with pytest.raises(HTTPException) as exc:
        dep(member)
    assert exc.value.status_code == 403


def test_consultor_convidado_nao_dono_leva_403_no_require_manager():
    member = _Member(OrganizationRole.MEMBER, SalesRole.CONSULTOR)
    dep = require_manager()
    with pytest.raises(HTTPException) as exc:
        dep(member)
    assert exc.value.status_code == 403


def test_require_analyst_aceita_analyst_e_manager():
    for sales_role in (SalesRole.ANALYST, SalesRole.MANAGER):
        member = _Member(OrganizationRole.MEMBER, sales_role)
        assert require_analyst()(member) is member


def test_require_analyst_aceita_owner_e_admin_independente_do_papel_de_venda():
    # Diretores passam mesmo com sales_role CONSULTOR (papel administrativo).
    owner = _Member(OrganizationRole.OWNER, SalesRole.CONSULTOR)
    admin = _Member(OrganizationRole.ADMIN, SalesRole.CONSULTOR)
    assert require_analyst()(owner) is owner
    assert require_analyst()(admin) is admin


def test_require_manager_aceita_manager_mas_bloqueia_analyst():
    manager = _Member(OrganizationRole.MEMBER, SalesRole.MANAGER)
    analyst = _Member(OrganizationRole.MEMBER, SalesRole.ANALYST)
    assert require_manager()(manager) is manager
    with pytest.raises(HTTPException) as exc:
        require_manager()(analyst)
    assert exc.value.status_code == 403


def test_sales_role_weight_crescente():
    # Regressão do ranking de privilégios usado pelos guards: ANALYST e MANAGER
    # passam no guard de BI; CONSULTOR é sempre barrado no guard mínimo.
    guard = require_analyst()
    consultor = _Member(OrganizationRole.MEMBER, SalesRole.CONSULTOR)
    analyst = _Member(OrganizationRole.MEMBER, SalesRole.ANALYST)
    manager = _Member(OrganizationRole.MEMBER, SalesRole.MANAGER)
    with pytest.raises(HTTPException):
        guard(consultor)
    assert guard(analyst) is analyst
    assert guard(manager) is manager


# ---------------------------------------------------------------------------
# `is_full_access` — quem enxerga TODOS os leads da org.
# ---------------------------------------------------------------------------

def test_consultor_convidado_nao_tem_acesso_total():
    member = _Member(OrganizationRole.MEMBER, SalesRole.CONSULTOR)
    assert is_full_access(member) is False


def test_full_access_para_diretores_e_analistas():
    cases = [
        _Member(OrganizationRole.OWNER, SalesRole.CONSULTOR),
        _Member(OrganizationRole.ADMIN, SalesRole.CONSULTOR),
        _Member(OrganizationRole.MEMBER, SalesRole.ANALYST),
        _Member(OrganizationRole.MEMBER, SalesRole.MANAGER),
    ]
    for member in cases:
        assert is_full_access(member) is True


# ---------------------------------------------------------------------------
# `consultant_lead_scope` — escopo de visibilidade na listagem de leads.
# ---------------------------------------------------------------------------

class _FakeFilteredQuery:
    """Grava o filtro aplicado (superfícies: column_descriptions + filter)."""

    def __init__(self, entity=Lead):
        self.entity = entity
        self.applied = None

    @property
    def column_descriptions(self):
        return [{"entity": self.entity}]

    def filter(self, *criteria):
        self.applied = criteria
        return self


def test_consultor_so_ve_proprios_e_nao_atribuidos():
    member = _Member(OrganizationRole.MEMBER, SalesRole.CONSULTOR)
    query = _FakeFilteredQuery()
    result = consultant_lead_scope(member, query)
    assert result is query
    assert query.applied is not None
    # CONSULTOR nunca passa query sem filtro (não vê a org inteira).
    assert len(query.applied) == 1


def test_full_access_nao_aplica_filtro_de_escopo():
    for member in [
        _Member(OrganizationRole.OWNER, SalesRole.CONSULTOR),
        _Member(OrganizationRole.MEMBER, SalesRole.ANALYST),
    ]:
        query = _FakeFilteredQuery()
        result = consultant_lead_scope(member, query)
        assert result is query
        assert query.applied is None