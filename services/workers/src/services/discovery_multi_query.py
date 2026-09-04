"""Multi-query de discovery (docs/melhorias/04): expande as consultas da
campanha e agrega resultados deduplicados com `source_queries` auditáveis.

- `expand_search_queries`: campanha com `search_queries` executa TODAS as
  consultas declaradas (variedade semântica, não paginação cega); sem a
  lista, cai para `places_query` (compat).
- `aggregate_multi_query_results`: funde os lotes por consulta, dedup por
  `place_id` (fallback: nome+categoria normalizados), mantém a ordem da
  primeira ocorrência e registra em `source_queries` TODAS as consultas que
  encontraram o lugar — evidência de especialidade/subnicho.
"""
import logging
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

MAX_SEARCH_QUERIES = 10


def _norm(text: Any) -> str:
    """Normaliza texto para comparação de identidade: minúsculas, sem
    espaços duplos e sem acentos (o Places alterna `Clínica`/`Clinica`)."""
    s = " ".join(str(text or "").lower().split())
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def expand_search_queries(
    campaign_like: Optional[Any],
    fallback_query: Optional[str] = None,
) -> List[str]:
    """Lista final de consultas a executar (não vazia, dedup, máx 10).

    Args:
        campaign_like: objeto/dict da campanha com `search_queries`
            (lista) e/ou `places_query`.
        fallback_query: consulta já resolvida pelo pipeline (quando a
            campanha não declara nada).
    """
    queries: List[str] = []
    if campaign_like is not None:
        raw = (
            campaign_like.get("search_queries")
            if isinstance(campaign_like, dict)
            else getattr(campaign_like, "search_queries", None)
        )
        if isinstance(raw, list):
            for q in raw:
                if isinstance(q, str) and q.strip():
                    queries.append(q.strip())

    if not queries:
        single = (
            campaign_like.get("places_query")
            if isinstance(campaign_like, dict)
            else getattr(campaign_like, "places_query", None)
        )
        if isinstance(single, str) and single.strip():
            queries.append(single.strip())

    if not queries and fallback_query and fallback_query.strip():
        queries.append(fallback_query.strip())

    # Fase 3 (#05): quando ainda só há 1 query (places_query ou fallback),
    # gera queries adicionais via SearchQueryGenerationService — templates
    # determinísticos por perfil + LLM opcional. Só roda se o profile_key
    # estiver disponível (vem do template) e houver segment+city suficientes.
    if len(queries) < 3 and campaign_like is not None:
        try:
            from services.search_query_generation_service import generate_queries
            target_service = (
                campaign_like.get("target_service")
                if isinstance(campaign_like, dict)
                else getattr(campaign_like, "target_service", None)
            ) or ""
            target_segment = (
                campaign_like.get("target_segment")
                if isinstance(campaign_like, dict)
                else getattr(campaign_like, "target_segment", None)
            ) or ""
            target_city = (
                campaign_like.get("target_city")
                if isinstance(campaign_like, dict)
                else getattr(campaign_like, "target_city", None)
            ) or ""
            target_state = (
                campaign_like.get("target_state")
                if isinstance(campaign_like, dict)
                else getattr(campaign_like, "target_state", None)
            ) or ""
            profile_key = (
                campaign_like.get("profile_key")
                if isinstance(campaign_like, dict)
                else getattr(campaign_like, "profile_key", None)
            ) or "generic"
            if target_service and target_segment and target_city:
                gen = generate_queries(
                    service=target_service,
                    segment=target_segment,
                    city=target_city,
                    state=target_state,
                    profile_key=profile_key,
                    max_queries=5,
                )
                for q in gen["queries"]:
                    if q.strip() and q not in queries:
                        queries.append(q)
        except Exception:
            # Se a Fase 3 falhar, mantém só as queries declaradas — não derruba
            # o pipeline (best-effort, como todo o resto da Fase 3).
            pass

    # Dedup preservando ordem (case-insensitive) e cap conservador.
    seen: set = set()
    out: List[str] = []
    for q in queries:
        key = _norm(q)
        if key and key not in seen:
            seen.add(key)
            out.append(q)
    return out[:MAX_SEARCH_QUERIES]


def aggregate_multi_query_results(
    per_query_results: Iterable[tuple],
) -> List[Dict[str, Any]]:
    """Funde resultados de N consultas deduplicando por identidade.

    Args:
        per_query_results: pares `(query, [item...])` — itens são dicts com
            `place_id` (ou `name` como fallback de identidade).

    Returns:
        Lista única de candidatos; cada item ganha `source_query` (primeira
        consulta que o encontrou) e `source_queries` (todas que o
        encontraram, em ordem de execução).
    """
    merged: List[Dict[str, Any]] = []
    index: Dict[str, int] = {}

    for query, results in per_query_results:
        for item in results or []:
            if not isinstance(item, dict):
                continue
            # O Places emite `place_id_candidate`; outros suppliers podem usar
            # `place_id`. Dedup por qualquer um — e, sem id, por nome+categoria
            # normalizados (sem acentos) como último recurso.
            place_id = item.get("place_id_candidate") or item.get("place_id")
            identity = f"pid:{place_id}" if place_id else \
                f"n:{_norm(item.get('name'))}|{_norm(item.get('category'))}"
            if identity in index:
                candidate = merged[index[identity]]
                if query not in candidate["source_queries"]:
                    candidate["source_queries"].append(query)
                continue
            candidate = dict(item)
            candidate["source_query"] = query
            candidate["source_queries"] = [query]
            index[identity] = len(merged)
            merged.append(candidate)

    return merged
