from sqlalchemy.dialects import postgresql

from src.db.models import Lead
from src.services.analytics_filters import CommercialFilterDTO, normalize_commercial_filters
from src.services.analytics_service import apply_commercial_filters


class CapturedQuery:
    def __init__(self):
        self.criteria = []

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self


def test_filter_context_normaliza_dimensoes_comerciais():
    dto = normalize_commercial_filters({
        "segment": "  psicologia  ",
        "city": " Araraquara ",
        "state": "sp",
        "negotiation_stage": ["rd", "ORCAMENTO"],
    })
    assert dto.segment == "psicologia"
    assert dto.city == "Araraquara"
    assert dto.state == "SP"
    assert dto.negotiation_stage == ["RD", "ORCAMENTO"]


def test_filter_context_aplica_segmento_regiao_e_estagio_no_sql():
    query = CapturedQuery()
    dto = CommercialFilterDTO.model_validate({
        "segment": "psicologia",
        "city": "Araraquara",
        "state": "SP",
        "negotiation_stage": ["RD"],
    })
    apply_commercial_filters(query, dto)
    sql = " ".join(str(item.compile(dialect=postgresql.dialect())) for item in query.criteria)
    assert "leads.category" in sql
    assert "leads.segment_opportunity" in sql
    assert "leads.city" in sql
    assert "upper(leads.state)" in sql.lower()
    assert "leads.negotiation_stage" in sql
