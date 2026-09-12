from types import SimpleNamespace
import uuid

from sqlalchemy_memory import ConsultaMemoria
from src.db.models import Company
from src.schemas.search import CompanySearchRequest
from src.services.prospect_search_service import ProspectSearchService


class _Query(ConsultaMemoria):
    def limit(self, value):
        self._limit = value
        return self

    def all(self):
        rows = super().all()
        return rows[: getattr(self, "_limit", len(rows))]


class _DB:
    def __init__(self, companies):
        self.companies = companies

    def query(self, model, *_args):
        if model is Company:
            return _Query(
                "companies",
                [{"companies": company} for company in self.companies],
            )
        raise AssertionError(f"consulta inesperada: {model}")


def _company(org_id, name):
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=org_id,
        company_name=name,
        name=name,
        cnpj=None,
        website=None,
        normalized_domain=None,
        phone=None,
        address=None,
        city="Araraquara",
        state="SP",
        country="Brasil",
        category="Indústria",
        google_rating=None,
        google_rating_count=None,
        google_maps_uri=None,
        company_linkedin_url=None,
        instagram_url=None,
        raw_data=None,
        created_at=None,
    )


def test_company_search_fails_closed_to_active_organization():
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    db = _DB([_company(org_b, "Empresa de outro tenant")])

    result = ProspectSearchService(db, org_a).search_companies(CompanySearchRequest())

    assert result["companies"] == []
    assert result["total"] == 0
