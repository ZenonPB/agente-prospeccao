"""Serviço de analytics (BI) — Item 2.2 do roadmap.

Todas as consultas são **org-scoped** (isolamento cross-tenant) e usadas
exclusivamente por ANALYST/MANAGER (owner/admin). Não expõem leads de outras
organizações: cada query filtra por `organization_id`.

Fonte de dados:
- `Lead` (funil, score, atribuição, geo, timeline de criação)
- `Conversion` (fechados, ticket, quem fechou)
- `LeadActivity` (timeline de reuniões via STATUS_CHANGED → REUNIAO_MARCADA)
- `OrganizationMember` (consultores da org)
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import (
    Lead,
    LeadStatus,
    Campaign,
    Conversion,
    LeadActivity,
    LeadActivityAction,
    User,
    OrganizationMember,
    NegotiationStage,
    ContractOutcome,
    LostReason,
)

# Faixas de score usadas no overview (0-100).
SCORE_BANDS = [
    (0, 39, "0-39"),
    (40, 59, "40-59"),
    (60, 79, "60-79"),
    (80, 100, "80-100"),
]

STAGE_WIN_RATES = {
    LeadStatus.NOVO: 0.05,
    LeadStatus.ANALISADO: 0.10,
    LeadStatus.QUALIFICADO: 0.15,
    LeadStatus.CONTATADO: 0.25,
    LeadStatus.RESPONDIDO: 0.40,
    LeadStatus.REUNIAO_MARCADA: 0.60,
    LeadStatus.REUNIAO_FEITA: 0.75,
    LeadStatus.PROPOSTA_ENVIADA: 0.90,
}


def _parse_period(value: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
    """Converte `YYYY-MM-DD` (ou ISO datetime) em datetime para filtros.

    `end_of_day=True` coloca em 23:59:59 (fim do dia) para filtros `to`.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    if isinstance(parsed, datetime) and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if end_of_day and isinstance(parsed, datetime) and parsed.hour == 0 and parsed.minute == 0:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed


