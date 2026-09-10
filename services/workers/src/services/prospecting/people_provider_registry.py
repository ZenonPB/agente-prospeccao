"""Waterfall de providers de pessoas com estados observáveis.

O registry não habilita nenhum provider por conta própria. Providers reais são
registrados pelo orquestrador, que pode injetar credenciais, quota e telemetria.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence
import logging
import re
import unicodedata

from services.prospecting.buyer_persona import (
    normalize_buyer_roles,
    resolve_buyer_role,
)


logger = logging.getLogger(__name__)


class PeopleProvider(Protocol):
    """Contrato mínimo para uma fonte assíncrona de pessoas."""

    name: str
    cost: float

    async def search(self, domain: str, titles: Sequence[str]) -> List[Dict[str, Any]]:
        """Busca pessoas para um domínio e cargos-alvo."""


@dataclass(frozen=True)
class ProviderAttempt:
    """Resultado observável de uma tentativa de provider."""

    provider: str
    status: str
    result_count: int = 0
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """Serializa a tentativa para auditoria e telemetria."""
        result = {
            "provider": self.provider,
            "status": self.status,
            "result_count": self.result_count,
        }
        if self.error:
            result["error"] = self.error
        return result


class PeopleProviderRegistry:
    """Executa providers em ordem de custo até atingir critérios de parada."""

    def __init__(self, providers: Optional[Sequence[PeopleProvider]] = None) -> None:
        self._providers: List[PeopleProvider] = []
        for provider in providers or ():
            self.register(provider)

    def register(self, provider: PeopleProvider) -> None:
        """Registra ou substitui um provider pelo nome."""
        if not getattr(provider, "name", None):
            raise ValueError("provider precisa declarar name")
        self._providers = [p for p in self._providers if p.name != provider.name]
        self._providers.append(provider)
        self._providers.sort(key=lambda item: float(getattr(item, "cost", 0)))

    def list_providers(self) -> List[str]:
        """Retorna os providers registrados na ordem de custo."""
        return [provider.name for provider in self._providers]

    async def waterfall_search(
        self,
        domain: str,
        titles: Sequence[str],
        *,
        min_contact_confidence: float = 70,
        require_verified_email: bool = False,
        max_steps: Optional[int] = None,
        max_cost: Optional[float] = None,
        min_role_fit: Optional[float] = None,
        min_identity_confidence: Optional[float] = None,
        required_buyer_role: Optional[Any] = None,
        seniority: Optional[Sequence[str]] = None,
        department: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Busca pessoas em cascata sem tratar falha como lista vazia.

        Args:
            domain: Domínio normalizado da empresa.
            titles: Cargos ou títulos aceitos pelo perfil da oferta.
            min_contact_confidence: Confiança mínima para early stopping.
            require_verified_email: Exige email explicitamente verificado.
            max_steps: Quantidade máxima de providers a consultar.
            max_cost: Custo máximo acumulado; providers que excederem o
                orçamento restante ficam bloqueados com status
                ``budget_exceeded`` (nunca consultados).
            min_role_fit: Pontuação mínima de aderência ao cargo-alvo para
                early stopping. Quando ausente, o comportamento legado é
                mantido e o fit é apenas anotado nos candidatos.
            min_identity_confidence: Confiança mínima de identidade para
                early stopping. Quando ausente, o comportamento legado é
                mantido (só contato/role param a cascata). Providers que
                não informam ``identity_confidence`` contam como zero.
            required_buyer_role: Papel de compra exigido para early
                stopping (ex.: ``"TECHNICAL_BUYER"`` ou lista). Quando
                ausente, o buyer role é só anotado nos candidatos.
            seniority: Senioridades aceitas para early stopping
                (ex.: ``["senior"]``). Quando ausente, não filtra.
            department: Departamentos aceitos para early stopping
                (ex.: ``["engineering"]``). Quando ausente, não filtra.

        Returns:
            Dicionário com ``people``, tentativas, status agregado, indicação
            de early stopping, ``cost_spent`` (custo acumulado dos providers
            efetivamente consultados) e resumo ``role_fit``. O resultado é
            seguro para serialização JSON.
        """
        people: List[Dict[str, Any]] = []
        attempts: List[ProviderAttempt] = []
        cost_spent = 0.0
        seniorities = _normalize_filter_values(seniority)
        departments = _normalize_filter_values(department)
        buyer_roles = normalize_buyer_roles(required_buyer_role)
        providers = self._providers[: max_steps if max_steps is not None else None]
        if not providers:
            return self._result(
                people, attempts, "disabled", False, cost_spent,
                seniorities, departments, buyer_roles,
            )

        for provider in providers:
            provider_cost = float(getattr(provider, "cost", 0))
            if max_cost is not None and cost_spent + provider_cost > max_cost:
                attempts.append(ProviderAttempt(
                    provider.name, "budget_exceeded", error="max_cost_reached",
                ))
                continue
            try:
                raw_people = await provider.search(domain, list(titles))
            except Exception as exc:  # provider boundary: preserve failure state
                logger.warning("People provider %s falhou: %s", provider.name, exc)
                attempts.append(ProviderAttempt(
                    provider.name,
                    getattr(exc, "status", "failed"),
                    error=str(exc),
                ))
                continue
            # Custo é cobrado só quando a chamada produziu resposta (success
            # ou empty), coerente com a cobrança de quota dos providers.
            cost_spent += provider_cost
            if raw_people is None:
                attempts.append(ProviderAttempt(provider.name, "failed", error="provider_returned_none"))
                continue
            if not isinstance(raw_people, list):
                attempts.append(ProviderAttempt(provider.name, "failed", error="provider_returned_invalid_payload"))
                continue
            if not raw_people:
                attempts.append(ProviderAttempt(provider.name, "empty"))
                continue

            normalized = [
                _with_buyer_role(
                    _with_role_filters(_with_role_fit(item, titles), seniorities, departments),
                    buyer_roles,
                )
                for item in raw_people
                if isinstance(item, dict)
            ]
            before = len(people)
            people = _merge_people(people, normalized, provider.name)
            attempts.append(ProviderAttempt(provider.name, "success", len(people) - before))
            if _has_sufficient_contact(
                people,
                min_contact_confidence,
                require_verified_email,
                min_role_fit,
                seniorities,
                departments,
                min_identity_confidence,
                buyer_roles,
            ):
                return self._result(
                    people, attempts, "success", True, cost_spent,
                    seniorities, departments, buyer_roles,
                )

        status = _aggregate_status(people, attempts)
        if (
            (min_role_fit is not None or seniorities or departments)
            and people
            and not any(
                _matches_role_requirements(person, min_role_fit, seniorities, departments)
                for person in people
            )
        ):
            status = "role_not_matched"
        if (
            buyer_roles
            and people
            and not any(_matches_buyer_role(person, buyer_roles) for person in people)
        ):
            status = "buyer_role_not_matched"
        return self._result(
            people, attempts, status, False, cost_spent,
            seniorities, departments, buyer_roles,
        )

    @staticmethod
    def _result(
        people: List[Dict[str, Any]],
        attempts: List[ProviderAttempt],
        status: str,
        early_stopped: bool,
        cost_spent: float = 0.0,
        seniorities: Sequence[str] = (),
        departments: Sequence[str] = (),
        buyer_roles: Sequence[str] = (),
    ) -> Dict[str, Any]:
        """Monta um payload consistente para todos os estados do waterfall."""
        return {
            "people": people,
            "status": status,
            "early_stopped": early_stopped,
            "providers_attempted": [attempt.provider for attempt in attempts],
            "attempts": [attempt.as_dict() for attempt in attempts],
            "cost_spent": cost_spent,
            "role_fit": {
                "matched": sum(
                    1 for person in people if person.get("role_fit_status") == "matched"
                ),
                "not_matched": sum(
                    1 for person in people if person.get("role_fit_status") == "not_matched"
                ),
                "unknown": sum(
                    1 for person in people if person.get("role_fit_status") == "unknown"
                ),
            },
            "role_filters": {
                "seniority": list(seniorities),
                "department": list(departments),
                "requested": bool(seniorities or departments),
                "matched": sum(
                    1 for person in people
                    if person.get("role_filter_status") == "matched"
                ),
                "not_matched": sum(
                    1 for person in people
                    if person.get("role_filter_status") == "not_matched"
                ),
            },
            "buyer_role": {
                "required": list(buyer_roles),
                "requested": bool(buyer_roles),
                "matched": sum(
                    1 for person in people
                    if person.get("buyer_role_status") == "matched"
                ),
                "not_matched": sum(
                    1 for person in people
                    if person.get("buyer_role_status") == "not_matched"
                ),
            },
        }


