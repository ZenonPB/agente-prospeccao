"""Serviço de analytics (BI).

Todas as consultas são **org-scoped** (isolamento cross-tenant) e usadas
exclusivamente por ANALYST/MANAGER (owner/admin). Não expõem leads de outras
organizações: cada query filtra por `organization_id`.

Fonte de dados:
- `Lead` (funil, score, atribuição, geo, timeline de criação)
- `Conversion` (fechados, ticket, quem fechou)
- `LeadActivity` (timeline de reuniões via STATUS_CHANGED → REUNIAO_MARCADA)
- `OrganizationMember` (consultores da org)
- `FollowUp`/`Message` (funil ponta-a-ponta — 1º contato e resposta)
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.db.models import (
    Lead,
    LeadStatus,
    Campaign,
    Conversion,
    FollowUp,
    LeadActivity,
    LeadActivityAction,
    Message,
    User,
    OrganizationMember,
    NegotiationStage,
    ContractOutcome,
    LostReason,
    SalesTarget,
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

# ---------------------------------------------------------------------------
# Funil ponta-a-ponta — achados → fechamento.
#
# Cada etapa é "pelo menos": um lead que respondeu também foi prospectado e
# foi achado. Além do status atual (que sai da frente quando o lead vira
# PERDIDO), contamos eventos reais (FollowUp/Message/LeadActivity/Conversion)
# para não perder quem passou pela etapa mas já saiu do funil.
# ---------------------------------------------------------------------------
CONTACTED_STATUSES = (
    LeadStatus.CONTATADO, LeadStatus.RESPONDIDO, LeadStatus.REUNIAO_MARCADA,
    LeadStatus.REUNIAO_FEITA, LeadStatus.PROPOSTA_ENVIADA,
)
RESPONDED_STATUSES = (
    LeadStatus.RESPONDIDO, LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA,
    LeadStatus.PROPOSTA_ENVIADA,
)
MEETING_STATUSES = (
    LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA, LeadStatus.PROPOSTA_ENVIADA,
)

FUNNEL_STAGES = [
    {"key": "achados", "label": "Achados"},
    {"key": "prospectados", "label": "Prospectados (1º contato)"},
    {"key": "responderam", "label": "Responderam"},
    {"key": "reuniao_diagnostica", "label": "Reunião diagnóstica"},
    {"key": "fecharam", "label": "Fecharam negócio"},
]


def build_funnel_stages(counts: dict) -> list:
    """Converte contagens por etapa no funil ponta-a-ponta ordenado, com conversão
    entre etapas e participação sobre o total (função pura — testável)."""
    total = counts.get("achados", 0)
    stages = []
    previous = None
    for stage in FUNNEL_STAGES:
        count = counts.get(stage["key"], 0)
        if previous is None:
            conversion_rate = 100.0
        elif previous == 0:
            conversion_rate = None
        else:
            conversion_rate = round(count / previous * 100, 1)
        stages.append({
            "key": stage["key"],
            "label": stage["label"],
            "count": count,
            "conversion_rate": conversion_rate,
            "share_of_total": round(count / total * 100, 1) if total else 0,
        })
        previous = count
    return stages


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
        # do score por faixa.
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

        # Forecast resumo para o overview
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
            # Funil interno de negociação: estágio
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

    # ---------------------------------------------------------------- funnel ponta-a-ponta
    def funnel(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        campaign_id: Optional[str] = None,
        consultant_id: Optional[str] = None,
    ) -> dict:
        """Funil ponta-a-ponta (achados → fechamento).

        Etapas: achados → prospectados (1º contato) → responderam → reunião
        diagnóstica → fecharam. Filtra por período/campanha/consultor sobre a
        mesma base (org-scoped) usada no overview; a conversão entre etapas
        mostra onde o funil afina/vaza.
        """
        base = self._leads(from_date, to_date, user_id=consultant_id)
        if campaign_id:
            base = base.filter(Lead.campaign_id == campaign_id)

        def _event_lead_ids(model, *criteria):
            """lead_ids (distintos, org-scoped) que têm o evento dado."""
            return (
                self.db.query(model.lead_id)
                .join(Lead, Lead.id == model.lead_id)
                .filter(Lead.organization_id == self.org_id, *criteria)
                .subquery()
            )

        sent_followups = _event_lead_ids(FollowUp, FollowUp.sent_at.isnot(None))
        sent_messages = _event_lead_ids(Message, Message.sent_at.isnot(None))
        response_ids = _event_lead_ids(Message, Message.is_response.is_(True))
        meeting_ids = _event_lead_ids(
            LeadActivity,
            or_(
                and_(
                    LeadActivity.action == LeadActivityAction.STATUS_CHANGED,
                    LeadActivity.status_to == LeadStatus.REUNIAO_MARCADA,
                ),
                LeadActivity.action == LeadActivityAction.MEETING_SCHEDULED,
            ),
        )
        converted_ids = _event_lead_ids(Conversion)

        counts = {
            "achados": base.count(),
            "prospectados": base.filter(
                or_(
                    Lead.status.in_(CONTACTED_STATUSES),
                    Lead.id.in_(sent_followups),
                    Lead.id.in_(sent_messages),
                )
            ).count(),
            "responderam": base.filter(
                or_(
                    Lead.status.in_(RESPONDED_STATUSES),
                    Lead.id.in_(response_ids),
                )
            ).count(),
            "reuniao_diagnostica": base.filter(
                or_(
                    Lead.status.in_(MEETING_STATUSES),
                    Lead.id.in_(meeting_ids),
                )
            ).count(),
            "fecharam": base.filter(Lead.id.in_(converted_ids)).count(),
        }
        return {"total_leads": counts["achados"], "funnel": build_funnel_stages(counts)}

    # ---------------------------------------------------------------- consultants
    def _target_month(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
        """Resolve o mês ("YYYY-MM") da meta conforme o período consultado.

        Prioriza `to_date` → `from_date` → mês atual. Itens 4.9: metas são
        mensais (`sales_targets.month`).
        """
        anchor = to_date or from_date
        if anchor and len(anchor) >= 7:
            return anchor[:7]
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _targets_by_user(self, month: str) -> dict:
        """Metas mensais (reuniões/receita) por user_id para a org."""
        rows = (
            self.db.query(SalesTarget)
            .filter(
                SalesTarget.organization_id == self.org_id,
                SalesTarget.month == month,
            )
            .all()
        )
        return {
            str(t.user_id): {
                "meetings_target": t.meetings_target or 0,
                "revenue_target": float(t.revenue_target or 0),
            }
            for t in rows
        }

    def consultants(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list:
        """Métricas por consultor: atribuídos, contatados, reuniões, propostas,
        convertidos, conversão % e atingimento da meta mensal."""
        month = self._target_month(from_date, to_date)
        targets = self._targets_by_user(month)
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
        revenue_by_user: dict = {}
        conv_rows = (
            self.db.query(
                Conversion.user_id,
                Conversion.assigned_to_id,
                Conversion.id,
                Conversion.contract_value,
            )
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .all()
        )
        for user_id, assigned_id, _, contract_value in conv_rows:
            key = str(user_id) if user_id else (str(assigned_id) if assigned_id else None)
            if key:
                converted_by_user[key] = converted_by_user.get(key, 0) + 1
                revenue_by_user[key] = revenue_by_user.get(key, 0) + float(contract_value or 0)

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
            revenue = revenue_by_user.get(uid, 0)

            tgt = targets.get(uid, {"meetings_target": 0, "revenue_target": 0.0})
            meetings_target = tgt["meetings_target"]
            revenue_target = tgt["revenue_target"]

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
                # Metas mensais e atingimento (%).
                "revenue_realized": round(revenue, 2),
                "meetings_target": meetings_target,
                "revenue_target": revenue_target,
                "meetings_attainment": round((meetings / meetings_target * 100), 1) if meetings_target else None,
                "revenue_attainment": round((revenue / revenue_target * 100), 1) if revenue_target else None,
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
        """Forecast ponderado por estágio do funil.

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

    # ---------------------------------------------------------------- threshold
    def suggest_qualification_threshold(
        self,
        current_threshold: int = 60,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> dict:
        """Sugere um limiar QUALIFICADO/DESQUALIFICADO com base no histórico
        da org. Avalia thresholds candidatos de 30 a 90 (passo 5) e escolhe
        o que maximiza a pontuação F1 sobre os leads convertidos vs. todos os
        qualificados.

        Lê leads pontuados + conversões da org no período e delega o cálculo
        para `compute_threshold_candidates` (pura, testável sem DB).
        """
        base = self._leads(from_date, to_date).filter(
            Lead.qualification_score.isnot(None),
        )
        rows = base.with_entities(
            Lead.qualification_score,
            Lead.id.label("lead_id"),
        ).all()
        scored = [(int(r.qualification_score or 0), str(r.lead_id)) for r in rows]

        converted_sub = (
            self.db.query(Conversion.lead_id)
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .subquery()
        )
        converted_ids = {
            r[0] for r in self.db.query(converted_sub.c.lead_id).all()
        }

        return compute_threshold_candidates(
            scored=scored,
            converted_ids=converted_ids,
            current_threshold=current_threshold,
        )

    # ---------------------------------------------------------------- A/B
    def message_variants(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> dict:
        """Desempenho por variante A/B de cadência.

        Usa `messages.variant` (uma linha por envio) — o que remove o proxy
        por `FollowUp.variant` que misturava aberturas/cliques de etapas
        distintas. Soma, por variante da org no período:
        - `sent`: mensagens efetivamente enviadas (não respostas).
        - `opened`: mensagens com `opened_at` registrado.
        - `clicked`: mensagens com `clicked_at` registrado.
        - `responded`: mensagens `is_response=True` da org — criadas pelo
          inbound com a variante da última mensagem enviada antes da resposta.
        """
        f = _parse_period(from_date)
        t = _parse_period(to_date, end_of_day=True)

        msg_base = (
            self.db.query(Message)
            .join(Lead, Message.lead_id == Lead.id)
            .filter(
                Lead.organization_id == self.org_id,
                Message.variant.isnot(None),
                Message.sent_at.isnot(None),
            )
        )
        if f:
            msg_base = msg_base.filter(Message.sent_at >= f)
        if t:
            msg_base = msg_base.filter(Message.sent_at <= t)

        rows = msg_base.with_entities(
            Message.variant,
            Message.tracking_token,
            Message.opened_at,
            Message.clicked_at,
            Message.is_response,
        ).all()

        by_variant: dict = {}
        for variant, token, opened_at, clicked_at, is_response in rows:
            v = (variant or "").strip().upper() or "(sem variante)"
            bucket = by_variant.setdefault(v, {
                "variant": v,
                "sent": 0,
                "opened": 0,
                "clicked": 0,
                "responded": 0,
            })
            if is_response:
                bucket["responded"] += 1
                continue
            bucket["sent"] += 1
            if opened_at is not None:
                bucket["opened"] += 1
            if clicked_at is not None:
                bucket["clicked"] += 1

        variants = []
        for v in sorted(by_variant.keys()):
            row = by_variant[v]
            sent = row["sent"] or 0
            row["open_rate"] = round((row["opened"] / sent) * 100, 1) if sent else 0
            row["click_rate"] = round((row["clicked"] / sent) * 100, 1) if sent else 0
            row["response_rate"] = round((row["responded"] / sent) * 100, 1) if sent else 0
            variants.append(row)

        return {"variants": variants}


def compute_threshold_candidates(
    scored: list,
    converted_ids: set,
    current_threshold: int = 60,
) -> dict:
    """Calcula o threshold ótimo a partir de (score, lead_id) e ids convertidos.

    Função pura — testável sem banco. Recebe os dados já lidos pelo service.
    Retorna a recomendação, candidatos (30–90 passo 5) com precisão/revisão/F1,
    e a `rationale` exibida na UI.

    Guarda de volume: se o histórico for pequeno (poucos leads ou zero
    conversões), a métrica F1 é ruidosa e a "recomendação" pode ser
    enganosa. Nesses casos mantemos o limiar atual e devolvemos uma
    `rationale` explicando o motivo.
    """
    MIN_LEADS = 5
    MIN_CONVERSIONS = 1

    if not scored:
        return {
            "recommended_threshold": current_threshold,
            "current_threshold": current_threshold,
            "candidates": [],
            "rationale": "Sem leads pontuados no período — mantenha o limiar atual.",
            "leads_considered": 0,
            "converted_total": 0,
        }

    total = len(scored)
    total_converted = sum(1 for _, lid in scored if lid in converted_ids)

    if total < MIN_LEADS or total_converted < MIN_CONVERSIONS:
        return {
            "recommended_threshold": current_threshold,
            "current_threshold": current_threshold,
            "candidates": [],
            "rationale": (
                f"Volume insuficiente para calibrar ({total} leads e "
                f"{total_converted} conversões no período; mínimo "
                f"{MIN_LEADS}/{MIN_CONVERSIONS}). Mantenha o limiar atual."
            ),
            "leads_considered": total,
            "converted_total": total_converted,
        }

    candidates: list = []
    best_threshold = current_threshold
    best_f1 = -1.0
    for threshold in range(30, 95, 5):
        qualified = [lid for s, lid in scored if s >= threshold]
        qualified_converted = sum(1 for lid in qualified if lid in converted_ids)
        precision = (qualified_converted / len(qualified)) if qualified else 0.0
        recall = (qualified_converted / total_converted) if total_converted else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )
        candidates.append({
            "threshold": threshold,
            "qualified": len(qualified),
            "qualified_converted": qualified_converted,
            "precision": round(precision * 100, 1),
            "recall": round(recall * 100, 1),
            "f1": round(f1 * 100, 1),
        })
        # Empate de F1 prefere o limiar atual para evitar "saltos" sem evidência.
        if f1 > best_f1 or (f1 == best_f1 and threshold == current_threshold):
            best_f1 = f1
            best_threshold = threshold

    rationale = (
        f"Limiar {best_threshold} maximiza o F1 do funil da org no "
        f"período ({round(best_f1 * 100, 1)}% sobre {total} leads e "
        f"{total_converted} conversões)."
    )
    return {
        "recommended_threshold": best_threshold,
        "current_threshold": current_threshold,
        "candidates": candidates,
        "rationale": rationale,
        "leads_considered": total,
        "converted_total": total_converted,
    }
