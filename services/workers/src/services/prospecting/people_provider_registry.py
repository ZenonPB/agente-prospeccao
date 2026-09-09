"""Waterfall de providers de pessoas com estados observáveis.

O registry não habilita nenhum provider por conta própria. Providers reais são
registrados pelo orquestrador, que pode injetar credenciais, quota e telemetria.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence
import logging
import re
import unicodedata


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

        Returns:
            Dicionário com ``people``, tentativas, status agregado, indicação
            de early stopping e ``cost_spent`` (custo acumulado dos providers
            efetivamente consultados). O resultado é seguro para serialização
            JSON.
        """
        people: List[Dict[str, Any]] = []
        attempts: List[ProviderAttempt] = []
        cost_spent = 0.0
        providers = self._providers[: max_steps if max_steps is not None else None]
        if not providers:
            return self._result(people, attempts, "disabled", False, cost_spent)

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

            normalized = [item for item in raw_people if isinstance(item, dict)]
            before = len(people)
            people = _merge_people(people, normalized, provider.name)
            attempts.append(ProviderAttempt(provider.name, "success", len(people) - before))
            if _has_sufficient_contact(people, min_contact_confidence, require_verified_email):
                return self._result(people, attempts, "success", True, cost_spent)

        status = _aggregate_status(people, attempts)
        return self._result(people, attempts, status, False, cost_spent)

    @staticmethod
    def _result(
        people: List[Dict[str, Any]],
        attempts: List[ProviderAttempt],
        status: str,
        early_stopped: bool,
        cost_spent: float = 0.0,
    ) -> Dict[str, Any]:
        """Monta um payload consistente para todos os estados do waterfall."""
        return {
            "people": people,
            "status": status,
            "early_stopped": early_stopped,
            "providers_attempted": [attempt.provider for attempt in attempts],
            "attempts": [attempt.as_dict() for attempt in attempts],
            "cost_spent": cost_spent,
        }


def _has_sufficient_contact(
    people: Sequence[Dict[str, Any]],
    minimum: float,
    require_verified_email: bool,
) -> bool:
    """Verifica se ao menos uma pessoa atende ao critério de parada."""
    for person in people:
        confidence = _number(person.get("contact_confidence", person.get("confidence", 0)))
        verified = bool(person.get("email_verified", person.get("verified", False)))
        if confidence >= minimum and (not require_verified_email or verified):
            return True
    return False


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