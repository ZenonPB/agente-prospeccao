"""Rotas de Analytics (BI).

Todos os endpoints são **ANALYST/MANAGER-only** (owner/admin passam) e
**org-scoped**: o serviço filtra por `organization_id` da org do usuário.
Consultor (CONSULTOR) recebe 403 — não acessa relatórios.

Endpoints:
- `GET /api/analytics/overview`      — KPIs, funil, conversão, resposta, score
- `GET /api/analytics/funnel`        — funil ponta-a-ponta
- `GET /api/analytics/consultants`   — desempenho por consultor
- `GET /api/analytics/consultants/{user_id}`        — perfil (KPIs da planilha + funil)
- `GET /api/analytics/consultants/{user_id}/activity` — trilha recente do consultor
- `GET /api/analytics/leads-ranking` — top leads (score/conversão/criação)
- `GET /api/analytics/geo`           — agregação por cidade/UF (heatmap/mapa)
- `GET /api/analytics/campaigns`     — desempenho por campanha
- `GET /api/analytics/outcomes-breakdown` — cortes por vertical/consultor/campanha/provider/versão
- `GET /api/analytics/timeline`      — evolução temporal (novos/reuniões/fechados)
- `GET /api/analytics/forecast`      — forecast ponderado por estágio
- `GET /api/analytics/export/pdf`    — relatório executivo em PDF
- `GET /api/analytics/provider-usage` — execução, latência e falhas por provider
"""
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.auth.dependencies import get_user_organization, require_analyst
from src.services.analytics_service import AnalyticsService
from src.services.pdf_report_service import build_report_pdf

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


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


@router.get("/executive-metrics")
def executive_metrics(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    campaign_id: Optional[str] = Query(None),
    k: int = Query(10, ge=1, le=100),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Expõe métricas executivas org-scoped sem efeitos colaterais."""
    return analytics.executive_metrics(
        from_date=from_date,
        to_date=to_date,
        campaign_id=campaign_id,
        k=k,
    )


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
    if not _valid_uuid(user_id):
        raise HTTPException(status_code=400, detail="Consultor inválido")
    detail = analytics.consultant_detail(
        user_id, from_date=from_date, to_date=to_date,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Consultor não encontrado")
    return detail


@router.get("/consultants/{user_id}/activity")
def consultant_activity(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Trilha recente do consultor (atividades dos leads dele + ações dele)."""
    if not _valid_uuid(user_id):
        raise HTTPException(status_code=400, detail="Consultor inválido")
    return {
        "activities": analytics.consultant_activity(
            user_id, limit=limit, from_date=from_date, to_date=to_date,
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


@router.get("/outcomes-breakdown")
def outcomes_breakdown(
    by: str = Query("vertical", min_length=1, max_length=32),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    offer_key: Optional[str] = Query(None, max_length=64),
    offer_version: Optional[str] = Query(None, max_length=32),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Cortes de BI sobre outcomes reais (P1.25).

    Dimensões com coluna real: `vertical` (Lead.category),
    `consultor` (responsável do lead), `campanha`, `provider` e
    `offer_version`. Amostra sempre visível com `sample_sufficient`.
    """
    try:
        return analytics.outcomes_breakdown(
            by=by,
            from_date=from_date,
            to_date=to_date,
            offer_key=offer_key,
            offer_version=offer_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/deliverability")
def deliverability(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Verifica saúde de entregabilidade de e-mail da organização.

    Retorna taxa de bounce, contadores e sinaliza se o envio automático
    deve ser pausado (bounce rate > 5%).
    """
    return analytics.check_email_deliverability(from_date=from_date, to_date=to_date)


@router.get("/provider-usage")
def provider_usage(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    provider: Optional[str] = Query(None, min_length=1, max_length=64),
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
    db: Session = Depends(get_db),
):
    """Agrega execuções de providers sem expor dados de outra organização."""
    from datetime import datetime, timezone
    from services.provider_execution_metric_service import ProviderExecutionMetricService

    def parse_boundary(value: Optional[str], end: bool = False):
        if not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    try:
        metrics = ProviderExecutionMetricService().list_for_organization(
            db,
            org.id,
            date_from=parse_boundary(from_date),
            date_to=parse_boundary(to_date, end=True),
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Período inválido: {exc}") from exc
    return {
        "providers": ProviderExecutionMetricService.aggregate_metrics(metrics),
        "sample_size": len(metrics),
        "cost_available": any(metric.cost is not None for metric in metrics),
    }


@router.get("/provider-trace/{correlation_id}")
def provider_trace(
    correlation_id: str,
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
    db: Session = Depends(get_db),
):
    """Devolve o trace de um job: todas as medições com o mesmo `correlation_id`.

    Permite explicar "por que esta campanha trouxe poucos leads" olhando
    status/latência/erro de cada provider daquela execução.
    """
    from uuid import UUID
    from services.provider_execution_metric_service import ProviderExecutionMetricService

    try:
        corr_uuid = UUID(str(correlation_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="correlation_id inválido") from None

    service = ProviderExecutionMetricService()
    metrics = service.list_by_correlation_id(db, corr_uuid)
    # Garante tenant scope: só devolve métricas da própria organização.
    metrics = [m for m in metrics if m.organization_id == org.id]
    if not metrics:
        return {"correlation_id": str(corr_uuid), "metrics": [], "sample_size": 0}

    def _serialize(m) -> dict:
        return {
            "provider": m.provider,
            "status": m.status,
            "result_count": m.result_count,
            "duration_ms": m.duration_ms,
            "budget_used": m.budget_used,
            "error_code": m.error_code,
            "retryable": m.retryable,
            "cost": float(m.cost) if m.cost is not None else None,
            "usage": m.usage,
            "job_id": str(m.job_id) if m.job_id else None,
            "campaign_id": str(m.campaign_id) if m.campaign_id else None,
            "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
        }

    return {
        "correlation_id": str(corr_uuid),
        "metrics": [_serialize(m) for m in metrics],
        "sample_size": len(metrics),
    }


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


@router.get("/template-insights")
def template_insights(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    campaign_id: Optional[str] = Query(None, alias="campaign_id"),
    analytics: AnalyticsService = Depends(_get_analytics),
):
    """Sugestões de calibração de vertente (loop de aprendizado).

    Correlaciona `score_factors[]` de leads convertidos × perdidos e sugere
    reforçar/reduzir características com desvio relevante. ANALYST/MANAGER
    leem; a edição dos pesos segue manual no editor da vertente.
    """
    return analytics.template_insights(
        from_date=from_date,
        to_date=to_date,
        campaign_id=campaign_id,
    )


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
