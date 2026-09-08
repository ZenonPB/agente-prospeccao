"""Contrato da resolução cross-provider por alias de empresa (PR 03).

Cobre a identidade de empresa fora do lote: quando um candidato descoberto por
um provider (Google Places, CNAE, PNCP) já existe como outra `Company`/`Lead`
na organização através de uma chave externa registrada (`CompanyAlias`), ele
deve ser mesclado em vez de duplicar.
"""
import operator
import uuid as uuid_mod

from sqlalchemy.sql import operators as sql_ops
from sqlalchemy.sql.elements import BooleanClauseList, BinaryExpression, BindParameter, Null

from database.models import Company, CompanyAlias, Lead


def _org():
    return uuid_mod.UUID(int=1)


def _company(company_id=None, **fields):
    defaults = {
        "id": company_id if company_id is not None else uuid_mod.uuid4(),
        "organization_id": _org(),
        "company_name": "XPTO",
        "name": "XPTO",
        "cnpj": None,
        "website": None,
        "normalized_domain": None,
        "phone": None,
        "address": None,
        "city": None,
        "state": None,
        "google_maps_uri": None,
        "google_rating": None,
    }
    defaults.update(fields)
    return Company(**defaults)


def _alias(company_id, kind, value):
    return CompanyAlias(
        organization_id=_org(),
        company_id=company_id,
        alias_kind=kind,
        alias_value=value,
    )


def _lead(company_id):
    return Lead(id=uuid_mod.uuid4(), organization_id=_org(), company_id=company_id)


class _FakeQuery:
    def __init__(self, rows, aliases=None):
        self.rows = rows
        self._aliases = aliases or []

    @staticmethod
    def _evaluate(expr, obj):
        # Cláusulas compostas (AND/OR) sempre usam a mesma metade do par.
        if isinstance(expr, BooleanClauseList):
            children = expr.get_children(column_collections=False)
            if expr.operator is sql_ops.and_:
                return all(_FakeQuery._evaluate(child, obj) for child in children)
            if expr.operator is sql_ops.or_:
                return any(_FakeQuery._evaluate(child, obj) for child in children)
            return False

        if isinstance(expr, BinaryExpression):
            # Objeto composto (join): escolhe a metade que casa com a coluna.
            if isinstance(obj, tuple):
                left_obj, right_obj = obj
                table = getattr(expr.left, "table", None)
                table_name = table.name if table is not None else ""
                obj = right_obj if table_name == "company_aliases" else left_obj

            column = expr.left.key
            value = getattr(obj, column, None)
            right = expr.right
            if expr.operator is sql_ops.is_not and isinstance(right, Null):
                return value is not None
            if expr.operator is sql_ops.is_ and isinstance(right, Null):
                return value is None
            if expr.operator is operator.eq and isinstance(right, BindParameter):
                return value == right.value
            if expr.operator is operator.eq:
                return value == right
        return False

    def filter(self, *criteria):
        return _FakeQuery(
            [row for row in self.rows if all(self._evaluate(c, row) for c in criteria)],
            aliases=self._aliases,
        )

    def join(self, _target, *_args):
        # Junção empresa × alias: gera pares (company, alias) casados por id.
        joined = []
        for company in self.rows:
            for alias in self._aliases:
                if alias.company_id == getattr(company, "id", None):
                    joined.append((company, alias))
        return _FakeQuery(joined)

    def order_by(self, *_args):
        return self

    def first(self):
        return self.rows[0][0] if self.rows and isinstance(self.rows[0], tuple) else (self.rows[0] if self.rows else None)

    def all(self):
        return [row[0] if isinstance(row, tuple) else row for row in self.rows]


class FakeDB:
    def __init__(self, companies=None, aliases=None, leads=None):
        self.companies = companies or []
        self.aliases = aliases or []
        self.leads = leads or []
        self.added = []

    def query(self, model):
        if model is Company or model is Lead:
            rows = self.companies if model is Company else self.leads
            return _FakeQuery(list(rows), aliases=self.aliases)
        if model is CompanyAlias:
            return _FakeQuery(list(self.aliases))
        return _FakeQuery([])

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass


from services.company_person_service import CompanyPersonService  # noqa: E402


# --- find_company_by_aliases -------------------------------------------------


def test_find_by_cnpj_prioriza_chave_mais_forte():
    db = FakeDB(companies=[_company(cnpj="00111222000133")])
    company = CompanyPersonService.find_company_by_aliases(
        db, _org(), {"cnpj": "00111222000133", "website": "https://xpto.com.br"}
    )
    assert company is not None
    assert company.cnpj == "00111222000133"


def test_find_by_dominio_casa_depois_do_cnpj():
    db = FakeDB(
        companies=[
            _company(cnpj=None, website="https://xpto.com.br", normalized_domain="xpto.com.br"),
        ]
    )
    company = CompanyPersonService.find_company_by_aliases(
        db, _org(), {"cnpj": None, "website": "https://www.xpto.com.br/contato"}
    )
    assert company is not None
    assert company.normalized_domain == "xpto.com.br"


def test_find_by_place_id_alias_resolve_empresa():
    company_id = uuid_mod.uuid4()
    db = FakeDB(
        companies=[_company(company_id)],
        aliases=[_alias(company_id, "place_id", "ChIJ1")],
    )
    company = CompanyPersonService.find_company_by_aliases(
        db, _org(), {"place_id_candidate": "ChIJ1"}
    )
    assert company is not None
    assert company.id == company_id


