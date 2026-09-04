"""Search Query Generation (#05) — gera queries automáticas via LLM com fallback.

Seam: service + segment + city + oferta/perfil → lista de queries/subnichos.
A LLM não qualifica leads — só expande consulta. Templates determinísticos como fallback.
"""
from typing import Any, Dict, List, Optional

# Templates determinísticos (fallback sem LLM) — organizados por perfil/intent
_TEMPLATES: Dict[str, List[str]] = {
    "web_presence": [
        "{service} {city}",
        "{service} {segment} {city}",
        "{segment} online {city}",
    ],
    "business_opportunity": [
        "{service} corporativo {city}",
        "{segment} B2B {city}",
        "fornecedor {service} {city}",
    ],
    "industrial": [
        "{service} industrial {city}",
        "{segment} metalúrgica {city}",
        "fabricante {service} {city}",
    ],
    "generic": [
        "{service} {city}",
        "{segment} {city}",
    ],
}


def generate_queries(
    service: str,
    segment: str,
    city: str,
    state: str = "",
    profile_key: str = "generic",
    offer_context: Optional[Dict[str, Any]] = None,
    llm_expander: Optional[Any] = None,
    max_queries: int = 6,
) -> Dict[str, Any]:
    """Gera queries de descoberta (doc 05).

    1. Tenta expansão via LLM (se llm_expander fornecido).
    2. Fallback determinístico via templates se LLM falhar/ausente.
    3. Deduplicação semântica (case-insensitive) e limite configurável.

    Returns:
        {"queries": [...], "profile_key": ..., "source": ..., "used_llm": bool}
    """
    used_llm = False
    queries = []

    # Tentativa via LLM (opcional — injetado para não acoplar ao Groq)
    if llm_expander is not None:
        try:
            expanded = llm_expander(service=service, segment=segment, city=city,
                                    state=state, profile_key=profile_key,
                                    offer_context=offer_context or {})
            if isinstance(expanded, list):
                queries = [q for q in expanded if isinstance(q, str) and q.strip()]
                used_llm = bool(queries)
        except Exception:
            queries = []

    # Fallback determinístico
    if not queries:
        templates = _TEMPLATES.get(profile_key, _TEMPLATES["generic"])
        queries = [
            t.format(service=service.strip(), segment=segment.strip(), city=city.strip())
            for t in templates
        ]

    # Dedup semântica (case-insensitive) e limite
    seen = set()
    deduped = []
    for q in queries:
        key = q.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(q.strip())
            if len(deduped) >= max_queries:
                break

    return {
        "queries": deduped,
        "profile_key": profile_key,
        "used_llm": used_llm,
        "source": "search_query_generation_service",
    }