class AnalyticsService:
    """Agregações de BI para uma organização. Nenhuma query vaza para outra org."""

    def __init__(self, db: Session, organization_id):
        self.db = db
        self.org_id = organization_id

    # ---------------------------------------------------------------- helpers
    def _leads(self, from_date: Optional[str] = None, to_date: Optional[str] = None, user_id=None):
        q = self.db.query(Lead).filter(Lead.organization_id == self.org_id)
        if user_id:
            q = q.filter(Lead.assigned_to_id == user_id)
        f = _parse_period(from_date)
        t = _parse_period(to_date, end_of_day=True)
        if f:
            q = q.filter(Lead.created_at >= f)
        if t:
            q = q.filter(Lead.created_at <= t)
        return q

    def _count_status(self, base, *statuses):
        return base.filter(Lead.status.in_(statuses)).count()

    # ---------------------------------------------------------------- overview
    def overview(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> dict:
        base = self._leads(from_date, to_date)
        total = base.count()

        qualified = self._count_status(base, LeadStatus.QUALIFICADO)
        contacted = self._count_status(base, LeadStatus.CONTATADO)
        responded = self._count_status(base, LeadStatus.RESPONDIDO)
        meetings = self._count_status(base, LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA)
        proposals = self._count_status(base, LeadStatus.PROPOSTA_ENVIADA)

        # Conversões (fechados) — via Conversion, filtrada pela org.
        conv_q = (
            self.db.query(Conversion)
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
        )
        converted = conv_q.count()
        revenue = (
            self.db.query(func.coalesce(func.sum(Conversion.contract_value), 0))
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .scalar()
        ) or 0

        funnel = [
            {"stage": "NOVO", "count": self._count_status(base, LeadStatus.NOVO)},
            {"stage": "ANALISADO", "count": self._count_status(base, LeadStatus.ANALISADO)},
            {"stage": "QUALIFICADO", "count": qualified},
            {"stage": "DESQUALIFICADO", "count": self._count_status(base, LeadStatus.DESQUALIFICADO)},
            {"stage": "CONTATADO", "count": contacted},
            {"stage": "RESPONDIDO", "count": responded},
            {"stage": "REUNIAO_MARCADA", "count": self._count_status(base, LeadStatus.REUNIAO_MARCADA)},
            {"stage": "REUNIAO_FEITA", "count": self._count_status(base, LeadStatus.REUNIAO_FEITA)},
            {"stage": "PROPOSTA_ENVIADA", "count": proposals},
            {"stage": "PERDIDO", "count": self._count_status(base, LeadStatus.PERDIDO)},
        ]

        # Leads com conversão (fechados) na org — usado p/ cruzar taxa de acerto
        # do score por faixa (Item 3.6.2).
        converted_sub = (
            self.db.query(Lead.id)
            .join(Conversion, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .subquery()
        )

        score_bands = []
        for lo, hi, label in SCORE_BANDS:
            band_q = base.filter(
                Lead.qualification_score >= lo,
                Lead.qualification_score <= hi,
            )
            band_count = band_q.count()
            band_converted = band_q.filter(
                Lead.id.in_(self.db.query(converted_sub.c.id)),
            ).count()
            score_bands.append({
                "band": label,
                "count": band_count,
                "converted": band_converted,
                "conversion_rate": round(
                    (band_converted / band_count * 100), 1
                ) if band_count else 0,
            })

        # Forecast resumo para o overview (item 4.8)
        open_leads = base.filter(Lead.status.in_(list(STAGE_WIN_RATES.keys()))).all()
        pipeline_val = sum(float(l.value or 0) for l in open_leads)
        forecast_val = sum(float(l.value or 0) * STAGE_WIN_RATES.get(l.status, 0.0) for l in open_leads)

        return {
            "total_leads": total,
            "qualified_leads": qualified,
            "contacted_leads": contacted,
            "responded_leads": responded,
            "meetings_scheduled": meetings,
            "proposals_sent": proposals,
            "converted_leads": converted,
            "total_revenue": round(float(revenue), 2),
            "pipeline_value": round(pipeline_val, 2),
            "forecast_weighted": round(forecast_val, 2),
            "conversion_rate": round((converted / qualified * 100), 1) if qualified else 0,
            "response_rate": round((responded / contacted * 100), 1) if contacted else 0,
            "meeting_rate": round((meetings / qualified * 100), 1) if qualified else 0,
            "funnel": funnel,
            "leads_by_score_band": score_bands,
            # Funil interno de negociação (roadmap-leads C.3): estágio
            # RD/ORÇAMENTO/RP e resultado de contrato APROVADO/REPROVADO/EM_ANÁLISE.
            "negotiation_distribution": [
                {"stage": s.value, "count": base.filter(Lead.negotiation_stage == s).count()}
                for s in NegotiationStage
            ],
            "contracts_by_outcome": [
                {"outcome": o.value, "count": base.filter(Lead.contract_outcome == o).count()}
                for o in ContractOutcome
            ],
        }

    # ---------------------------------------------------------------- consultants
    def consultants(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list:
        """Métricas por consultor: atribuídos, contatados, reuniões, propostas,
        convertidos, conversão %. Baseia-se em `assigned_to_id` (atribuição) e
        `Conversion` (quem fechou). Inclui apenas membros da org."""
        members = (
            self.db.query(OrganizationMember, User)
            .join(User, OrganizationMember.user_id == User.id)
            .filter(OrganizationMember.organization_id == self.org_id)
            .all()
        )

        # Leads atribuídos por usuário (no período).
        assigned_by_user: dict = {}
        rows = (
            self.db.query(Lead.assigned_to_id, func.count(Lead.id))
            .filter(Lead.organization_id == self.org_id, Lead.assigned_to_id.isnot(None))
            .group_by(Lead.assigned_to_id)
        )
        f = _parse_period(from_date)
        t = _parse_period(to_date, end_of_day=True)
        if f:
            rows = rows.filter(Lead.created_at >= f)
        if t:
            rows = rows.filter(Lead.created_at <= t)
        for uid, count in rows.all():
            assigned_by_user[str(uid)] = count

        # Conversões por usuário (quem fechou: user_id ou assigned_to_id).
        converted_by_user: dict = {}
        conv_rows = (
            self.db.query(Conversion.user_id, Conversion.assigned_to_id, Conversion.id)
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .all()
        )
        for user_id, assigned_id, _ in conv_rows:
            key = str(user_id) if user_id else (str(assigned_id) if assigned_id else None)
            if key:
                converted_by_user[key] = converted_by_user.get(key, 0) + 1

        result = []
        for member, user in members:
            uid = str(user.id)
            assigned = assigned_by_user.get(uid, 0)
            converted = converted_by_user.get(uid, 0)
            # Contagens por status sobre os leads atribuídos a este consultor.
            base = self._leads(from_date, to_date, user_id=user.id)
            contacted = self._count_status(
                base, LeadStatus.CONTATADO, LeadStatus.RESPONDIDO,
                LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA,
                LeadStatus.PROPOSTA_ENVIADA,
            )
            meetings = self._count_status(base, LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA)
            proposals = self._count_status(base, LeadStatus.PROPOSTA_ENVIADA)

            result.append({
                "user_id": uid,
                "name": user.name,
                "email": user.email,
                "assigned_leads": assigned,
                "contacted_leads": contacted,
                "meetings": meetings,
                "proposals_sent": proposals,
                "converted_leads": converted,
                "conversion_rate": round((converted / assigned * 100), 1) if assigned else 0,
            })

        result.sort(key=lambda r: r["converted_leads"], reverse=True)
        return result

    # ---------------------------------------------------------------- leads ranking
    def leads_ranking(
        self,
        sort_by: str = "score",
        campaign_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 20,
    ) -> dict:
        base = self._leads(from_date, to_date)
        if campaign_id:
            base = base.filter(Lead.campaign_id == campaign_id)

        if sort_by == "converted":
            rows = (
                base.join(Conversion, Conversion.lead_id == Lead.id)
                .order_by(Conversion.converted_at.desc())
                .limit(limit)
                .all()
            )
        elif sort_by == "created":
            rows = base.order_by(Lead.created_at.desc()).limit(limit).all()
        else:  # score (default)
            rows = base.order_by(Lead.qualification_score.desc()).limit(limit).all()

        # Conversões por lead (para marcar convertidos no ranking).
        lead_ids = [str(r.id) for r in rows]
        converted_ids = set()
        if lead_ids:
            converted_ids = {
                str(row[0])
                for row in self.db.query(Conversion.lead_id)
                .filter(Conversion.lead_id.in_(lead_ids))
                .all()
            }

        items = []
        for lead in rows:
            items.append({
                "id": str(lead.id),
                "company_name": lead.company_name,
                "city": lead.city,
                "state": lead.state,
                "status": lead.status.value if lead.status else None,
                "qualification_score": lead.qualification_score,
                "campaign_id": str(lead.campaign_id) if lead.campaign_id else None,
                "assigned_to_name": lead.assigned_to.name if lead.assigned_to else None,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "converted": str(lead.id) in converted_ids,
            })
        return {"sort_by": sort_by, "items": items}

    # ---------------------------------------------------------------- geo
    def geo(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> dict:
        base = self._leads(from_date, to_date)

        cities = (
            base.with_entities(
                Lead.city,
                Lead.state,
                func.count(Lead.id),
                func.avg(Lead.qualification_score),
            )
            .group_by(Lead.city, Lead.state)
            .order_by(func.count(Lead.id).desc())
            .all()
        )

        # Convertidos por cidade/estado (fechamentos vinculados à org).
        converted_by_city: dict = {}
        converted_by_state: dict = {}
        conv_rows = (
            self.db.query(Lead.city, Lead.state, Conversion.id)
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .all()
        )
        for city, state, _ in conv_rows:
            ckey = city or "Não informado"
            converted_by_city[ckey] = converted_by_city.get(ckey, 0) + 1
            if state:
                converted_by_state[state] = converted_by_state.get(state, 0) + 1

        city_list = [
            {
                "city": city or "Não informado",
                "state": state,
                "count": count,
                "avg_score": round(float(avg_score), 1) if avg_score else 0,
                "converted": converted_by_city.get(city or "Não informado", 0),
            }
            for city, state, count, avg_score in cities
        ]

        # Agregação por estado (UF).
        states = (
            base.with_entities(
                Lead.state,
                func.count(Lead.id),
                func.avg(Lead.qualification_score),
            )
            .filter(Lead.state.isnot(None))
            .group_by(Lead.state)
            .order_by(func.count(Lead.id).desc())
            .all()
        )
        state_list = [
            {
                "state": state,
                "count": count,
                "avg_score": round(float(avg_score), 1) if avg_score else 0,
                "converted": converted_by_state.get(state, 0),
            }
            for state, count, avg_score in states
        ]
        return {"cities": city_list, "states": state_list}

    # ---------------------------------------------------------------- campaigns
    def campaigns(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list:
        campaigns = self.db.query(Campaign).filter(Campaign.organization_id == self.org_id).all()
        result = []
        for campaign in campaigns:
            base = self.db.query(Lead).filter(
                Lead.organization_id == self.org_id,
                Lead.campaign_id == campaign.id,
            )
            f = _parse_period(from_date)
            t = _parse_period(to_date, end_of_day=True)
            if f:
                base = base.filter(Lead.created_at >= f)
            if t:
                base = base.filter(Lead.created_at <= t)

            total = base.count()
            qualified = self._count_status(base, LeadStatus.QUALIFICADO)
            contacted = self._count_status(base, LeadStatus.CONTATADO)
            meetings = self._count_status(base, LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA)

            converted = (
                self.db.query(func.count(Conversion.id))
                .join(Lead, Conversion.lead_id == Lead.id)
                .filter(Lead.organization_id == self.org_id, Lead.campaign_id == campaign.id)
                .scalar()
            ) or 0
            revenue = (
                self.db.query(func.coalesce(func.sum(Conversion.contract_value), 0))
                .join(Lead, Conversion.lead_id == Lead.id)
                .filter(Lead.organization_id == self.org_id, Lead.campaign_id == campaign.id)
                .scalar()
            ) or 0

            result.append({
                "id": str(campaign.id),
                "name": campaign.name,
                "leads": total,
                "qualified_leads": qualified,
                "contacted_leads": contacted,
                "meetings": meetings,
                "converted_leads": converted,
                "conversion_rate": round((converted / qualified * 100), 1) if qualified else 0,
                "revenue": round(float(revenue), 2),
            })
        result.sort(key=lambda r: r["leads"], reverse=True)
        return result

    # ---------------------------------------------------------------- timeline
    def timeline(
        self,
        group_by: str = "day",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list:
        """Evolução temporal: novos leads, reuniões marcadas e fechados.

        - novos: `Lead.created_at`
        - reuniões: `LeadActivity` STATUS_CHANGED → REUNIAO_MARCADA
        - fechados: `Conversion.converted_at`
        """
        granularity = group_by if group_by in ("day", "week") else "day"
        f = _parse_period(from_date)
        t = _parse_period(to_date, end_of_day=True)

        # Novos leads por bucket.
        new_bucket = func.date_trunc(granularity, Lead.created_at)
        new_q = (
            self.db.query(new_bucket.label("bucket"), func.count(Lead.id))
            .filter(Lead.organization_id == self.org_id)
            .group_by(new_bucket)
        )
        if f:
            new_q = new_q.filter(Lead.created_at >= f)
        if t:
            new_q = new_q.filter(Lead.created_at <= t)

        # Reuniões (status → REUNIAO_MARCADA) por bucket.
        meeting_bucket = func.date_trunc(granularity, LeadActivity.created_at)
        meeting_q = (
            self.db.query(meeting_bucket.label("bucket"), func.count(LeadActivity.id))
            .join(Lead, LeadActivity.lead_id == Lead.id)
            .filter(
                Lead.organization_id == self.org_id,
                LeadActivity.action == LeadActivityAction.STATUS_CHANGED,
                LeadActivity.status_to == LeadStatus.REUNIAO_MARCADA,
            )
            .group_by(meeting_bucket)
        )
        if f:
            meeting_q = meeting_q.filter(LeadActivity.created_at >= f)
        if t:
            meeting_q = meeting_q.filter(LeadActivity.created_at <= t)

        # Fechados por bucket.
        conv_bucket = func.date_trunc(granularity, Conversion.converted_at)
        conv_q = (
            self.db.query(conv_bucket.label("bucket"), func.count(Conversion.id))
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .group_by(conv_bucket)
        )
        if f:
            conv_q = conv_q.filter(Conversion.converted_at >= f)
        if t:
            conv_q = conv_q.filter(Conversion.converted_at <= t)

        series: dict = {}
        for bucket, count in new_q.all():
            key = bucket.isoformat() if bucket else "sem-data"
            series.setdefault(key, {"date": key, "new_leads": 0, "meetings": 0, "closed": 0})
            series[key]["new_leads"] = count
        for bucket, count in meeting_q.all():
            key = bucket.isoformat() if bucket else "sem-data"
            series.setdefault(key, {"date": key, "new_leads": 0, "meetings": 0, "closed": 0})
            series[key]["meetings"] = count
        for bucket, count in conv_q.all():
            key = bucket.isoformat() if bucket else "sem-data"
            series.setdefault(key, {"date": key, "new_leads": 0, "meetings": 0, "closed": 0})
            series[key]["closed"] = count

        ordered = sorted(series.values(), key=lambda r: r["date"])
        return ordered

    # ---------------------------------------------------------------- forecast
    def forecast(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> dict:
        """Forecast ponderado por estágio do funil (Item 4.8).

        Calcula o valor total do pipeline aberto, o forecast ponderado pela
        probabilidade de conversão de cada estágio e a receita já realizada.
        """
        base = self._leads(from_date, to_date)

        revenue = (
            self.db.query(func.coalesce(func.sum(Conversion.contract_value), 0))
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .scalar()
        ) or 0

        open_statuses = list(STAGE_WIN_RATES.keys())
        open_leads = base.filter(Lead.status.in_(open_statuses)).all()

        pipeline_value = sum(float(l.value or 0) for l in open_leads)
        forecast_weighted = sum(
            float(l.value or 0) * STAGE_WIN_RATES.get(l.status, 0.0)
            for l in open_leads
        )

        by_stage = []
        for status, weight in STAGE_WIN_RATES.items():
            leads_in = [l for l in open_leads if l.status == status]
            val = sum(float(l.value or 0) for l in leads_in)
            by_stage.append({
                "stage": status.value,
                "count": len(leads_in),
                "probability": weight,
                "total_value": round(val, 2),
                "weighted_value": round(val * weight, 2),
            })

        lost_reasons = []
        for r in LostReason:
            count = base.filter(
                Lead.status == LeadStatus.PERDIDO,
                Lead.lost_reason == r,
            ).count()
            lost_reasons.append({"reason": r.value, "count": count})
        no_reason = base.filter(
            Lead.status == LeadStatus.PERDIDO,
            Lead.lost_reason.is_(None),
        ).count()
        if no_reason:
            lost_reasons.append({"reason": "SEM_MOTIVO", "count": no_reason})

        return {
            "pipeline_value": round(pipeline_value, 2),
            "forecast_weighted": round(forecast_weighted, 2),
            "realized_revenue": round(float(revenue), 2),
            "open_leads_count": len(open_leads),
            "pipeline_by_stage": by_stage,
            "lost_reasons_breakdown": lost_reasons,
        }
