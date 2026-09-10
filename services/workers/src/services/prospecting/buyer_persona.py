"""BuyerPersona — vocabulário de papéis de compra (Fase 2 do roadmap).

Seam puro: inferência determinística de ``buyer_role`` a partir do cargo,
sem chamar provider e sem inventar decisor. Valor explícito informado pelo
provider (``buyer_role``/``buyer_type``/``qsa_buyer_type``) sempre prevalece
sobre a inferência; sem cargo, o resultado é ``UNKNOWN`` (nunca um papel
inventado).
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

KNOWN_BUYER_ROLES = frozenset({
    "ECONOMIC_BUYER", "TECHNICAL_BUYER", "CHAMPION", "END_USER", "INFLUENCER",
})

_TECHNICAL_TOKENS = frozenset({
    "procurement", "operations", "plant", "maintenance", "engineer",
    "engenheiro", "engenharia", "engineering", "technical", "tecnico",
    "automation", "production", "producao", "industrial", "operacoes",
})

_ECONOMIC_TOKENS = frozenset({
    "ceo", "founder", "director", "diretor", "diretora", "president",
    "presidente", "owner", "socio", "partner", "cfo", "cto", "coo", "cmo",
    "chief",
})


def infer_buyer_role(role: Any) -> str:
    """Infere o buyer role de um cargo com regras determinísticas.

    Precedência (igual ao pipeline de decisores): marcadores técnicos
    primeiro, depois econômicos; demais cargos são ``CHAMPION``.
    Sem cargo, retorna ``UNKNOWN``.
    """
    tokens = set(_normalize(role).split())
    if not tokens:
        return "UNKNOWN"
    if tokens & _TECHNICAL_TOKENS:
        return "TECHNICAL_BUYER"
    if tokens & _ECONOMIC_TOKENS:
        return "ECONOMIC_BUYER"
    return "CHAMPION"


def explicit_buyer_role(person: Dict[str, Any]) -> Optional[str]:
    """Extrai buyer role explícito do candidato, se o provider informou."""
    for field in ("buyer_role", "buyer_type", "qsa_buyer_type"):
        value = person.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def resolve_buyer_role(person: Dict[str, Any]) -> Dict[str, str]:
    """Resolve buyer role com fonte rastreável (explícito > inferido)."""
    explicit = explicit_buyer_role(person)
    if explicit:
        return {"buyer_role": explicit, "buyer_role_source": "explicit"}
    role = (
        person.get("role")
        or person.get("role_label")
        or person.get("title")
        or person.get("job_title")
    )
    inferred = infer_buyer_role(role)
    return {
        "buyer_role": inferred,
        "buyer_role_source": "inferred" if inferred != "UNKNOWN" else "unknown",
    }


def normalize_buyer_roles(value: Any) -> List[str]:
    """Normaliza papel exigido (str ou lista) para UPPER sem duplicatas."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    normalized: List[str] = []
    for item in value:
        text = str(item or "").strip().upper()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize(value: Any) -> str:
    """Normaliza cargo para comparação (minúsculas, sem acento)."""
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


@dataclass(frozen=True)
class BuyerPersona:
    """Persona de compra: quem decide cada oferta AlphaMec.

    `title_patterns` são cargos que identificam a persona; `seniority` e
    `department` usam o vocabulário do classificador de cargos do waterfall;
    `preferred_channels` usa o vocabulário de canais do OfferProfile.
    """

    key: str
    title_patterns: List[str] = field(default_factory=list)
    seniority: str = "staff"
    department: str = "other"
    buyer_type: str = "CHAMPION"
    priority: int = 99
    preferred_channels: List[str] = field(default_factory=list)


BUYER_PERSONAS: Dict[str, BuyerPersona] = {
    persona.key: persona
    for persona in [
        BuyerPersona(
            key="founder",
            title_patterns=["founder", "socio fundador", "ceo", "presidente"],
            seniority="executive",
            department="other",
            buyer_type="ECONOMIC_BUYER",
            priority=1,
            preferred_channels=["email", "phone", "linkedin"],
        ),
        BuyerPersona(
            key="marketing_manager",
            title_patterns=["marketing manager", "gerente de marketing", "product manager"],
            seniority="lead",
            department="marketing",
            buyer_type="CHAMPION",
            priority=2,
            preferred_channels=["email", "instagram", "linkedin"],
        ),
        BuyerPersona(
            key="operations_director",
            title_patterns=["operations director", "diretor de operacoes", "coo"],
            seniority="executive",
            department="engineering",
            buyer_type="TECHNICAL_BUYER",
            priority=3,
            preferred_channels=["email", "phone"],
        ),
        BuyerPersona(
            key="engineering_manager",
            title_patterns=["engineering manager", "gerente de engenharia", "plant engineer"],
            seniority="lead",
            department="engineering",
            buyer_type="TECHNICAL_BUYER",
            priority=4,
            preferred_channels=["email", "phone", "linkedin"],
        ),
        BuyerPersona(
            key="maintenance_manager",
            title_patterns=["maintenance manager", "gerente de manutencao", "maintenance"],
            seniority="lead",
            department="engineering",
            buyer_type="TECHNICAL_BUYER",
            priority=5,
            preferred_channels=["phone", "email", "whatsapp"],
        ),
        BuyerPersona(
            key="safety_manager",
            title_patterns=["safety manager", "tecnico de seguranca", "safety"],
            seniority="lead",
            department="engineering",
            buyer_type="TECHNICAL_BUYER",
            priority=6,
            preferred_channels=["email", "phone"],
        ),
        BuyerPersona(
            key="event_director",
            title_patterns=["event director", "diretor de eventos", "event manager"],
            seniority="executive",
            department="marketing",
            buyer_type="ECONOMIC_BUYER",
            priority=7,
            preferred_channels=["email", "instagram", "phone"],
        ),
        BuyerPersona(
            key="procurement",
            title_patterns=["procurement", "compras", "purchasing"],
            seniority="staff",
            department="other",
            buyer_type="TECHNICAL_BUYER",
            priority=8,
            preferred_channels=["email", "phone"],
        ),
    ]
}


def get_persona(key: Any) -> Optional[BuyerPersona]:
    """Retorna a persona pela chave, ou None quando desconhecida."""
    return BUYER_PERSONAS.get(str(key or "").strip().lower())


def list_personas() -> List[BuyerPersona]:
    """Lista as personas em ordem de prioridade."""
    return sorted(BUYER_PERSONAS.values(), key=lambda persona: persona.priority)


def match_persona_for_role(role: Any) -> Optional[str]:
    """Identifica a persona de um cargo por sobreposição de tokens.

    Retorna a chave da primeira persona (por prioridade) cujo padrão
    aparece no cargo, ou None quando nenhum padrão casa.
    """
    tokens = set(_normalize(role).split())
    if not tokens:
        return None
    for persona in list_personas():
        for pattern in persona.title_patterns:
            pattern_tokens = set(_normalize(pattern).split())
            if pattern_tokens and pattern_tokens <= tokens:
                return persona.key
    return None


def required_buyer_role_for_profile(profile: Any) -> List[str]:
    """Extrai os buyer types do OfferProfile como gate exigido.

    Lê `decision_makers.buyer_types` (vocabulário validado em P1.4).
    Perfil sem buyer types não exige gate (lista vazia = neutro).
    """
    decision_makers = (
        profile.get("decision_makers", {}) if isinstance(profile, dict) else {}
    )
    if not isinstance(decision_makers, dict):
        return []
    return normalize_buyer_roles(decision_makers.get("buyer_types"))
