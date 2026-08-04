"""Router de template de scoring contextual (Fase 1.2).

Melhora o `load_scoring_template` do enrichment_orchestrator: quando o match
exato (case-insensitive) falha — caso comum para verticais novas — decide
entre:

1. Um template existente por aproximação (token/contains overlap).
2. Classificação por LLM entre os labels existentes.
3. Sinal `GENERATE_NEW` (consumido pelo TemplateGenerationService, item 1.3)
   para criar critérios sob demanda — nada hardcoded.

Modelo: Groq Llama 3.1 8B (classificação barata e rápida; não é geração de
texto client-facing). Com cache em memória por string normalizada para
evitar chamadas repetidas de Groq para a mesma campanha.
"""
import json
import logging
import os
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings  # noqa: E402
from database.models import CampaignScoringTemplate  # noqa: E402

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

# Threshold do overlap de tokens para aceitar match fuzzy sem LLM.
_FUZZY_THRESHOLD = 0.5

# Sinais de roteamento retornados junto com o template.
ROUTE_GENERATE_NEW = "GENERATE_NEW"
ROUTE_MATCHED = "MATCHED"
ROUTE_GENERIC = "GENERIC"


def normalize_key(value: str) -> str:
    """Normaliza string para comparação: minúsculas, sem acentos, colapsa espaços."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def token_overlap(a: str, b: str) -> float:
    """Fração de tokens de `a` presentes em `b` (ordem irrelevante).

    Ex.: "clínicas de psicologia" vs "desenvolvimento de sites" → baixo;
         "marketing digital para academias" vs "marketing digital" → alto.
    """
    ta = set(normalize_key(a).split())
    tb = set(normalize_key(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta)


def _templates_snapshot(db: Session) -> List[CampaignScoringTemplate]:
    """Templates ativos, ordenados por criação (mais antigo primeiro)."""
    return (
        db.query(CampaignScoringTemplate)
        .filter(CampaignScoringTemplate.is_active.is_(True))
        .order_by(CampaignScoringTemplate.created_at.asc())
        .all()
    )


def _find_exact(db: Session, query: str) -> Optional[CampaignScoringTemplate]:
    """Match case-insensitive/accent-insensitive por service_label."""
    key = normalize_key(query)
    if not key:
        return None
    for tmpl in _templates_snapshot(db):
        if normalize_key(tmpl.service_label) == key:
            return tmpl
    return None


def _find_fuzzy(db: Session, query: str, threshold: float = _FUZZY_THRESHOLD) -> Optional[CampaignScoringTemplate]:
    """Match por overlap de tokens acima do threshold."""
    key = normalize_key(query)
    if not key:
        return None
    best, best_score = None, 0.0
    for tmpl in _templates_snapshot(db):
        score = token_overlap(tmpl.service_label, key)
        if score > best_score:
            best, best_score = tmpl, score
    return best if best_score >= threshold else None


def _find_generic(db: Session) -> Optional[CampaignScoringTemplate]:
    return _find_exact(db, "Genérico") or _find_exact(db, "generico")


def _serialize(tmpl: CampaignScoringTemplate) -> Dict[str, Any]:
    return {
        "service_label": tmpl.service_label,
        "positive_signals": tmpl.positive_signals or [],
        "negative_signals": tmpl.negative_signals or [],
        "context_signals": tmpl.context_signals or [],
        "requires_technical_report": bool(tmpl.requires_technical_report),
        "requires_business_data": bool(tmpl.requires_business_data),
        "extra_instructions": tmpl.extra_instructions,
        "playbook": tmpl.playbook or {},
    }


# Cache em memória da classificação LLM: chave = "texto|labels", valor = (route, label).
_llm_route_cache: Dict[str, Tuple[str, str]] = {}
_LLM_CACHE_MAX = 256


def _cache_llm_route(key: str, labels_key: str, value: Tuple[str, str]) -> None:
    if len(_llm_route_cache) >= _LLM_CACHE_MAX:
        _llm_route_cache.clear()
    _llm_route_cache[f"{key}|{labels_key}"] = value


def _get_cached_llm_route(key: str, labels_key: str) -> Optional[Tuple[str, str]]:
    return _llm_route_cache.get(f"{key}|{labels_key}")


async def _classify_llm(
    query: str, labels: List[str], api_key: Optional[str] = None,
) -> Tuple[str, str]:
    """Pede à LLM que escolha o melhor label existente ou GENERATE_NEW.

    Returns:
        (ROUTE_GENERATE_NEW, "") se nenhum label serve.
        (ROUTE_MATCHED, label) se a LLM escolheu um template existente.
    """
    labels_text = "\n".join(f"- {label}" for label in labels) if labels else "(nenhum)"
    system = (
        "Você classifica ofertas de prospecção B2B em categorias de critérios. "
        "Dado o serviço/segmento que alguém quer vender, escolha a categoria "
        "existente cujos critérios melhor se aplicam. Se NENHUMA for boa, "
        "responda GENERATE_NEW. Responda SOMENTE com JSON puro."
    )
    user = (
        "Categorias de critérios de qualificação disponíveis:\n"
        f"{labels_text}\n\n"
        "Oferta a classificar:\n"
        f"Serviço: {query}\n\n"
        "Responda: {\"choice\": \"<nome exato da categoria>\"} ou "
        "{\"choice\": \"GENERATE_NEW\"}"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {api_key or settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.0,
                "max_tokens": 64,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")

    try:
        parsed = json.loads(content)
        choice = str(parsed.get("choice", "")).strip()
    except json.JSONDecodeError:
        # Fallback: procura GENERATE_NEW ou um label no texto bruto.
        if "GENERATE_NEW" in content:
            return ROUTE_GENERATE_NEW, ""
        for label in labels:
            if normalize_key(label) and normalize_key(label) in normalize_key(content):
                return ROUTE_MATCHED, label
        return ROUTE_GENERIC, "Genérico"

    if choice == "GENERATE_NEW":
        return ROUTE_GENERATE_NEW, ""
    for label in labels:
        if normalize_key(label) == normalize_key(choice):
            return ROUTE_MATCHED, label
    # A LLM devolveu um label que não está na lista (label fantasma).
    return ROUTE_GENERIC, "Genérico"


async def route_scoring_template(
    db: Session,
    target_service: str,
    target_segment: str = "",
    explicit_template_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve o melhor template de scoring para a campanha.

    Ordem:
    1. Template explicitamente associado à campanha.
    2. Match exact/accent-insensitive em target_service.
    3. Match exact/accent-insensitive em target_segment.
    4. Match fuzzy (token overlap) em target_service/segment.
    5. Classificação LLM entre labels existentes + GENERATE_NEW.
    6. Fallback Genérico.

    Returns:
        dict com o template serializado + metadados de roteamento:
        {
          "template": {...} | None,
          "route": "MATCHED" | "GENERATE_NEW" | "GENERIC",
          "matched_label": str | None,
        }
    """
    # 1. Explícito
    if explicit_template_id:
        tmpl = db.query(CampaignScoringTemplate).filter(
            CampaignScoringTemplate.id == explicit_template_id,
            CampaignScoringTemplate.is_active.is_(True),
        ).first()
        if tmpl:
            return {"template": _serialize(tmpl), "route": ROUTE_MATCHED,
                    "matched_label": tmpl.service_label}

    # 2/3. Exact
    for query in (target_service, target_segment):
        tmpl = _find_exact(db, query)
        if tmpl:
            return {"template": _serialize(tmpl), "route": ROUTE_MATCHED,
                    "matched_label": tmpl.service_label}

    # 4. Fuzzy
    for query in (target_service, target_segment):
        tmpl = _find_fuzzy(db, query)
        if tmpl:
            return {"template": _serialize(tmpl), "route": ROUTE_MATCHED,
                    "matched_label": tmpl.service_label}

    # 5. LLM (apenas se há mais que o Genérico disponível para classificar)
    snapshots = [t for t in _templates_snapshot(db)
                 if normalize_key(t.service_label) != normalize_key("Genérico")]
    generic = _find_generic(db)
    query = normalize_key(f"{target_service} {target_segment}".strip())

    if query and snapshots:
        labels = [t.service_label for t in snapshots]
        labels_key = normalize_key("|".join(labels))
        cached = _get_cached_llm_route(query, labels_key)
        if cached is not None:
            route, label = cached
        else:
            try:
                route, label = await _classify_llm(
                    f"{target_service} {target_segment}".strip(), labels, api_key,
                )
                _cache_llm_route(query, labels_key, (route, label))
            except Exception as e:
                logger.warning("LLM routing failed, falling back to generic: %s", e)
                route, label = ROUTE_GENERIC, None

        if route == ROUTE_GENERATE_NEW:
            # Item 1.3 consome este sinal para criar o template.
            return {
                "template": _serialize(generic) if generic else None,
                "route": ROUTE_GENERATE_NEW,
                "matched_label": None,
            }
        if route == ROUTE_MATCHED and label:
            tmpl = _find_exact(db, label)
            if tmpl:
                return {"template": _serialize(tmpl), "route": ROUTE_MATCHED,
                        "matched_label": label}

    # 6. Fallback Genérico
    if generic:
        return {"template": _serialize(generic), "route": ROUTE_GENERIC,
                "matched_label": generic.service_label}
    return {"template": None, "route": ROUTE_GENERIC, "matched_label": None}


async def get_playbook_for_campaign(
    db: Session,
    target_service: str,
    target_segment: str = "",
    explicit_template_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve o template da campanha e retorna o playbook de outreach (item 3.8).

    Reusa `route_scoring_template` (exact → fuzzy → LLM → genérico) para achar
    o template mais próximo e devolve seu `playbook` (hooks/subject_ideas/
    objections). Vazio `{}` se nada for resolvido.
    """
    routed = await route_scoring_template(
        db,
        target_service=target_service,
        target_segment=target_segment,
        explicit_template_id=explicit_template_id,
        api_key=api_key,
    )
    tmpl = routed.get("template") or {}
    return tmpl.get("playbook") or {}
