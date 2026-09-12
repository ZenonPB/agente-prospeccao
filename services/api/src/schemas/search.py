"""DTOs validados para busca avançada de empresas e pessoas."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SearchTruth(str, Enum):
    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    UNKNOWN = "UNKNOWN"


class FilterOperator(str, Enum):
    EQ = "EQ"
    CONTAINS = "CONTAINS"
    IN = "IN"
    GTE = "GTE"
    LTE = "LTE"
    BETWEEN = "BETWEEN"
    EXISTS = "EXISTS"


class FilterCondition(BaseModel):
    field: str = Field(..., min_length=1, max_length=64)
    operator: FilterOperator = FilterOperator.EQ
    value: Any = None

    @field_validator("value")
    @classmethod
    def validate_value_shape(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            if isinstance(value, str) and len(value) > 500:
                raise ValueError("valor de filtro excede 500 caracteres")
            return value
        if isinstance(value, list):
            if len(value) > 50:
                raise ValueError("lista de filtro excede 50 itens")
            if any(not isinstance(item, (str, int, float, bool)) for item in value):
                raise ValueError("lista de filtro aceita apenas valores escalares")
            if any(isinstance(item, str) and len(item) > 500 for item in value):
                raise ValueError("item de filtro excede 500 caracteres")
            return value
        raise ValueError("valor de filtro deve ser escalar ou lista de escalares")


class FilterExpression(BaseModel):
    operator: Literal["AND", "OR", "NOT"] = "AND"
    conditions: list[FilterCondition] = Field(default_factory=list, max_length=50)
    groups: list["FilterExpression"] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.operator == "NOT" and len(self.conditions) + len(self.groups) != 1:
            raise ValueError("NOT exige exatamente uma condição ou grupo")
        if not self.conditions and not self.groups:
            raise ValueError("expressão de filtro vazia")
        return self


def _expression_stats(expression: FilterExpression, depth: int = 1) -> tuple[int, int]:
    deepest = depth
    predicates = len(expression.conditions)
    for group in expression.groups:
        child_predicates, child_depth = _expression_stats(group, depth + 1)
        predicates += child_predicates
        deepest = max(deepest, child_depth)
    return predicates, deepest


class CompanySearchRequest(BaseModel):
    query: str | None = Field(None, max_length=200)
    locations: list[str] = Field(default_factory=list, max_length=20)
    industries: list[str] = Field(default_factory=list, max_length=20)
    cnaes: list[str] = Field(default_factory=list, max_length=30)
    sizes: list[str] = Field(default_factory=list, max_length=20)
    employee_min: int | None = Field(None, ge=0)
    employee_max: int | None = Field(None, ge=0)
    revenue_min: float | None = Field(None, ge=0)
    revenue_max: float | None = Field(None, ge=0)
    age_min: int | None = Field(None, ge=0, le=500)
    age_max: int | None = Field(None, ge=0, le=500)
    technologies: list[str] = Field(default_factory=list, max_length=30)
    signals: list[str] = Field(default_factory=list, max_length=30)
    intent: list[str] = Field(default_factory=list, max_length=30)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    exclusions: list[str] = Field(default_factory=list, max_length=30)
    expression: FilterExpression | None = None
    include_unknown: bool = False
    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0, le=10000)

    @model_validator(mode="after")
    def validate_ranges_and_complexity(self):
        for minimum, maximum, label in (
            (self.employee_min, self.employee_max, "employees"),
            (self.revenue_min, self.revenue_max, "revenue"),
            (self.age_min, self.age_max, "age"),
        ):
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"intervalo inválido para {label}")
        if self.expression is not None:
            predicates, depth = _expression_stats(self.expression)
            if depth > 3:
                raise ValueError("expressão excede profundidade máxima de 3 níveis")
            if predicates > 50:
                raise ValueError("expressão excede 50 predicados")
        return self


class PeopleSearchRequest(BaseModel):
    query: str | None = Field(None, max_length=200)
    company: str | None = Field(None, max_length=200)
    domain: str | None = Field(None, max_length=255)
    titles: list[str] = Field(default_factory=list, max_length=30)
    functions: list[str] = Field(default_factory=list, max_length=20)
    seniorities: list[str] = Field(default_factory=list, max_length=20)
    buyer_roles: list[str] = Field(default_factory=list, max_length=20)
    locations: list[str] = Field(default_factory=list, max_length=20)
    email_status: Literal["any", "present", "verified", "missing"] = "any"
    phone_status: Literal["any", "present", "missing"] = "any"
    linkedin_status: Literal["any", "present", "missing"] = "any"
    min_actionable_score: float | None = Field(None, ge=0, le=100)
    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0, le=10000)


class NaturalLanguageSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    target: Literal["companies", "people", "auto"] = "auto"

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class SearchIntent(BaseModel):
    target: Literal["companies", "people"]
    company_filters: CompanySearchRequest | None = None
    people_filters: PeopleSearchRequest | None = None
    summary: str = Field(..., min_length=1, max_length=600)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    unresolved: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_target_payload(self):
        if self.target == "companies" and self.company_filters is None:
            raise ValueError("company_filters é obrigatório para busca de empresas")
        if self.target == "people" and self.people_filters is None:
            raise ValueError("people_filters é obrigatório para busca de pessoas")
        return self
