"""Output contract e grounding determinístico do AI Commercial Analyst.

Não chama LLM, não altera ranking e não persiste nada. A fronteira recebe uma
saída não confiável do modelo e devolve somente análise estruturalmente válida,
com claims factuais ancorados no EvidenceContext de entrada.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

OUTPUT_CONTRACT_VERSION = "commercial-analysis-output-v1"
_VALID_EPISTEMIC = {"FACT", "INFERENCE", "HYPOTHESIS", "UNKNOWN"}
_MAX_CLAIMS = 20
_MAX_REFS = 20
_MAX_TEXT = 1200


class CommercialAnalysisValidationError(ValueError):
    pass


def _text(value: Any, limit: int = _MAX_TEXT) -> str:
    return str(value or "").strip()[:limit]


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _evidence_index(analysis_input: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    context = analysis_input.get("evidence_context")
    if not isinstance(context, Mapping):
        return set(), set()
    refs: set[str] = set()
    fact_refs: set[str] = set()
    for obs in context.get("observations") or []:
        if not isinstance(obs, Mapping):
            continue
        candidates = []
        if obs.get("reference"):
            candidates.append(str(obs["reference"]))
        if isinstance(obs.get("evidence_refs"), list):
            candidates.extend(str(x) for x in obs["evidence_refs"] if x)
        refs.update(candidates)
        if str(obs.get("epistemic") or "").upper() == "FACT":
            fact_refs.update(candidates)
    return refs, fact_refs


def _claim(raw: Any, *, allowed_refs: set[str], fact_refs: set[str]) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    statement = _text(raw.get("statement") or raw.get("text"))
    if not statement:
        return None
    refs = raw.get("evidence_refs")
    refs = [str(x)[:240] for x in refs if x][: _MAX_REFS] if isinstance(refs, list) else []
    # Referências inventadas são removidas na fronteira.
    refs = [ref for ref in refs if ref in allowed_refs]
    requested = str(raw.get("epistemic") or "INFERENCE").upper()
    if requested not in _VALID_EPISTEMIC:
        requested = "INFERENCE"

    # FACT exige pelo menos uma referência que a entrada já classificava como FACT.
    if requested == "FACT" and not any(ref in fact_refs for ref in refs):
        requested = "INFERENCE"
    # UNKNOWN não deve carregar uma afirmação positiva como se fosse observação.
    if requested == "UNKNOWN":
        refs = []

    return {
        "statement": statement,
        "epistemic": requested,
        "confidence": _confidence(raw.get("confidence")),
        "evidence_refs": refs,
    }


def _claims(raw: Any, *, allowed_refs: set[str], fact_refs: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw[:_MAX_CLAIMS]:
        normalized = _claim(item, allowed_refs=allowed_refs, fact_refs=fact_refs)
        if normalized:
            result.append(normalized)
    return result


def validate_commercial_analysis_output(
    raw: Mapping[str, Any],
    *,
    analysis_input: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise CommercialAnalysisValidationError("analysis output must be an object")
    if analysis_input.get("contract_version") != "commercial-analysis-input-v1":
        raise CommercialAnalysisValidationError("unsupported analysis input contract")

    allowed_refs, fact_refs = _evidence_index(analysis_input)
    metadata = analysis_input.get("analysis_metadata") or {}
    offer = analysis_input.get("offer") or {}
    evidence_context = analysis_input.get("evidence_context") or {}

    sections = {}
    for key in ("why_company", "why_offer", "why_now", "counter_evidence", "unknowns"):
        sections[key] = _claims(raw.get(key), allowed_refs=allowed_refs, fact_refs=fact_refs)

    hypotheses = _claims(raw.get("opportunity_hypotheses"), allowed_refs=allowed_refs, fact_refs=fact_refs)
    # Hipótese comercial nunca é promovida a FACT, mesmo se o modelo pedir.
    for item in hypotheses:
        if item["epistemic"] == "FACT":
            item["epistemic"] = "HYPOTHESIS"
        elif item["epistemic"] == "INFERENCE":
            item["epistemic"] = "HYPOTHESIS"

    approach = raw.get("suggested_approach")
    if not isinstance(approach, Mapping):
        approach = {}
    suggested_approach = {
        "angle": _text(approach.get("angle"), 600),
        "message_goal": _text(approach.get("message_goal"), 400),
        "avoid_claims": [_text(x, 240) for x in (approach.get("avoid_claims") or [])[:10] if x],
    }

    result = {
        "contract_version": OUTPUT_CONTRACT_VERSION,
        "analysis_metadata": {
            "analyzer_version": metadata.get("analyzer_version"),
            "policy_version": metadata.get("policy_version"),
            "provider": metadata.get("provider"),
            "model": metadata.get("model"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "offer_key": offer.get("key"),
            "offer_version": offer.get("version"),
            "evidence_context_hash": evidence_context.get("context_hash"),
        },
        **sections,
        "opportunity_hypotheses": hypotheses,
        "suggested_approach": suggested_approach,
    }
    canonical = json.dumps(result, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    result["analysis_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return result
