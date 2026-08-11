"""Rotas de Analytics (BI) — Item 2.2 do roadmap.

Todos os endpoints são **ANALYST/MANAGER-only** (owner/admin passam) e
**org-scoped**: o serviço filtra por `organization_id` da org do usuário.
Consultor (CONSULTOR) recebe 403 — não acessa relatórios.

Endpoints:
- `GET /api/analytics/overview`      — KPIs, funil, conversão, resposta, score
- `GET /api/analytics/consultants`   — desempenho por consultor
- `GET /api/analytics/leads-ranking` — top leads (score/conversão/criação)
- `GET /api/analytics/geo`           — agregação por cidade/UF (heatmap/mapa)
- `GET /api/analytics/campaigns`     — desempenho por campanha
- `GET /api/analytics/timeline`      — evolução temporal (novos/reuniões/fechados)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.auth.dependencies import get_user_organization, require_analyst
from src.services.analytics_service import AnalyticsService
from src.services.pdf_report_service import build_report_pdf

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_analytics(
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(require_analyst()),
    db: Session = Depends(get_db),
) -> AnalyticsService:
    """Dependency: ANALYST/MANAGER (owner/admin) + serviço org-scoped."""
    return AnalyticsService(db, org.id)


@router.get("/overview")
def overview(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    return analytics.overview(from_date=from_date, to_date=to_date)


@router.get("/consultants")
def consultants(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    return {"consultants": analytics.consultants(from_date=from_date, to_date=to_date)}


@router.get("/forecast")
def forecast(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    return analytics.forecast(from_date=from_date, to_date=to_date)


@router.get("/leads-ranking")
def leads_ranking(
    sort_by: str = Query("score", pattern="^(score|converted|created)$"),
    campaign_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    limit: int = Query(20, ge=1, le=100),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    return analytics.leads_ranking(
        sort_by=sort_by,
        campaign_id=campaign_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )


@router.get("/geo")
def geo(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    return analytics.geo(from_date=from_date, to_date=to_date)


@router.get("/campaigns")
def campaigns(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    return {"campaigns": analytics.campaigns(from_date=from_date, to_date=to_date)}


@router.get("/timeline")
def timeline(
    group_by: str = Query("day", pattern="^(day|week)$"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    return {"timeline": analytics.timeline(group_by=group_by, from_date=from_date, to_date=to_date)}


@router.get("/export/pdf")
def export_pdf(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(require_analyst()),
    db: Session = Depends(get_db),
):
    """Exporta o relatório executivo completo em PDF (ANALYST/MANAGER-only).

    Rota declarada após `/timeline` e antes de nenhum path com `{param}` —
    não há conflito de roteamento aqui porque todos os outros endpoints
    possuem path fixo.
    """
    try:
        pdf_bytes = build_report_pdf(
            db, org_name=org.name or "Minha organização", org_id=org.id,
            from_date=from_date, to_date=to_date,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc}",
        ) from exc

    filename = f"relatorio-prospeccao-{from_date or 'inicio'}-{to_date or 'hoje'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