def _has_sufficient_contact(
    people: Sequence[Dict[str, Any]],
    minimum: float,
    require_verified_email: bool,
    min_role_fit: Optional[float] = None,
    seniorities: Sequence[str] = (),
    departments: Sequence[str] = (),
    min_identity_confidence: Optional[float] = None,
    buyer_roles: Sequence[str] = (),
) -> bool:
    """Verifica se ao menos uma pessoa atende ao critério de parada."""
    for person in people:
        confidence = _number(person.get("contact_confidence", person.get("confidence", 0)))
        verified = bool(person.get("email_verified", person.get("verified", False)))
        role_ok = _matches_role_requirements(person, min_role_fit, seniorities, departments)
        identity_ok = (
            min_identity_confidence is None
            or _number(person.get("identity_confidence", 0)) >= min_identity_confidence
        )
        buyer_ok = _matches_buyer_role(person, buyer_roles)
        if confidence >= minimum and (not require_verified_email or verified) and role_ok and identity_ok and buyer_ok:
            return True
    return False


def _matches_role_requirements(
    person: Dict[str, Any],
    min_role_fit: Optional[float],
    seniorities: Sequence[str],
    departments: Sequence[str],
) -> bool:
    """Confirma score mínimo, senioridade e departamento quando exigidos."""
    if min_role_fit is not None and _number(person.get("role_fit_score", 0)) < min_role_fit:
        return False
    if seniorities and str(person.get("role_seniority") or "").lower() not in seniorities:
        return False
    if departments and str(person.get("role_department") or "").lower() not in departments:
        return False
    return True


