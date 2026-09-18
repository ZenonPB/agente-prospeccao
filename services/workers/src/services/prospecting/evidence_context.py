"""Adapter puro para o contexto de evidência consumido pela inteligência.

Não cria uma nova fonte de verdade. Normaliza as estruturas canônicas já
persistidas para leitura/auditoria pelo AI Commercial Analyst e snapshots.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

EVIDENCE_CONTEXT_VERSION = "evidence-context-v1"
_VALID_EPISTEMIC = {"FACT", "INFERENCE", "HYPOTHESIS", "UNKNOWN"}


def _items(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                yield item


def _normalize(item: Mapping[str, Any], family: str) -> dict[str, Any]:
    source = item.get("source") or item.get("provider") or family
    epistemic = str(
        item.get("epistemic") or item.get("epistemic_status") or ""
    ).upper()
    if epistemic not in _VALID_EPISTEMIC:
        # Conteúdo legado não recebe FACT por conveniência.
        epistemic = "INFERENCE" if item else "UNKNOWN"
    confidence = item.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        confidence = None
    elif confidence > 1:
        confidence = max(0.0, min(1.0, float(confidence) / 100.0))
    else:
        confidence = max(0.0, min(1.0, float(confidence)))
    return {
        "family": family,
        "key": item.get("key"),
        "title": item.get("title"),
        "description": item.get("description") or item.get("evidence"),
        "source": str(source)[:200] if source else None,
        "reference": item.get("url") or item.get("source_url") or item.get("reference"),
        "observed_at": item.get("observed_at"),
        "confidence": confidence,
        "epistemic": epistemic,
        "evidence_refs": list(item.get("evidence_refs") or [])[:20]
        if isinstance(item.get("evidence_refs"), list) else [],
    }


def build_evidence_context(
    *,
    evidence: Any = None,
    discovery_provenance: Any = None,
    evidence_score: Any = None,
    signals: Any = None,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for family, raw in (
        ("scoring", evidence),
        ("discovery", discovery_provenance),
        ("derived", evidence_score),
        ("signal", signals),
    ):
        for item in _items(raw):
            observations.append(_normalize(item, family))

    # Ordem determinística: hash não depende da ordem incidental de producers.
    observations.sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False, default=str))
    payload = {"schema_version": EVIDENCE_CONTEXT_VERSION, "observations": observations}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    payload["context_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload
