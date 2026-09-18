"""Contrato puro do futuro AI Commercial Analyst.

Esta fatia NÃO chama LLM e NÃO altera ranking. Ela prepara um input
reproduzível, versionado e grounded para que a implementação do Analyst não
precise descobrir arquitetura, nem consumir tabelas soltas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from services.prospecting.evidence_context import build_evidence_context

ANALYSIS_CONTRACT_VERSION = "commercial-analysis-input-v1"


def build_commercial_analysis_input(
    *,
    organization_id: Any,
    lead: Any,
    opportunity: Any,
    offer_profile: Any,
    provider: str | None = None,
    model: str | None = None,
    analyzer_version: str = "commercial-analyst-v1",
    policy_version: str = "grounded-analysis-v1",
) -> dict[str, Any]:
    """Monta somente fatos/contexto já existentes; nenhuma conclusão comercial."""
    profile_payload = offer_profile.to_dict() if offer_profile is not None else None
    evidence_context = build_evidence_context(
        evidence=getattr(lead, "evidence", None),
        discovery_provenance=getattr(lead, "discovery_provenance", None),
        evidence_score=getattr(lead, "evidence_score", None),
    )
    score_vector = getattr(lead, "score_vector", None)
    return {
        "contract_version": ANALYSIS_CONTRACT_VERSION,
        "analysis_metadata": {
            "analyzer_version": analyzer_version,
            "policy_version": policy_version,
            "provider": provider,
            "model": model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "identity": {
            "organization_id": str(organization_id),
            "lead_id": str(getattr(lead, "id", "")),
            "company_id": str(getattr(lead, "company_id", "") or "") or None,
            "opportunity_id": str(getattr(opportunity, "id", "") or "") or None,
        },
        "offer": {
            "key": getattr(offer_profile, "key", None),
            "version": getattr(offer_profile, "version", None),
            "profile": profile_payload,
        },
        "company": {
            "name": getattr(lead, "company_name", None),
            "cnpj": getattr(lead, "cnpj", None),
            "category": getattr(lead, "category", None),
            "city": getattr(lead, "city", None),
            "state": getattr(lead, "state", None),
            "website": getattr(lead, "website", None),
        },
        "scoring": {
            "qualification_score": getattr(lead, "qualification_score", None),
            "score_vector": dict(score_vector) if isinstance(score_vector, Mapping) else None,
            "offer_score": getattr(opportunity, "score", None),
            "signals_matched": list(getattr(opportunity, "signals_matched", None) or []),
            "signals_missing": list(getattr(opportunity, "signals_missing", None) or []),
            "score_breakdown": dict(getattr(opportunity, "score_breakdown", None) or {}),
        },
        "evidence_context": evidence_context,
    }
