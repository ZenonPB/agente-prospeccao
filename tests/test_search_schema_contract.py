import pytest
from pydantic import ValidationError

from src.schemas.search import CompanySearchRequest, SearchIntent


def test_search_intent_requires_payload_matching_target():
    with pytest.raises(ValidationError, match="company_filters"):
        SearchIntent.model_validate({
            "target": "companies",
            "summary": "Empresas industriais",
            "people_filters": {"titles": ["CEO"]},
        })


def test_company_filter_dsl_rejects_more_than_50_predicates_total():
    expression = {
        "operator": "AND",
        "groups": [
            {
                "operator": "AND",
                "conditions": [
                    {"field": "industry", "operator": "CONTAINS", "value": f"segmento-{group}-{item}"}
                    for item in range(10)
                ],
            }
            for group in range(6)
        ],
    }

    with pytest.raises(ValidationError, match="50 predicados"):
        CompanySearchRequest.model_validate({"expression": expression})


def test_filter_value_rejects_nested_payloads():
    with pytest.raises(ValidationError, match="escalar"):
        CompanySearchRequest.model_validate({
            "expression": {
                "operator": "AND",
                "conditions": [
                    {"field": "industry", "operator": "EQ", "value": {"unsafe": "payload"}},
                ],
            },
        })