def test_find_by_google_maps_uri_alias_resolve_empresa():
    company_id = uuid_mod.uuid4()
    db = FakeDB(
        companies=[_company(company_id)],
        aliases=[_alias(company_id, "google_maps_uri", "https://maps.google.com/?cid=7")],
    )
    company = CompanyPersonService.find_company_by_aliases(
        db, _org(), {"maps_uri": "https://maps.google.com/?cid=7"}
    )
    assert company is not None
    assert company.id == company_id


def test_find_sem_chave_ou_sem_match_retorna_none():
    db = FakeDB(companies=[_company()])
    assert CompanyPersonService.find_company_by_aliases(db, _org(), {"name": "XPTO"}) is None
    assert CompanyPersonService.find_company_by_aliases(
        db, _org(), {"cnpj": "11111111111111"}
    ) is None


def test_find_ignora_outra_organizacao():
    db = FakeDB(companies=[_company(cnpj="00111222000133")])
    other_org = uuid_mod.UUID(int=2)
    assert (
        CompanyPersonService.find_company_by_aliases(db, other_org, {"cnpj": "00111222000133"})
        is None
    )


# --- register_company_aliases ------------------------------------------------


def test_register_aliases_registra_place_id_dominio_e_maps_uri():
    company_id = uuid_mod.uuid4()
    db = FakeDB(companies=[_company(company_id)])
    CompanyPersonService.register_company_aliases(
        db,
        _org(),
        company_id,
        {
            "place_id": "ChIJ1",
            "normalized_domain": "xpto.com.br",
            "google_maps_uri": "https://maps.google.com/?cid=7",
            "provider": "google_places",
        },
    )
    added = [(a.alias_kind, a.alias_value) for a in db.added]
    assert ("place_id", "ChIJ1") in added
    assert ("normalized_domain", "xpto.com.br") in added
    assert ("google_maps_uri", "https://maps.google.com/?cid=7") in added


def test_register_alias_nao_duplica_com_registro_existente():
    company_id = uuid_mod.uuid4()
    db = FakeDB(
        companies=[_company(company_id)],
        aliases=[_alias(company_id, "place_id", "ChIJ1")],
    )
    CompanyPersonService.register_company_aliases(db, _org(), company_id, {"place_id": "ChIJ1"})
    assert not db.added


# --- Resolução cross-provider no pipeline -------------------------------------


def test_resolve_cross_provider_lead_retorna_lead_da_mesma_company():
    """Candidato novo que casa por alias deve deduplicar contra lead existente."""
    from src.pipeline_worker import resolve_cross_provider_lead

    company_id = uuid_mod.uuid4()
    existing = _lead(company_id)
    db = FakeDB(
        companies=[_company(company_id, cnpj="00111222000133")],
        aliases=[_alias(company_id, "place_id", "ChIJ9")],
        leads=[existing],
    )
    result = resolve_cross_provider_lead(
        db,
        _org(),
        {"company_name": "XPTO", "place_id_candidate": "ChIJ9", "provider": "google_places"},
    )
    assert result is existing


def test_resolve_cross_provider_lead_retorna_none_sem_company_casada():
    from src.pipeline_worker import resolve_cross_provider_lead

    db = FakeDB(companies=[_company(cnpj="00111222000133")])
    result = resolve_cross_provider_lead(
        db,
        _org(),
        {"company_name": "OUTRA EMPRESA", "place_id_candidate": "ChIJ9", "provider": "google_places"},
    )
    assert result is None


def test_backfill_candidate_fields_preenche_vazios_e_nao_sobrescreve():
    from src.pipeline_worker import _backfill_candidate_fields

    lead = Lead(id=uuid_mod.uuid4(), organization_id=_org(), company_name="XPTO", cnpj=None, phone=None)
    changed = _backfill_candidate_fields(
        lead, {"cnpj": "00111222000133", "phone": "11999999999"}
    )
    assert changed is True
    assert lead.cnpj == "00111222000133"
    assert lead.phone == "11999999999"

    lead2 = Lead(id=uuid_mod.uuid4(), organization_id=_org(), company_name="XPTO", cnpj="1234", phone="110")
    changed2 = _backfill_candidate_fields(lead2, {"cnpj": "00111", "phone": "11999999999"})
    assert changed2 is False
    assert lead2.cnpj == "1234"
    assert lead2.phone == "110"


def test_merge_discovery_provenance_acumula_providers_sem_duplicar():
    from src.pipeline_worker import _merge_discovery_provenance

    lead = Lead(
        id=uuid_mod.uuid4(),
        organization_id=_org(),
        company_name="XPTO",
        discovery_provenance={"providers": ["cnae"], "provider_queries": ["metalurgia sp"]},
    )
    _merge_discovery_provenance(
        lead,
        {"discovery_provenance": {"provider": "google_places", "providers": ["google_places"]}},
    )
    assert set(lead.discovery_provenance["providers"]) == {"cnae", "google_places"}
    assert lead.discovery_provenance["provider"] == "google_places"


def test_candidate_identity_data_extrai_chaves_do_item():
    from src.pipeline_worker import _candidate_identity_data

    data = _candidate_identity_data(
        {
            "cnpj": "00111222000133",
            "website": "https://xpto.com.br",
            "place_id_candidate": "ChIJ1",
            "maps_uri": "https://maps.google.com/?cid=7",
            "provider": "google_places",
        }
    )
    assert data["cnpj"] == "00111222000133"
    assert data["place_id"] == "ChIJ1"
    assert data["google_maps_uri"] == "https://maps.google.com/?cid=7"
    assert data["provider"] == "google_places"