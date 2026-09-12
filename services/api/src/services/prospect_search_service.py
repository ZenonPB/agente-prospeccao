"""Busca local, tenant-aware e sem efeitos colaterais sobre dados canônicos.

A busca consulta somente dados já conhecidos pela organização. Filtros que
podem ser avaliados com segurança no PostgreSQL são aplicados antes do limite
de candidatos; critérios derivados continuam usando lógica ternária em memória.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.db.models import Company, CompanyRecord, Enrichment, Lead, LeadOpportunityRow, Person
from src.schemas.search import (
    CompanySearchRequest,
    FilterCondition,
    FilterExpression,
    FilterOperator,
    PeopleSearchRequest,
    SearchTruth,
)
from services.prospecting.actionable_contact_score import calculate_actionable_contact_score
from services.prospecting.buyer_persona import match_persona_for_role, resolve_buyer_role


MAX_CANDIDATES = 2000
_ALLOWED_COMPANY_FIELDS = {
    "name", "company_name", "domain", "location", "city", "state", "country",
    "industry", "category", "cnae", "size", "employees", "revenue", "age",
    "technology", "technologies", "signal", "signals", "intent", "keyword",
    "keywords",
}


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _as_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _flatten_strings(value: Any) -> list[str]:
    out: list[str] = []
    if value is None:
        return out
    if isinstance(value, Mapping):
        for key, item in value.items():
            out.extend(_flatten_strings(key))
            out.extend(_flatten_strings(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            out.extend(_flatten_strings(item))
    else:
        text = _normalized(value)
        if text:
            out.append(text)
    return out


def _first_number(sources: Iterable[Mapping[str, Any]], keys: Iterable[str]) -> float | None:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _condition_value(document: Mapping[str, Any], field: str) -> Any:
    aliases = {
        "name": "company_name",
        "domain": "normalized_domain",
        "industry": "category",
        "technology": "technologies",
        "signal": "signals",
        "keyword": "keywords",
    }
    return document.get(aliases.get(field, field))


def evaluate_condition(document: Mapping[str, Any], condition: FilterCondition) -> SearchTruth:
    """Avalia uma condição com semântica MATCH/NO_MATCH/UNKNOWN."""
    if condition.field not in _ALLOWED_COMPANY_FIELDS:
        raise ValueError(f"campo de busca não permitido: {condition.field}")
    actual = _condition_value(document, condition.field)
    operator = condition.operator

    if operator == FilterOperator.EXISTS:
        expected = True if condition.value is None else bool(condition.value)
        exists = actual is not None and actual != "" and actual != []
        return SearchTruth.MATCH if exists == expected else SearchTruth.NO_MATCH

    if actual is None or actual == []:
        return SearchTruth.UNKNOWN

    requested = condition.value
    actual_values = _as_values(actual)
    requested_values = _as_values(requested)

    if operator == FilterOperator.EQ:
        target = _normalized(requested)
        return SearchTruth.MATCH if any(_normalized(item) == target for item in actual_values) else SearchTruth.NO_MATCH
    if operator == FilterOperator.CONTAINS:
        target = _normalized(requested)
        return SearchTruth.MATCH if target and any(target in _normalized(item) for item in actual_values) else SearchTruth.NO_MATCH
    if operator == FilterOperator.IN:
        targets = {_normalized(item) for item in requested_values}
        return SearchTruth.MATCH if any(_normalized(item) in targets for item in actual_values) else SearchTruth.NO_MATCH

    try:
        number = float(actual_values[0])
    except (TypeError, ValueError, IndexError):
        return SearchTruth.UNKNOWN

    if operator == FilterOperator.GTE:
        return SearchTruth.MATCH if number >= float(requested) else SearchTruth.NO_MATCH
    if operator == FilterOperator.LTE:
        return SearchTruth.MATCH if number <= float(requested) else SearchTruth.NO_MATCH
    if operator == FilterOperator.BETWEEN:
        if len(requested_values) != 2:
            raise ValueError("BETWEEN exige [mínimo, máximo]")
        low, high = float(requested_values[0]), float(requested_values[1])
        return SearchTruth.MATCH if low <= number <= high else SearchTruth.NO_MATCH
    raise ValueError(f"operador não suportado: {operator}")


def evaluate_expression(
    document: Mapping[str, Any],
    expression: FilterExpression,
    *,
    depth: int = 0,
) -> SearchTruth:
    """Avalia grupos AND/OR/NOT preservando UNKNOWN por lógica de Kleene."""
    if depth > 3:
        raise ValueError("expressão excede profundidade máxima de 3 níveis")
    results = [evaluate_condition(document, item) for item in expression.conditions]
    results.extend(evaluate_expression(document, group, depth=depth + 1) for group in expression.groups)

    if expression.operator == "NOT":
        value = results[0]
        if value == SearchTruth.UNKNOWN:
            return value
        return SearchTruth.NO_MATCH if value == SearchTruth.MATCH else SearchTruth.MATCH
    if expression.operator == "AND":
        if SearchTruth.NO_MATCH in results:
            return SearchTruth.NO_MATCH
        return SearchTruth.UNKNOWN if SearchTruth.UNKNOWN in results else SearchTruth.MATCH
    if SearchTruth.MATCH in results:
        return SearchTruth.MATCH
    return SearchTruth.UNKNOWN if SearchTruth.UNKNOWN in results else SearchTruth.NO_MATCH


def _combine_truth(values: Iterable[SearchTruth]) -> SearchTruth:
    items = list(values)
    if SearchTruth.NO_MATCH in items:
        return SearchTruth.NO_MATCH
    if SearchTruth.UNKNOWN in items:
        return SearchTruth.UNKNOWN
    return SearchTruth.MATCH


def _contains_any(haystack: Any, needles: Iterable[str]) -> SearchTruth:
    normalized_needles = [_normalized(item) for item in needles if _normalized(item)]
    if not normalized_needles:
        return SearchTruth.MATCH
    values = _flatten_strings(haystack)
    if not values:
        return SearchTruth.UNKNOWN
    return SearchTruth.MATCH if any(any(needle in value for value in values) for needle in normalized_needles) else SearchTruth.NO_MATCH


def _contains_all(haystack: Any, needles: Iterable[str]) -> SearchTruth:
    normalized_needles = [_normalized(item) for item in needles if _normalized(item)]
    if not normalized_needles:
        return SearchTruth.MATCH
    values = _flatten_strings(haystack)
    if not values:
        return SearchTruth.UNKNOWN
    return SearchTruth.MATCH if all(any(needle in value for value in values) for needle in normalized_needles) else SearchTruth.NO_MATCH


def _range_truth(value: Any, minimum: Any, maximum: Any) -> SearchTruth:
    if minimum is None and maximum is None:
        return SearchTruth.MATCH
    if value is None:
        return SearchTruth.UNKNOWN
    try:
        number = float(value)
    except (TypeError, ValueError):
        return SearchTruth.UNKNOWN
    if minimum is not None and number < float(minimum):
        return SearchTruth.NO_MATCH
    if maximum is not None and number > float(maximum):
        return SearchTruth.NO_MATCH
    return SearchTruth.MATCH


def _like_pattern(value: str) -> str:
    """Escapa curingas SQL para busca literal por substring."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _contains_clause(column: Any, values: Iterable[str]):
    clauses = [column.ilike(_like_pattern(value.strip()), escape="\\") for value in values if value.strip()]
    return or_(*clauses) if clauses else None