def _matches_buyer_role(person: Dict[str, Any], buyer_roles: Sequence[str]) -> bool:
    """Confirma buyer role exigido; sem exigência, qualquer candidato passa."""
    if not buyer_roles:
        return True
    return str(person.get("buyer_role") or "").upper() in {str(r).upper() for r in buyer_roles}


def _with_buyer_role(person: Dict[str, Any], buyer_roles: Sequence[str]) -> Dict[str, Any]:
    """Anota buyer role (explícito > inferido) sem remover o candidato."""
    result = dict(person)
    resolved = resolve_buyer_role(person)
    result["buyer_role"] = resolved["buyer_role"]
    result["buyer_role_source"] = resolved["buyer_role_source"]
    result["buyer_role_status"] = (
        "not_requested"
        if not buyer_roles
        else "matched"
        if _matches_buyer_role(result, buyer_roles)
        else "not_matched"
    )
    return result


def _with_role_fit(person: Dict[str, Any], titles: Sequence[str]) -> Dict[str, Any]:
    """Anota aderência do cargo sem substituir o dado original do provider."""
    result = dict(person)
    candidate_role = (
        person.get("role")
        or person.get("role_label")
        or person.get("title")
        or person.get("job_title")
    )
    score, matched_titles = _role_fit(candidate_role, titles)
    result["role_fit_score"] = score
    result["role_fit_status"] = (
        "matched" if score >= 70 else "not_matched" if candidate_role else "unknown"
    )
    result["matched_titles"] = matched_titles
    result["role_seniority"], result["role_department"] = _classify_role(candidate_role)
    return result


def _with_role_filters(
    person: Dict[str, Any],
    seniorities: Sequence[str],
    departments: Sequence[str],
) -> Dict[str, Any]:
    """Anota o resultado dos filtros configuráveis sem remover o candidato."""
    result = dict(person)
    result["role_filter_status"] = (
        "not_requested"
        if not (seniorities or departments)
        else "matched"
        if _matches_role_requirements(person, None, seniorities, departments)
        else "not_matched"
    )
    return result


def _role_fit(role: Any, titles: Sequence[str]) -> tuple[float, List[str]]:
    """Calcula fit determinístico por igualdade e sobreposição de tokens."""
    candidate = _normalize_role(role)
    targets = [str(title) for title in titles if _normalize_role(title)]
    if not candidate or not targets:
        return 0.0, []
    candidate_tokens = set(candidate.split())
    best_score = 0.0
    matched: List[str] = []
    for title in targets:
        normalized_title = _normalize_role(title)
        title_tokens = set(normalized_title.split())
        if candidate == normalized_title:
            score = 100.0
        else:
            overlap = len(candidate_tokens & title_tokens)
            score = round(100 * overlap / len(title_tokens), 1) if title_tokens else 0.0
        if score > best_score:
            best_score = score
            matched = [title] if score >= 70 else []
        elif score >= 70 and score == best_score and title not in matched:
            matched.append(title)
    return best_score, matched


def _normalize_filter_values(values: Any) -> List[str]:
    """Normaliza filtros opcionais como lista em minúsculas e sem duplicatas."""
    if isinstance(values, str):
        values = [values]
    normalized = []
    for value in values or ():
        text = _normalize_role(value)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _classify_role(role: Any) -> tuple[str, str]:
    """Classifica senioridade e departamento com regras determinísticas."""
    tokens = set(_normalize_role(role).split())
    seniority = "unknown" if not tokens else "staff"
    for level in ("c_level", "executive", "senior", "lead", "junior", "intern"):
        if _SENIORITY_TOKENS[level] & tokens:
            seniority = level
            break
    department = "other" if tokens else "unknown"
    if tokens:
        for area, keywords in _DEPARTMENT_TOKENS.items():
            if keywords & tokens:
                department = area
                break
    return seniority, department


