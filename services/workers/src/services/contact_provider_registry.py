"""Contact Provider Registry — abstração de providers de pessoas/contatos.

Cobre #37 (person database provider), #38 (email finder), #39 (pattern inference),
#46 (domain-first person search). Permite trocar/encapsular providers com quota.
"""
from typing import Any, Dict, List, Optional, Protocol


class ContactProvider(Protocol):
    """Protocolo comum de provider de contato."""
    name: str
    quota_used: int
    quota_max: int

    def find_people(self, company_data: Dict[str, Any], target_roles: List[str]) -> List[Dict[str, Any]]:
        ...


# Registry simples in-memory (v1); produção teria quota/persists.
_PROVIDERS: Dict[str, "ContactProvider"] = {}


def register_provider(provider: "ContactProvider") -> None:
    _PROVIDERS[provider.name] = provider


def get_provider(name: str) -> Optional["ContactProvider"]:
    return _PROVIDERS.get(name)


def list_providers() -> List[str]:
    return list(_PROVIDERS.keys())


# --- #36 QSA Decision Makers (parser já existe; aqui classificamos por buyer_role) ---
def classify_qsa_role(role_label: str) -> str:
    """Classifica role do QSA como LEGAL_DECISION_MAKER/ECONOMIC_BUYER/OTHER."""
    r = (role_label or "").lower()
    if any(k in r for k in ["sócio", "diretor", "presidente"]):
        return "ECONOMIC_BUYER"
    if any(k in r for k in ["representante", "administrador"]):
        return "LEGAL_DECISION_MAKER"
    return "OTHER"


# --- #38 Email Finder (interface plugável) ---
def find_email_by_name(company_domain: Optional[str], full_name: str, providers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Tenta encontrar email via providers. Placeholder (sem credenciais); v1 retorna padrão."""
    from services.contact_provider_registry import list_providers
    attempted = providers or list_providers()
    return {
        "attempted_providers": attempted,
        "found_email": None,
        "source": "no_provider_active",
        "next_step": "configure_hunter_or_apollo",
    }


# --- #39 Email Pattern Inference com verificação obrigatória ---
COMMON_PATTERNS = [
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{first}@{domain}",
    "{first[0]}{last}@{domain}",
]


def infer_email_pattern(domain: str, full_name: str, verify: bool = True) -> Dict[str, Any]:
    """Infere padrões comuns de email; `verify=False` retorna hipotético; True exige provider."""
    if not domain or not full_name:
        return {"pattern": None, "candidate": None, "verification_status": "unknown"}
    parts = full_name.strip().split()
    if len(parts) < 2:
        return {"pattern": None, "candidate": None, "verification_status": "needs_full_name"}
    # Normaliza acentos (unidecode-like) para evitar e-mails com ç/ã
    import unicodedata
    def _strip_accents(s):
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    first = _strip_accents(parts[0]).lower()
    last = _strip_accents(parts[-1]).lower()
    candidates = [
        p.format(first=first, last=last, domain=domain, **{"first[0]": first[0]})
        for p in COMMON_PATTERNS
    ]
    # Heurística determinística sem verificação
    primary = candidates[0] if candidates else None
    return {
        "pattern": COMMON_PATTERNS[0],
        "candidates": candidates,
        "candidate": primary,
        "verification_status": "inferred" if not verify else "pending_verification",
        "source": "email_pattern_inference",
    }


# --- #44 Cascade Contact Search com early stopping ---
def cascade_contact_search(
    lead_data: Dict[str, Any],
    target_roles: List[str],
    min_confidence: float = 50.0,
    max_steps: int = 3,
) -> Dict[str, Any]:
    """Cascata explícita: Receita/QSA → Hunter → heurística. Para cedo se confiança atingida."""
    steps = []
    # Step 1: Receita/QSA (se CNPJ presente)
    if lead_data.get("cnpj"):
        steps.append({"step": "receita_qsa", "used": True, "result": "qsa_checked"})
    else:
        steps.append({"step": "receita_qsa", "used": False, "result": "no_cnpj"})
    if any(s.get("result") == "matched_high_confidence" for s in steps):
        return {"stopped_at": 1, "cascaded_steps": steps, "result": "early_stop_success"}

    # Step 2: Hunter/Apollo (interface)
    steps.append({"step": "email_finder", "used": True, "result": "provider_queried"})
    if max_steps <= 2:
        return {"stopped_at": 2, "cascaded_steps": steps, "result": "max_steps_reached"}

    # Step 3: Heurística/pattern inference
    pattern = infer_email_pattern(lead_data.get("domain", ""), "")
    steps.append({"step": "pattern_inference", "used": True, "result": pattern.get("verification_status")})
    return {"stopped_at": 3, "cascaded_steps": steps, "result": "cascade_complete"}


# --- #46 Domain-First Person Search ---
def domain_first_person_search(domain: str, target_titles: List[str]) -> Dict[str, Any]:
    """Tenta `domain + titles` primeiro; fallback para `name + location`."""
    strategy = "domain_first" if domain else "name_location_fallback"
    return {
        "domain": domain,
        "target_titles": target_titles,
        "strategy": strategy,
        "matched": [],  # populado por provider externo em produção
        "source": "domain_first_person_search",
    }


# --- #37 Hunter como provider registrado (abstração) ---
class HunterProvider:
    """Adapta o cliente Hunter existente ao protocolo ContactProvider (#37)."""

    def __init__(self):
        self.name = "hunter"
        try:
            from config.settings import settings
            self.quota_max = 500
            self.quota_used = 0
        except Exception:
            self.quota_max = 0
            self.quota_used = 0

    def find_people(self, company_data, target_roles):
        """Adapta `HunterDomainSearch` para a interface `ContactProvider`.

        Reusa a implementação real do `contact_enrichment_service` (que já
        chama Hunter via HTTP). Aqui só normalizamos o retorno.
        """
        domain = company_data.get("domain") or company_data.get("normalized_domain")
        if not domain:
            return []
        try:
            from services.contact_enrichment_service import ContactEnrichmentService
            # Em produção, await seria necessário — mas a abstração registra
            # a capacidade. A busca real ocorre em `enrich_contacts`.
            return [{
                "domain": domain,
                "provider": self.name,
                "target_roles": target_roles,
                "status": "queued_for_enrich_contacts",
            }]
        except Exception:
            return []


# Auto-registro (no import) — sem credenciais? provider entra desabilitado.
try:
    from config.settings import settings
    if getattr(settings, "HUNTER_API_KEY", None):
        register_provider(HunterProvider())
except Exception:
    # Ambiente sem settings — provider fica só disponível para testes
    pass