class ProspectSearchService:
    def __init__(self, db: Session, organization_id: Any) -> None:
        self.db = db
        self.organization_id = organization_id

    def _company_documents(self, request: CompanySearchRequest) -> tuple[list[dict[str, Any]], bool]:
        query = self.db.query(Company).filter(Company.organization_id == self.organization_id)

        if request.locations:
            location_clauses = []
            for value in request.locations:
                pattern = _like_pattern(value.strip())
                if value.strip():
                    location_clauses.append(or_(
                        Company.city.ilike(pattern, escape="\\"),
                        Company.state.ilike(pattern, escape="\\"),
                        Company.country.ilike(pattern, escape="\\"),
                    ))
            if location_clauses:
                known = or_(*location_clauses)
                if request.include_unknown:
                    known = or_(known, and_(Company.city.is_(None), Company.state.is_(None), Company.country.is_(None)))
                query = query.filter(known)

        if request.industries:
            known = _contains_clause(Company.category, request.industries)
            if known is not None:
                if request.include_unknown:
                    known = or_(known, Company.category.is_(None))
                query = query.filter(known)

        companies = (
            query
            .order_by(Company.created_at.desc())
            .limit(MAX_CANDIDATES + 1)
            .all()
        )
        truncated = len(companies) > MAX_CANDIDATES
        companies = companies[:MAX_CANDIDATES]
        ids = [company.id for company in companies]
        if not ids:
            return [], truncated

        leads = (
            self.db.query(Lead)
            .filter(Lead.organization_id == self.organization_id, Lead.company_id.in_(ids))
            .all()
        )
        leads_by_company: dict[Any, list[Any]] = defaultdict(list)
        for lead in leads:
            leads_by_company[lead.company_id].append(lead)
        lead_ids = [lead.id for lead in leads]

        records_by_lead: dict[Any, Any] = {}
        enrichments_by_lead: dict[Any, list[Any]] = defaultdict(list)
        opportunities_by_lead: dict[Any, list[Any]] = defaultdict(list)
        if lead_ids:
            for record in self.db.query(CompanyRecord).filter(CompanyRecord.lead_id.in_(lead_ids)).all():
                records_by_lead[record.lead_id] = record
            for enrichment in self.db.query(Enrichment).filter(Enrichment.lead_id.in_(lead_ids)).all():
                enrichments_by_lead[enrichment.lead_id].append(enrichment)
            for opportunity in self.db.query(LeadOpportunityRow).filter(
                LeadOpportunityRow.organization_id == self.organization_id,
                LeadOpportunityRow.lead_id.in_(lead_ids),
            ).all():
                opportunities_by_lead[opportunity.lead_id].append(opportunity)

        documents: list[dict[str, Any]] = []
        for company in companies:
            company_leads = leads_by_company.get(company.id, [])
            raw_sources: list[Mapping[str, Any]] = []
            technologies: list[str] = []
            signals: list[str] = []
            intents: list[str] = []
            cnaes: list[str] = []
            sizes: list[str] = []
            ages: list[float] = []
            for lead in company_leads:
                if isinstance(lead.evidence_score, Mapping):
                    raw_sources.append(lead.evidence_score)
                    signals.extend(_flatten_strings(lead.evidence_score.get("signals")))
                    intents.extend(_flatten_strings(lead.evidence_score.get("intent")))
                record = records_by_lead.get(lead.id)
                if record:
                    if record.cnae_principal:
                        cnaes.append(str(record.cnae_principal))
                    cnaes.extend(_flatten_strings(record.cnae_secundarios))
                    if record.porte:
                        sizes.append(str(record.porte))
                    if record.porte_label:
                        sizes.append(str(record.porte_label))
                    if record.idade_anos is not None:
                        ages.append(float(record.idade_anos))
                    if isinstance(record.raw_data, Mapping):
                        raw_sources.append(record.raw_data)
                for enrichment in enrichments_by_lead.get(lead.id, []):
                    if enrichment.cms:
                        technologies.append(str(enrichment.cms))
                    for payload in (enrichment.raw_technical_data, enrichment.raw_business_data):
                        if isinstance(payload, Mapping):
                            raw_sources.append(payload)
                            technologies.extend(_flatten_strings(payload.get("technologies") or payload.get("technology_stack")))
                            intents.extend(_flatten_strings(payload.get("intent") or payload.get("intent_signals")))
                for opportunity in opportunities_by_lead.get(lead.id, []):
                    signals.extend(_flatten_strings(opportunity.signals_matched))

            if isinstance(company.raw_data, Mapping):
                raw_sources.append(company.raw_data)
                technologies.extend(_flatten_strings(company.raw_data.get("technologies") or company.raw_data.get("technology_stack")))
                intents.extend(_flatten_strings(company.raw_data.get("intent") or company.raw_data.get("intent_signals")))

            employees = _first_number(raw_sources, ("employees", "employee_count", "employees_count", "funcionarios", "numero_funcionarios"))
            revenue = _first_number(raw_sources, ("annual_revenue", "revenue", "faturamento", "faturamento_anual"))
            age = max(ages) if ages else _first_number(raw_sources, ("age", "age_years", "idade_anos"))
            keywords = [
                company.company_name, company.name, company.category, company.city,
                company.state, company.country, company.normalized_domain, *cnaes,
                *technologies, *signals, *intents,
            ]
            documents.append({
                "id": str(company.id),
                "company_name": company.company_name,
                "name": company.name,
                "cnpj": company.cnpj,
                "website": company.website,
                "normalized_domain": company.normalized_domain,
                "phone": company.phone,
                "city": company.city,
                "state": company.state,
                "country": company.country,
                "location": " / ".join(part for part in (company.city, company.state, company.country) if part),
                "category": company.category,
                "cnae": list(dict.fromkeys(cnaes)),
                "size": list(dict.fromkeys(sizes)),
                "employees": employees,
                "revenue": revenue,
                "age": age,
                "technologies": list(dict.fromkeys(technologies)),
                "signals": list(dict.fromkeys(signals)),
                "intent": list(dict.fromkeys(intents)),
                "keywords": keywords,
                "linkedin_url": company.company_linkedin_url,
                "instagram_url": company.instagram_url,
                "google_rating": company.google_rating,
                "google_rating_count": company.google_rating_count,
                "lead_count": len(company_leads),
            })
        return documents, truncated

    def search_companies(self, request: CompanySearchRequest) -> dict[str, Any]:
        documents, truncated = self._company_documents(request)
        matches: list[dict[str, Any]] = []
        unknown_count = 0
        for document in documents:
            truths = [
                _contains_any(document.get("location"), request.locations),
                _contains_any(document.get("category"), request.industries),
                _contains_any(document.get("cnae"), request.cnaes),
                _contains_any(document.get("size"), request.sizes),
                _range_truth(document.get("employees"), request.employee_min, request.employee_max),
                _range_truth(document.get("revenue"), request.revenue_min, request.revenue_max),
                _range_truth(document.get("age"), request.age_min, request.age_max),
                _contains_all(document.get("technologies"), request.technologies),
                _contains_all(document.get("signals"), request.signals),
                _contains_all(document.get("intent"), request.intent),
                _contains_all(document.get("keywords"), request.keywords),
            ]
            if request.query:
                truths.append(_contains_any(document.get("keywords"), [request.query]))
            if request.exclusions:
                exclusion = _contains_any(document.get("keywords"), request.exclusions)
                truths.append(
                    SearchTruth.NO_MATCH if exclusion == SearchTruth.MATCH
                    else SearchTruth.MATCH if exclusion == SearchTruth.NO_MATCH
                    else SearchTruth.UNKNOWN
                )
            if request.expression:
                truths.append(evaluate_expression(document, request.expression))
            truth = _combine_truth(truths)
            if truth == SearchTruth.UNKNOWN:
                unknown_count += 1
            if truth == SearchTruth.MATCH or (request.include_unknown and truth == SearchTruth.UNKNOWN):
                item = {key: value for key, value in document.items() if key != "keywords"}
                item["match_state"] = truth.value
                matches.append(item)

        total = len(matches)
        page = matches[request.offset: request.offset + request.limit]
        return {
            "companies": page,
            "total": total,
            "unknown_count": unknown_count,
            "limit": request.limit,
            "offset": request.offset,
            "candidate_scan_truncated": truncated,
        }

    def search_people(self, request: PeopleSearchRequest) -> dict[str, Any]:
        person_query = self.db.query(Person).filter(Person.organization_id == self.organization_id)

        if request.email_status == "present":
            person_query = person_query.filter(Person.email.isnot(None), Person.email != "")
        elif request.email_status == "verified":
            person_query = person_query.filter(Person.email.isnot(None), Person.email != "", Person.email_verified.is_(True))
        elif request.email_status == "missing":
            person_query = person_query.filter(or_(Person.email.is_(None), Person.email == ""))

        if request.phone_status == "present":
            person_query = person_query.filter(Person.phone.isnot(None), Person.phone != "")
        elif request.phone_status == "missing":
            person_query = person_query.filter(or_(Person.phone.is_(None), Person.phone == ""))

        if request.linkedin_status == "present":
            person_query = person_query.filter(Person.linkedin_url.isnot(None), Person.linkedin_url != "")
        elif request.linkedin_status == "missing":
            person_query = person_query.filter(or_(Person.linkedin_url.is_(None), Person.linkedin_url == ""))

        company_ids: list[Any] | None = None
        if request.company or request.domain or request.locations:
            company_query = self.db.query(Company.id).filter(Company.organization_id == self.organization_id)
            if request.company:
                company_query = company_query.filter(Company.company_name.ilike(_like_pattern(request.company), escape="\\"))
            if request.domain:
                company_query = company_query.filter(Company.normalized_domain.ilike(_like_pattern(request.domain), escape="\\"))
            if request.locations:
                location_clauses = []
                for value in request.locations:
                    if not value.strip():
                        continue
                    pattern = _like_pattern(value.strip())
                    location_clauses.append(or_(
                        Company.city.ilike(pattern, escape="\\"),
                        Company.state.ilike(pattern, escape="\\"),
                        Company.country.ilike(pattern, escape="\\"),
                    ))
                if location_clauses:
                    company_query = company_query.filter(or_(*location_clauses))
            company_ids = [row[0] for row in company_query.limit(MAX_CANDIDATES + 1).all()]
            if not company_ids:
                return {
                    "people": [],
                    "total": 0,
                    "limit": request.limit,
                    "offset": request.offset,
                    "candidate_scan_truncated": False,
                }
            person_query = person_query.filter(Person.company_id.in_(company_ids[:MAX_CANDIDATES]))

        people = (
            person_query
            .order_by(Person.created_at.desc())
            .limit(MAX_CANDIDATES + 1)
            .all()
        )
        truncated = len(people) > MAX_CANDIDATES or bool(company_ids and len(company_ids) > MAX_CANDIDATES)
        people = people[:MAX_CANDIDATES]
        related_company_ids = list({person.company_id for person in people if person.company_id})
        companies = {}
        if related_company_ids:
            companies = {
                company.id: company
                for company in self.db.query(Company).filter(
                    Company.organization_id == self.organization_id,
                    Company.id.in_(related_company_ids),
                ).all()
            }

        results: list[dict[str, Any]] = []
        for person in people:
            company = companies.get(person.company_id)
            role = person.role_label or (person.role.value if person.role else None)
            raw_data = person.raw_data if isinstance(person.raw_data, Mapping) else {}
            seniority = _normalized(raw_data.get("role_seniority")) or None
            department = _normalized(raw_data.get("role_department")) or None
            buyer = resolve_buyer_role({
                "buyer_role": raw_data.get("buyer_role"),
                "buyer_type": raw_data.get("buyer_type"),
                "role_label": role,
            })
            location = " / ".join(
                part for part in (
                    getattr(company, "city", None), getattr(company, "state", None), getattr(company, "country", None)
                ) if part
            )
            searchable = [person.name, role, person.email, person.linkedin_url, getattr(company, "company_name", None), getattr(company, "normalized_domain", None), location]

            if request.query and _contains_any(searchable, [request.query]) != SearchTruth.MATCH:
                continue
            if request.company and _contains_any(getattr(company, "company_name", None), [request.company]) != SearchTruth.MATCH:
                continue
            if request.domain and _contains_any(getattr(company, "normalized_domain", None), [request.domain]) != SearchTruth.MATCH:
                continue
            if request.titles and _contains_any(role, request.titles) != SearchTruth.MATCH:
                continue
            if request.functions and _contains_any(department or role, request.functions) != SearchTruth.MATCH:
                continue
            if request.seniorities and _normalized(seniority) not in {_normalized(item) for item in request.seniorities}:
                continue
            if request.buyer_roles and buyer["buyer_role"].upper() not in {item.upper() for item in request.buyer_roles}:
                continue
            if request.locations and _contains_any(location, request.locations) != SearchTruth.MATCH:
                continue
            if request.email_status == "present" and not person.email:
                continue
            if request.email_status == "verified" and not (person.email and person.email_verified):
                continue
            if request.email_status == "missing" and person.email:
                continue
            if request.phone_status == "present" and not person.phone:
                continue
            if request.phone_status == "missing" and person.phone:
                continue
            if request.linkedin_status == "present" and not person.linkedin_url:
                continue
            if request.linkedin_status == "missing" and person.linkedin_url:
                continue

            actionable = calculate_actionable_contact_score(person, role_fit_score=raw_data.get("role_fit_score"))
            if request.min_actionable_score is not None and actionable["score"] < request.min_actionable_score:
                continue
            results.append({
                "id": str(person.id),
                "name": person.name,
                "role": role,
                "company": {
                    "id": str(company.id) if company else None,
                    "name": company.company_name if company else None,
                    "domain": company.normalized_domain if company else None,
                    "location": location or None,
                },
                "email": person.email,
                "email_verified": bool(person.email_verified),
                "phone": person.phone,
                "linkedin_url": person.linkedin_url,
                "identity_confidence": person.identity_confidence,
                "contact_confidence": person.contact_confidence,
                "verification_status": person.verification_status,
                "routability_type": person.routability_type,
                "buyer_role": buyer["buyer_role"],
                "buyer_role_source": buyer["buyer_role_source"],
                "persona": match_persona_for_role(role),
                "seniority": seniority,
                "department": department,
                "source": person.source,
                "actionable_contact": actionable,
            })

        results.sort(key=lambda item: item["actionable_contact"]["score"], reverse=True)
        total = len(results)
        return {
            "people": results[request.offset: request.offset + request.limit],
            "total": total,
            "limit": request.limit,
            "offset": request.offset,
            "candidate_scan_truncated": truncated,
        }
