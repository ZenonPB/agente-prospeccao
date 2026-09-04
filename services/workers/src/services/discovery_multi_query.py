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
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

MAX_SEARCH_QUERIES = 10


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


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
            place_id = item.get("place_id")
            identity = f"pid:{place_id}" if place_id else \
                f"n:{_norm(item.get('name'))}|{item.get('category') or ''}"
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
