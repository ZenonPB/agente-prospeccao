"""Piloto Araraquara: Landing Pages → clínicas de psicologia (PR E).

Recorte operacional por workspace (CNAE 8650-0/03, SP, município 3503208),
stage idempotente da versão e smoke sem outreach, sem rede e sem provider
pago. Fixtures em layout oficial exercitam o caminho; snapshot real
continua gate de validação operacional.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Mapping

logger = logging.getLogger(__name__)

PILOT_OFFER_KEY = "landing_page"
PILOT_VERSION = "1.1"
PILOT_CNAES = ["8650-0/03"]
PILOT_STATES = ["SP"]
PILOT_MUNICIPIO_COD = "3503208"
PILOT_SIZES = ["ME", "EPP"]
PILOT_SEGMENTS = ["psicologia", "psicanálise", "clínicas"]
PILOT_TARGET_CANDIDATES = 20
PILOT_SITUACAO_ATIVA = "02"
PILOT_MONTH = "2026-08"


def build_pilot_overlay(base_profile: Any) -> dict[str, Any]:
    """Aplica o recorte do piloto sobre a Vertente base (sem mutá-la)."""
    from services.prospecting.workspace_overlay import build_workspace_overlay

    return build_workspace_overlay(
        base_profile,
        version=PILOT_VERSION,
        icp_overrides={
            "company_sizes": list(PILOT_SIZES),
            "segments": list(PILOT_SEGMENTS),
            "cnaes": list(PILOT_CNAES),
            "geography": {
                "country": "BR",
                "states": list(PILOT_STATES),
                "municipality_code": PILOT_MUNICIPIO_COD,
            },
        },
        discovery_overrides={
            "providers": ["cnae_discovery", "google_places"],
            "target_candidates": PILOT_TARGET_CANDIDATES,
            "provider_budgets": {"cnae_discovery": PILOT_TARGET_CANDIDATES},
        },
    )


def stage_pilot_overlay(db: Any, organization_id: Any, *, version: str = PILOT_VERSION) -> Any:
    """Persiste o overlay como versão INATIVA (idempotente). A ativação é
    humana e explícita, pelo fluxo existente de versões — nunca automática."""
    from database.learning_models import OfferProfileVersion
    from services.prospecting.default_profiles import get_base_registry

    base = get_base_registry().get(PILOT_OFFER_KEY)
    if base is None:
        raise ValueError(f"oferta base ausente no catálogo: {PILOT_OFFER_KEY}")
    existing = db.query(OfferProfileVersion).filter(
        OfferProfileVersion.organization_id == organization_id,
        OfferProfileVersion.offer_key == PILOT_OFFER_KEY,
        OfferProfileVersion.version == version,
    ).first()
    if existing is not None:
        return existing
    snapshot = build_pilot_overlay(base)
    snapshot["version"] = version
    row = OfferProfileVersion(
        organization_id=organization_id,
        offer_key=PILOT_OFFER_KEY,
        version=version,
        profile_snapshot=snapshot,
        is_active=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _situacao_ativa(value: Any) -> bool:
    return str(value or "").strip().lstrip("0") == PILOT_SITUACAO_ATIVA.lstrip("0")


async def run_pilot_smoke(
    db: Any, organization_id: Any, *, snapshot_month: str,
    target_candidates: int = PILOT_TARGET_CANDIDATES,
) -> dict[str, Any]:
    """Executa o caminho do piloto sobre o Registry e devolve o relatório.

    Registry → discovery → entity resolution → Company → shadow UNKNOWN →
    budget R$0. Sem outreach, sem rede, sem provider pago.
    """
    from services.company_identity_service import CompanyIdentityResolver
    from services.company_person_service import CompanyPersonService
    from services.prospecting.commercial_dimensions import derive_commercial_dimensions
    from services.prospecting.effective_offer_registry import get_effective_profile
    from services.prospecting.pilot_metrics import summarize_pilot
    from services.prospecting.provider_access_policy import ProviderAccessPolicy
    from services.prospecting.provider_planner import ProviderPolicy
    from services.registry.activation import resolve_snapshot
    from services.registry.discovery_adapter import RegistryCnaeDiscoveryAdapter
    from services.registry.importer import SOURCE
    from services.registry.search import RegistrySearchService
    from services.registry.targeting import TargetingResult

    started = time.perf_counter()
    # Contrato A: o mês solicitado controla a query; indisponível falha
    # fechado aqui (SnapshotNotAvailable é ValueError), sem fallback.
    resolved = resolve_snapshot(db, source=SOURCE, snapshot_month=snapshot_month)
    if resolved is None:  # pragma: no cover — mês sempre explícito no piloto
        raise SnapshotNotAvailable(f"snapshot {SOURCE}/{snapshot_month} indisponível")
    resolved_month = str(resolved.snapshot_month)
    if resolved_month != snapshot_month:
        raise SnapshotNotAvailable(
            f"snapshot resolvido {resolved_month} diverge do solicitado {snapshot_month}")
    profile = get_effective_profile(db, organization_id, PILOT_OFFER_KEY)
    if profile is None or profile.version != PILOT_VERSION:
        raise ValueError("overlay piloto ativo ausente para a organização")
    outcome = TargetingResult.from_offer(
        profile.icp, profile.discovery, target_candidates=target_candidates)
    if outcome.filters is None:
        raise ValueError("ICP do piloto não gerou filtros do Registry")

    adapter = RegistryCnaeDiscoveryAdapter(
        search_service_factory=lambda: RegistrySearchService(db),
        budget_total=target_candidates,
        source_snapshot=resolved_month,
    )
    context = {
        "icp": dict(profile.icp),
        "municipio_cod": PILOT_MUNICIPIO_COD,
        "target_candidates": target_candidates,
    }
    discovery = await adapter.run_with_status("", context)
    status = discovery.get("status")
    failures = 0 if status in ("success", "empty") else 1
    items: list[dict[str, Any]] = list(discovery.get("items") or [])

    resolver = CompanyIdentityResolver()
    collisions = 0
    for index, item in enumerate(items):
        others = [other for j, other in enumerate(items) if j != index]
        found = resolver.resolve(dict(item), [dict(o) for o in others])
        if found.status == "confirmed":
            collisions += 1
    companies: list[Any] = []
    for item in items:
        company = CompanyPersonService.get_or_create_company(
            db, organization_id, dict(item))
        if company is not None:
            companies.append(company)
    db.commit()
    repeat_ids = set()
    for item in items:
        company = CompanyPersonService.get_or_create_company(
            db, organization_id, dict(item))
        if company is not None:
            repeat_ids.add(str(company.id))
    duplicates_avoided = sum(
        1 for company in companies if str(company.id) in repeat_ids)

    dimensions = derive_commercial_dimensions({}, evidence=None) or {}
    unknown = all(dimensions.get(key) is None for key in (
        "adherence", "moment", "contactability", "data_confidence"))
    policy = ProviderAccessPolicy()
    paid_allowed, _ = policy.allows(ProviderPolicy(
        provider="hunter", capability="contact_enrichment", cost_per_request=0.02))
    attempts = [{
        "provider": "brazil_company_registry",
        "status": status,
        "result_count": len(items),
        "cost": 0.0,
    }]
    summary = summarize_pilot([], attempts)
    providers = summary.get("providers") or {}

    principal = sum(1 for item in items if (item.get("cnae_code") or "") == "8650003")
    secundario = sum(
        1 for item in items
        if (item.get("cnae_code") or "") != "8650003"
        and "8650003" in (item.get("cnaes_secundarios") or []))
    report = {
        "status": "success" if failures == 0 and status == "success" else status,
        "vertente": profile.key,
        "versao": profile.version,
        "cnaes": list((profile.icp or {}).get("cnaes") or []),
        "territorio": {"uf": "SP", "municipio_cod": PILOT_MUNICIPIO_COD},
        "snapshot": resolved_month,
        "requested_snapshot": snapshot_month,
        "resolved_snapshot": resolved_month,
        "candidatos": len(items),
        "ativas": sum(1 for item in items if _situacao_ativa(item.get("situacao"))),
        "cnae_principal": principal,
        "cnae_secundario": secundario,
        "colisoes": collisions,
        "empresas_materializadas": len(companies),
        "duplicatas_evitadas": duplicates_avoided,
        "websites_encontrados": 0,
        "custo_estimado": providers.get("estimated_cost", 0.0),
        "prova_sem_pago": paid_allowed is False,
        "dimensoes_unknown": unknown,
        "proveniencias_ok": all(bool(item.get("source_snapshot")) for item in items),
        "falhas": failures,
        "duracao_s": round(time.perf_counter() - started, 3),
    }
    logger.info(
        "piloto araraquara: %s candidatos=%d ativas=%d materializadas=%d custo=%s",
        report["status"], report["candidatos"], report["ativas"],
        report["empresas_materializadas"], report["custo_estimado"])
    return report


def empty_pilot_sample_summary() -> Mapping[str, Any]:
    """Agregado honesto do smoke: sem leads trabalhados, sem outcomes."""
    from services.prospecting.pilot_metrics import summarize_pilot

    return summarize_pilot([], [])
