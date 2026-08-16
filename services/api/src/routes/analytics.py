"""Rotas de Analytics (BI).

Todos os endpoints são **ANALYST/MANAGER-only** (owner/admin passam) e
**org-scoped**: o serviço filtra por `organization_id` da org do usuário.
Consultor (CONSULTOR) recebe 403 — não acessa relatórios.

Endpoints:
- `GET /api/analytics/overview`      — KPIs, funil, conversão, resposta, score
- `GET /api/analytics/funnel`        — funil ponta-a-ponta
- `GET /api/analytics/consultants`   — desempenho por consultor
- `GET /api/analytics/leads-ranking` — top leads (score/conversão/criação)
- `GET /api/analytics/geo`           — agregação por cidade/UF (heatmap/mapa)
- `GET /api/analytics/campaigns`     — desempenho por campanha
- `GET /api/analytics/timeline`      — evolução temporal (novos/reuniões/fechados)
- `GET /api/analytics/forecast`      — forecast ponderado por estágio
- `GET /api/analytics/export/pdf`    — relatório executivo em PDF
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


@router.get("/funnel")
def funnel(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    campaign_id: Optional[str] = Query(None),
    consultant_id: Optional[str] = Query(None),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Funil ponta-a-ponta — achados → fechamento.

    Aceita filtros opcionais de campanha e consultor além do período.
    """
    return analytics.funnel(
        from_date=from_date,
        to_date=to_date,
        campaign_id=campaign_id,
        consultant_id=consultant_id,
    )


@router.get("/consultants")
def consultants(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    return {"consultants": analytics.consultants(from_date=from_date, to_date=to_date)}


@router.get("/consultants/{user_id}")
def consultant_detail(
    user_id: str,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Perfil de um consultor (ANALYST/MANAGER-only): KPIs da planilha +
    funil ponta-a-ponta dele. 404 se o usuário não é membro da org."""
    detail = analytics.consultant_detail(
        str(user_id), from_date=from_date, to_date=to_date,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Consultor não encontrado")
    return detail


@router.get("/consultants/{user_id}/activity")
def consultant_activity(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Trilha recente do consultor (atividades dos leads dele + ações dele)."""
    return {
        "activities": analytics.consultant_activity(
            str(user_id), limit=limit,
        )
    }


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


@router.get("/threshold-suggestion")
def threshold_suggestion(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
    org: Organization = Depends(get_user_organization),
):
    """Sugere um limiar QUALIFICADO/DESQUALIFICADO calibrado pela org.

    Apenas ANALYST/MANAGER (owner/admin) leem. A UI exibe o threshold atual
    da org + o sugerido com a lista de candidatos (precisão/revisão/F1) e
    deixa o owner/admin aplicar manualmente em `/api/orgs/{id}`.
    """
    current = org.qualification_threshold or 60
    return analytics.suggest_qualification_threshold(
        current_threshold=current,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/message-variants")
def message_variants(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Desempenho por variante A/B de cadência.

    Para cada variante (A/B/...), mostra: mensagens enviadas, abertas,
    clicadas e que receberam resposta. A variante é lida de `messages.variant`
    (uma linha por envio real) — sem o proxy pelo status do funil. A resposta
    é atribuída à variante da última mensagem enviada antes do inbound.
    """
    return analytics.message_variants(from_date=from_date, to_date=to_date)


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