_SENIORITY_TOKENS = {
    "c_level": {"ceo", "cfo", "cto", "cio", "coo", "cmo", "chief", "presidente", "president"},
    "executive": {"director", "diretor", "diretora", "vp", "vice", "owner", "founder", "socio"},
    "senior": {"senior", "sr", "head"},
    "lead": {"lead", "techlead", "coordinator", "coordenador", "supervisor", "gerente", "manager"},
    "junior": {"junior", "jr", "estagiario", "intern", "trainee", "assistente", "assistant"},
    "intern": {"estagio"},
}
_DEPARTMENT_TOKENS = {
    "engineering": {
        "engineer", "engenheiro", "engenharia", "engineering", "plant", "maintenance",
        "technical", "tecnico", "developer", "designer", "safety", "operations",
    },
    "sales": {"sales", "vendas", "comercial", "account", "sdr", "bdr"},
    "marketing": {"marketing", "growth", "brand", "product"},
    "finance": {"finance", "financas", "financeiro", "accounting", "controller"},
    "hr": {"hr", "rh", "people", "talent", "recruiter"},
    "legal": {"legal", "juridico", "compliance"},
    "it": {"it", "ti", "infra", "devops", "security", "data"},
}


def _normalize_role(value: Any) -> str:
    """Normaliza cargo para comparação semântica conservadora."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def _aggregate_status(people: Sequence[Dict[str, Any]], attempts: Sequence[ProviderAttempt]) -> str:
    """Consolida o resultado sem ocultar bloqueios ou falhas do provider."""
    if people:
        return "success"
    if not attempts:
        return "disabled"
    statuses = {attempt.status for attempt in attempts}
    if statuses == {"disabled"}:
        return "disabled"
    if "quota_exceeded" in statuses:
        return "quota_exceeded"
    if statuses == {"budget_exceeded"} or statuses.issubset({"budget_exceeded", "empty"}):
        return "budget_exceeded"
    if statuses == {"failed"} or statuses.issubset({"failed", "configuration_error"}):
        return "failed"
    return "empty"


def _merge_people(
    current: Sequence[Dict[str, Any]],
    incoming: Sequence[Dict[str, Any]],
    provider_name: str,
) -> List[Dict[str, Any]]:
    """Deduplica por identificador forte e preserva a melhor evidência."""
    merged = [dict(item) for item in current]
    indexes = {_identity_key(item): index for index, item in enumerate(merged)}
    for item in incoming:
        candidate = dict(item)
        candidate.setdefault("source", provider_name)
        key = _identity_key(candidate)
        if key in indexes:
            index = indexes[key]
            merged[index] = _combine(merged[index], candidate)
        else:
            indexes[key] = len(merged)
            merged.append(candidate)
    return merged


def _combine(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Combina duas evidências sem apagar dados já encontrados."""
    result = dict(existing)
    for key, value in incoming.items():
        if value not in (None, "", False) and result.get(key) in (None, "", False):
            result[key] = value
    sources = list(dict.fromkeys(_as_sources(existing) + _as_sources(incoming)))
    if sources:
        result["sources"] = sources
    result["confidence"] = max(
        _number(existing.get("confidence", existing.get("contact_confidence", 0))),
        _number(incoming.get("confidence", incoming.get("contact_confidence", 0))),
    )
    result["identity_confidence"] = max(
        _number(existing.get("identity_confidence", 0)),
        _number(incoming.get("identity_confidence", 0)),
    )
    existing_fit = _number(existing.get("role_fit_score", 0))
    incoming_fit = _number(incoming.get("role_fit_score", 0))
    if incoming_fit > existing_fit:
        result["role_fit_score"] = incoming_fit
        result["role_fit_status"] = incoming.get("role_fit_status", "unknown")
    result["matched_titles"] = list(dict.fromkeys([
        *(existing.get("matched_titles") or []),
        *(incoming.get("matched_titles") or []),
    ]))
    return result


def _identity_key(person: Dict[str, Any]) -> str:
    """Obtém uma chave forte ou uma chave conservadora para deduplicação."""
    for field in ("email", "linkedin_url", "external_id"):
        value = str(person.get(field) or "").strip().lower()
        if value:
            return f"{field}:{value}"
    name = _normalize_text(person.get("name"))
    role = _normalize_text(person.get("role") or person.get("title"))
    return f"name:{name}|role:{role}" if name else f"anonymous:{id(person)}"


def _as_sources(person: Dict[str, Any]) -> List[str]:
    """Normaliza provenance singular ou múltipla."""
    value = person.get("sources", person.get("source"))
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)] if value else []


def _normalize_text(value: Any) -> str:
    """Normaliza texto apenas para comparação de identidade."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().lower()


def _number(value: Any) -> float:
    """Converte confiança externa inválida para zero."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0