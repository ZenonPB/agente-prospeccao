import pytest

from src.schemas.search import FilterCondition, FilterExpression, FilterOperator, SearchTruth
from src.services.prospect_search_service import evaluate_condition, evaluate_expression


def condition(field, operator, value=None):
    return FilterCondition(field=field, operator=operator, value=value)


def test_unknown_is_not_collapsed_to_false_in_boolean_logic():
    document = {"category": "Metalúrgica", "employees": None, "signals": ["HAS_CNC"]}
    expression = FilterExpression(
        operator="AND",
        conditions=[
            condition("industry", FilterOperator.CONTAINS, "metal"),
            condition("employees", FilterOperator.GTE, 20),
        ],
    )
    assert evaluate_expression(document, expression) == SearchTruth.UNKNOWN


def test_and_or_not_follow_three_valued_logic():
    document = {"category": "Metalúrgica", "employees": None, "signals": ["HAS_CNC"]}

    and_expr = FilterExpression(
        operator="AND",
        conditions=[
            condition("signal", FilterOperator.CONTAINS, "HAS_CNC"),
            condition("employees", FilterOperator.GTE, 10),
        ],
    )
    or_expr = FilterExpression(
        operator="OR",
        conditions=[
            condition("industry", FilterOperator.CONTAINS, "software"),
            condition("signal", FilterOperator.CONTAINS, "HAS_CNC"),
        ],
    )
    not_expr = FilterExpression(
        operator="NOT",
        conditions=[condition("employees", FilterOperator.GTE, 10)],
    )

    assert evaluate_expression(document, and_expr) == SearchTruth.UNKNOWN
    assert evaluate_expression(document, or_expr) == SearchTruth.MATCH
    assert evaluate_expression(document, not_expr) == SearchTruth.UNKNOWN


def test_filter_dsl_rejects_unknown_fields_and_invalid_between():
    with pytest.raises(ValueError, match="campo de busca não permitido"):
        evaluate_condition(
            {"company_name": "Teste"},
            condition("raw_sql", FilterOperator.EQ, "DROP TABLE companies"),
        )

    with pytest.raises(ValueError, match="BETWEEN exige"):
        evaluate_condition(
            {"employees": 30},
            condition("employees", FilterOperator.BETWEEN, [10]),
        )


def test_nested_filter_depth_is_bounded():
    leaf = FilterExpression(operator="AND", conditions=[condition("industry", FilterOperator.EQ, "x")])
    level1 = FilterExpression(operator="AND", groups=[leaf])
    level2 = FilterExpression(operator="AND", groups=[level1])
    level3 = FilterExpression(operator="AND", groups=[level2])
    level4 = FilterExpression(operator="AND", groups=[level3])

    with pytest.raises(ValueError, match="profundidade máxima"):
        evaluate_expression({"category": "x"}, level4)
