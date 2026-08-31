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
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from src.db.models import (
    Lead,
    LeadStatus,
    Campaign,
    Conversion,
    FollowUp,
    FollowUpStep,
    LeadActivity,
    LeadActivityAction,
    Message,
    MessageChannel,
    User,
    OrganizationMember,
    NegotiationStage,
    ContractOutcome,
    LostReason,
    SalesTarget,
    EmailSuppression,
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

        status_counts = dict(
            base.with_entities(Lead.status, func.count(Lead.id))
            .group_by(Lead.status)
            .all()
        )
        total = sum(status_counts.values())

        qualified = status_counts.get(LeadStatus.QUALIFICADO, 0)
        contacted = status_counts.get(LeadStatus.CONTATADO, 0)
        responded = status_counts.get(LeadStatus.RESPONDIDO, 0)
        meetings = status_counts.get(LeadStatus.REUNIAO_MARCADA, 0) + status_counts.get(LeadStatus.REUNIAO_FEITA, 0)
        proposals = status_counts.get(LeadStatus.PROPOSTA_ENVIADA, 0)

        funnel = [
            {"stage": s.value, "count": status_counts.get(s, 0)}
            for s in (
                LeadStatus.NOVO, LeadStatus.ANALISADO, LeadStatus.QUALIFICADO,
                LeadStatus.DESQUALIFICADO, LeadStatus.CONTATADO, LeadStatus.RESPONDIDO,
                LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA,
                LeadStatus.PROPOSTA_ENVIADA, LeadStatus.PERDIDO,
            )
        ]

        conv_agg = (
            self.db.query(
                func.count(Conversion.id),
                func.coalesce(func.sum(Conversion.contract_value), 0),
            )
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .one()
        )
        converted = conv_agg[0]
        revenue = conv_agg[1]

        score_bands = []
        # Score bands via CASE WHEN em SQL (P1-7): 1 query em vez de 8.
        band_query = base.with_entities(
            func.sum(func.case(
                (Lead.qualification_score.between(0, 39), 1), else_=0
            )).label("b0"),
            func.sum(func.case(
                (Lead.qualification_score.between(40, 59), 1), else_=0
            )).label("b1"),
            func.sum(func.case(
                (Lead.qualification_score.between(60, 79), 1), else_=0
            )).label("b2"),
            func.sum(func.case(
                (Lead.qualification_score.between(80, 100), 1), else_=0
            )).label("b3"),
        ).one()
        band_counts = [band_query.b0 or 0, band_query.b1 or 0, band_query.b2 or 0, band_query.b3 or 0]

        # Convertidos por faixa: query separada (precisa JOIN com Conversion).
        conv_sub = (
            base.join(Conversion, Conversion.lead_id == Lead.id, isouter=True)
            .with_entities(
                func.sum(func.case(
                    (Lead.qualification_score.between(0, 39) & Conversion.id.isnot(None), 1), else_=0
                )).label("c0"),
                func.sum(func.case(
                    (Lead.qualification_score.between(40, 59) & Conversion.id.isnot(None), 1), else_=0
                )).label("c1"),
                func.sum(func.case(
                    (Lead.qualification_score.between(60, 79) & Conversion.id.isnot(None), 1), else_=0
                )).label("c2"),
                func.sum(func.case(
                    (Lead.qualification_score.between(80, 100) & Conversion.id.isnot(None), 1), else_=0
                )).label("c3"),
            ).one()
        )
        band_converted = [conv_sub.c0 or 0, conv_sub.c1 or 0, conv_sub.c2 or 0, conv_sub.c3 or 0]

        for idx, (lo, hi, label) in enumerate(SCORE_BANDS):
            bc = band_counts[idx]
            bcv = band_converted[idx]
            score_bands.append({
                "band": label,
                "count": bc,
                "converted": bcv,
                "conversion_rate": round((bcv / bc * 100), 1) if bc else 0,
            })

        open_statuses = list(STAGE_WIN_RATES.keys())
        pipeline_val = (
            base.filter(Lead.status.in_(open_statuses))
            .with_entities(func.coalesce(func.sum(Lead.value), 0))
            .scalar()
        )
        # Forecast ponderado: CASE WHEN por estágio em SQL.
        forecast_cases = [
            func.sum(
                func.case(
                    (Lead.status == status, Lead.value * weight),
                    else_=0,
                )
            )
            for status, weight in STAGE_WIN_RATES.items()
        ]
        forecast_val = (
            base.filter(Lead.status.in_(open_statuses))
            .with_entities(*forecast_cases)
            .one()
        )
        forecast_val = sum(float(v or 0) for v in forecast_val)

        negotiation_counts = dict(
            base.with_entities(Lead.negotiation_stage, func.count(Lead.id))
            .filter(Lead.negotiation_stage.isnot(None))
            .group_by(Lead.negotiation_stage)
            .all()
        )
        contract_counts = dict(
            base.with_entities(Lead.contract_outcome, func.count(Lead.id))
            .filter(Lead.contract_outcome.isnot(None))
            .group_by(Lead.contract_outcome)
            .all()
        )

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
            "negotiation_distribution": [
                {"stage": s.value, "count": negotiation_counts.get(s, 0)}
                for s in NegotiationStage
            ],
            "contracts_by_outcome": [
                {"outcome": o.value, "count": contract_counts.get(o, 0)}
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
    def _consultant_planilha(
        self,
        user_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        assigned_leads: Optional[int] = None,
    ) -> dict:
        """KPIs da planilha Alphamec para um consultor.

        Efetua consultas específicas do usuário: pitch enviado (abertura da
        cadência), respostas (inbound), estágio de negociação, resultado do
        contrato, ticket médio, tempo de cadência e de fechamento e canal de
        contato. Tudo org-scoped (leads atribuídos ao consultor).
        """
        f = _parse_period(from_date)
        t = _parse_period(to_date, end_of_day=True)
        uid = user_id

        # Abertura (pitch) efetivamente enviada.
        pitch_q = (
            self.db.query(func.count(FollowUp.id))
            .join(Lead, FollowUp.lead_id == Lead.id)
            .filter(
                Lead.organization_id == self.org_id,
                Lead.assigned_to_id == uid,
                FollowUp.step == FollowUpStep.OPENING,
                FollowUp.sent_at.isnot(None),
            )
        )
        if f:
            pitch_q = pitch_q.filter(FollowUp.sent_at >= f)
        if t:
            pitch_q = pitch_q.filter(FollowUp.sent_at <= t)
        pitch_sent = pitch_q.scalar() or 0

        # Respostas via inbound (`Message.is_response`), leads distintos.
        resp_q = (
            self.db.query(func.count(func.distinct(Message.lead_id)))
            .join(Lead, Message.lead_id == Lead.id)
            .filter(
                Lead.organization_id == self.org_id,
                Lead.assigned_to_id == uid,
                Message.is_response.is_(True),
            )
        )
        if f:
            resp_q = resp_q.filter(Message.sent_at >= f)
        if t:
            resp_q = resp_q.filter(Message.sent_at <= t)
        responded_leads = resp_q.scalar() or 0

        # Estágio de negociação e resultado de contrato — GROUP BY em vez de .all().
        base_leads = self._leads(from_date, to_date, user_id=uid)
        contract_counts = dict(
            base_leads.filter(Lead.contract_outcome.isnot(None))
            .with_entities(Lead.contract_outcome, func.count(Lead.id))
            .group_by(Lead.contract_outcome)
            .all()
        )
        negotiation = dict(
            base_leads.filter(Lead.negotiation_stage.isnot(None))
            .with_entities(Lead.negotiation_stage, func.count(Lead.id))
            .group_by(Lead.negotiation_stage)
            .all()
        )
        contract_outcomes = {o.value: contract_counts.get(o, 0) for o in ContractOutcome}
        contracts_total = sum(contract_outcomes.values())
        contracts_approved = contract_outcomes.get(ContractOutcome.APROVADO.value, 0)

        # Conversões: ticket médio + tempo de fechamento.
        conv_rows = (
            self.db.query(Conversion.contract_value, Conversion.time_to_close_days)
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(
                Lead.organization_id == self.org_id,
                or_(Lead.assigned_to_id == uid, Conversion.user_id == uid),
            )
            .all()
        )
        ticket_sum = sum(float(c) or 0 for c, _ in conv_rows)
        ticket_count = len(conv_rows)
        close_days = [int(d) for _, d in conv_rows if d]

        # Cadência: intervalo abertura → resposta por lead (média).
        pitch_by_lead = {
            str(lid): sent_at
            for lid, sent_at in (
                self.db.query(FollowUp.lead_id, func.min(FollowUp.sent_at))
                .join(Lead, FollowUp.lead_id == Lead.id)
                .filter(
                    Lead.organization_id == self.org_id,
                    Lead.assigned_to_id == uid,
                    FollowUp.step == FollowUpStep.OPENING,
                    FollowUp.sent_at.isnot(None),
                )
                .group_by(FollowUp.lead_id)
                .all()
            )
        }
        responded_by_lead = {
            str(lid): resp_at
            for lid, resp_at in (
                self.db.query(Message.lead_id, func.min(Message.sent_at))
                .join(Lead, Message.lead_id == Lead.id)
                .filter(
                    Lead.organization_id == self.org_id,
                    Lead.assigned_to_id == uid,
                    Message.is_response.is_(True),
                )
                .group_by(Message.lead_id)
                .all()
            )
        }
        cadence_days = [
            interval_days(pitch_at, responded_by_lead[lid])
            for lid, pitch_at in pitch_by_lead.items()
            if lid in responded_by_lead
        ]

        # Canal de contato: distribuição das mensagens enviadas.
        channel_dist = {c.value: 0 for c in MessageChannel}
        for channel, count in (
            self.db.query(Message.channel, func.count(Message.id))
            .join(Lead, Message.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id, Lead.assigned_to_id == uid)
            .group_by(Message.channel)
            .all()
        ):
            if channel:
                channel_dist[channel.value] = count

        if assigned_leads is None:
            assigned_leads = (
                self.db.query(func.count(Lead.id))
                .filter(Lead.organization_id == self.org_id, Lead.assigned_to_id == uid)
                .scalar()
                or 0
            )

        kpis = build_planilha_kpis(
            assigned_leads=assigned_leads,
            pitch_sent=pitch_sent,
            responded_leads=responded_leads,
            contracts_approved=contracts_approved,
            contracts_total=contracts_total,
            ticket_sum=ticket_sum,
            ticket_count=ticket_count,
            cadence_days=cadence_days,
            close_days=close_days,
        )
        return {
            **kpis,
            "pitch_sent": pitch_sent,
            "responded_leads": responded_leads,
            "contracts_approved": contracts_approved,
            "contracts_total": contracts_total,
            "ticket_count": ticket_count,
            "cadence_days_n": len(cadence_days),
            "close_days_n": len(close_days),
            "negotiation_distribution": [
                {"stage": k, "count": v} for k, v in negotiation.items()
            ],
            "contracts_by_outcome": [
                {"outcome": k, "count": v} for k, v in contract_outcomes.items()
            ],
            "channel_distribution": [
                {"channel": k, "count": v} for k, v in channel_dist.items()
            ],
        }

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

            planilha = self._consultant_planilha(
                uid, from_date=from_date, to_date=to_date, assigned_leads=assigned,
            )

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
                # KPIs da planilha Alphamec.
                **planilha,
            })

        result.sort(key=lambda r: r["converted_leads"], reverse=True)
        return result

    def consultant_detail(
        self,
        user_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Optional[dict]:
        """Perfil de um consultor: KPIs da planilha + funil ponta-a-ponta.

        Usado na tela `/relatorios/consultores/[id]`. Retorna `None` quando o
        usuário não é membro ativo da org (o caller responde 404).
        """
        row = (
            self.db.query(OrganizationMember, User)
            .join(User, OrganizationMember.user_id == User.id)
            .filter(
                OrganizationMember.organization_id == self.org_id,
                User.id == user_id,
            )
            .first()
        )
        if row is None:
            return None
        member, user = row

        assigned = (
            self.db.query(func.count(Lead.id))
            .filter(Lead.organization_id == self.org_id, Lead.assigned_to_id == user.id)
            .scalar()
            or 0
        )
        planilha = self._consultant_planilha(
            str(user.id), from_date=from_date, to_date=to_date, assigned_leads=assigned,
        )
        funnel = self.funnel(
            from_date=from_date, to_date=to_date, consultant_id=str(user.id),
        )
        return {
            "user_id": str(user.id),
            "name": user.name,
            "email": user.email,
            "sales_role": member.sales_role.value if member.sales_role else None,
            "assigned_leads": assigned,
            **planilha,
            "funnel": funnel,
        }

    def consultant_activity(
        self,
        user_id: str,
        limit: int = 50,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list:
        """Trilha recente de um consultor.

        Atividades (LeadActivity) dos leads atribuídos a ele OU executadas por
        ele — org-scoped, mais recentes primeiro. Compõe a aba "Atividades" do
        perfil do consultor. Aceita período via `from_date`/`to_date`.
        """
        f = _parse_period(from_date)
        t = _parse_period(to_date, end_of_day=True)
        activity_filter = or_(
            Lead.assigned_to_id == user_id,
            LeadActivity.user_id == user_id,
        )
        if f:
            activity_filter = and_(activity_filter, LeadActivity.created_at >= f)
        if t:
            activity_filter = and_(activity_filter, LeadActivity.created_at <= t)
        rows = (
            self.db.query(LeadActivity, Lead)
            .join(Lead, LeadActivity.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id, activity_filter)
            .order_by(LeadActivity.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(activity.id),
                "action": activity.action.value,
                "detail": activity.detail,
                "status_from": activity.status_from.value if activity.status_from else None,
                "status_to": activity.status_to.value if activity.status_to else None,
                "user_id": str(activity.user_id) if activity.user_id else None,
                "created_at": activity.created_at.isoformat() if activity.created_at else None,
                "lead_id": str(activity.lead_id),
                "company_name": lead.company_name,
            }
            for activity, lead in rows
        ]

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
                .options(joinedload(Lead.assigned_to))
                .order_by(Conversion.converted_at.desc())
                .limit(limit)
                .all()
            )
        elif sort_by == "created":
            rows = base.options(joinedload(Lead.assigned_to)).order_by(Lead.created_at.desc()).limit(limit).all()
        else:  # score (default)
            rows = base.options(joinedload(Lead.assigned_to)).order_by(Lead.qualification_score.desc()).limit(limit).all()

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
        f = _parse_period(from_date)
        t = _parse_period(to_date, end_of_day=True)

        # Agregação GROUP BY campaign_id para todos os KPIs de uma vez.
        lead_base = self.db.query(Lead).filter(Lead.organization_id == self.org_id)
        if f:
            lead_base = lead_base.filter(Lead.created_at >= f)
        if t:
            lead_base = lead_base.filter(Lead.created_at <= t)

        stats_rows = (
            lead_base.with_entities(
                Lead.campaign_id,
                func.count(Lead.id),
                func.sum(func.case((Lead.status == LeadStatus.QUALIFICADO, 1), else_=0)),
                func.sum(func.case((Lead.status == LeadStatus.CONTATADO, 1), else_=0)),
                func.sum(func.case((Lead.status.in_(
                    (LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA)
                ), 1), else_=0)),
            )
            .group_by(Lead.campaign_id)
            .all()
        )
        stats_by_campaign = {str(row[0]): {
            "total": row[1], "qualified": row[2] or 0,
            "contacted": row[3] or 0, "meetings": row[4] or 0,
        } for row in stats_rows}

        # Conversões por campanha.
        conv_rows = (
            self.db.query(
                Lead.campaign_id,
                func.count(Conversion.id),
                func.coalesce(func.sum(Conversion.contract_value), 0),
            )
            .join(Lead, Conversion.lead_id == Lead.id)
            .filter(Lead.organization_id == self.org_id)
            .group_by(Lead.campaign_id)
            .all()
        )
        conv_by_campaign = {str(row[0]): {"converted": row[1], "revenue": row[2]}
                            for row in conv_rows}

        result = []
        for campaign in campaigns:
            cid = str(campaign.id)
            s = stats_by_campaign.get(cid, {"total": 0, "qualified": 0, "contacted": 0, "meetings": 0})
            c = conv_by_campaign.get(cid, {"converted": 0, "revenue": 0})
            qualified = s["qualified"]
            result.append({
                "id": cid,
                "name": campaign.name,
                "leads": s["total"],
                "qualified_leads": qualified,
                "contacted_leads": s["contacted"],
                "meetings": s["meetings"],
                "converted_leads": c["converted"],
                "conversion_rate": round((c["converted"] / qualified * 100), 1) if qualified else 0,
                "revenue": round(float(c["revenue"]), 2),
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

        lost_counts = dict(
            base.filter(Lead.status == LeadStatus.PERDIDO)
            .with_entities(Lead.lost_reason, func.count(Lead.id))
            .group_by(Lead.lost_reason)
            .all()
        )
        lost_reasons = [{"reason": r.value, "count": lost_counts.get(r, 0)} for r in LostReason]
        no_reason = lost_counts.get(None, 0)
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

    # ---------------------------------------------------------------- deliverability
    def check_email_deliverability(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> dict:
        """Verifica saúde de entregabilidade de e-mail da organização.

        Calcula taxa de bounce no período e retorna alerta se exceder o limiar
        de 5%. O scheduler (main.py) pode chamar periodicamente para pausar
        `auto_send_email` e notificar o owner.

        Retorna:
        - `bounce_rate`: % de bounces / envios no período
        - `sent_today`: e-mails enviados hoje
        - `bounced_today`: bounces permanentes hoje
        - `suppressed_count`: total de e-mails na lista de supressão
        - `should_pause`: True se bounce_rate > 5%
        - `alert_message`: mensagem de alerta se should_pause
        """
        from datetime import datetime, timezone
        from sqlalchemy import func

        # Período padrão: últimos 7 dias
        if from_date:
            try:
                start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
            except ValueError:
                start = None
        else:
            start = datetime.now(timezone.utc) - timedelta(days=7)

        if to_date:
            try:
                end = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc)
            except ValueError:
                end = None
        else:
            end = datetime.now(timezone.utc)

        if not start or not end:
            start = datetime.now(timezone.utc) - timedelta(days=7)
            end = datetime.now(timezone.utc)

        # Conta envios no período (Messages do canal EMAIL)
        sent_query = self.db.query(func.count(Message.id)).join(
            Lead, Message.lead_id == Lead.id
        ).filter(
            Lead.organization_id == self.org_id,
            Message.channel == MessageChannel.EMAIL,
            Message.sent_at >= start,
            Message.sent_at <= end,
        )
        sent_count = sent_query.scalar() or 0

        # Conta bounces permanentes no período, restritos à organização.
        # A coluna `organization_id` em email_suppressions evita misturar
        # bounces de workspaces diferentes no alerta de entregabilidade.
        bounced_query = self.db.query(func.count(EmailSuppression.id)).filter(
            EmailSuppression.organization_id == self.org_id,
            EmailSuppression.created_at >= start,
            EmailSuppression.created_at <= end,
        )
        bounced_count = bounced_query.scalar() or 0

        # Total suprimidos (só desta organização)
        suppressed_total = self.db.query(func.count(EmailSuppression.id)).filter(
            EmailSuppression.organization_id == self.org_id,
        ).scalar() or 0

        # Hoje (em UTC)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = self.db.query(func.count(Message.id)).join(
            Lead, Message.lead_id == Lead.id
        ).filter(
            Lead.organization_id == self.org_id,
            Message.channel == MessageChannel.EMAIL,
            Message.sent_at >= today_start,
        ).scalar() or 0

        bounced_today = self.db.query(func.count(EmailSuppression.id)).filter(
            EmailSuppression.organization_id == self.org_id,
            EmailSuppression.created_at >= today_start,
        ).scalar() or 0

        bounce_rate = (bounced_count / sent_count * 100) if sent_count > 0 else 0.0
        should_pause = bounce_rate > 5.0

        return {
            "bounce_rate": round(bounce_rate, 2),
            "sent_in_period": sent_count,
            "bounced_in_period": bounced_count,
            "sent_today": sent_today,
            "bounced_today": bounced_today,
            "suppressed_count": suppressed_total,
            "should_pause": should_pause,
            "alert_message": (
                f"Muitos e-mails estão voltando sem chegar ({bounce_rate:.1f}%). "
                f"Por segurança, o envio automático foi pausado para proteger a "
                f"reputação do seu e-mail. Revise a lista de contatos antes de reativar."
            ) if should_pause else None,
            "period": {
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
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

    # ------------------------------------------------- aprendizado da vertente
    def template_insights(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        campaign_id: Optional[str] = None,
    ) -> dict:
        """Correlaciona características (`score_factors[]`) de leads convertidos
        × perdidos e sugere ajustes de peso por frequência relativa.

        Para cada característica com amostra suficiente compara a taxa em que
        aparece entre convertidos e perdidos: sobre-representada nos perdidos →
        sugere reduzir o peso; nos convertidos → reforçar. Ajuste é sugestão
        (nunca automático) — a calibração continua sendo decisão humana no
        editor da vertente.
        """
        f = _parse_period(from_date)
        t = _parse_period(to_date, end_of_day=True)

        def _perioded(q):
            if f:
                q = q.filter(Lead.created_at >= f)
            if t:
                q = q.filter(Lead.created_at <= t)
            if campaign_id:
                q = q.filter(Lead.campaign_id == campaign_id)
            return q

        lost_q = _perioded(
            self.db.query(Lead.score_factors)
            .filter(
                Lead.organization_id == self.org_id,
                Lead.status == LeadStatus.PERDIDO,
                Lead.score_factors.isnot(None),
            )
        )
        converted_q = _perioded(
            self.db.query(Lead.score_factors)
            .join(Conversion, Conversion.lead_id == Lead.id)
            .filter(
                Lead.organization_id == self.org_id,
                Lead.score_factors.isnot(None),
            )
        )

        return compute_signal_insights(
            converted_factors=[r[0] for r in converted_q.all()],
            lost_factors=[r[0] for r in lost_q.all()],
        )


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


# ---------------------------------------------------------------------------
# KPIs da planilha Alphamec por consultor.
# Funções puras — testáveis sem banco.
# ---------------------------------------------------------------------------

# Amostra mínima por característica para a sugestão ter valor estatístico.
INSIGHT_MIN_OCCURRENCES = 3
# Diferença mínima (pontos percentuais) entre as taxas convertidos × perdidos.
INSIGHT_MIN_GAP_PP = 15.0


def compute_signal_insights(
    converted_factors: list,
    lost_factors: list,
    min_occurrences: int = INSIGHT_MIN_OCCURRENCES,
    min_gap_pp: float = INSIGHT_MIN_GAP_PP,
) -> dict:
    """Sugestões de calibração de vertente por frequência relativa.

    `converted_factors` / `lost_factors`: listas do JSONB `score_factors[]`
    (cada item um dict com `label`). Normaliza o rótulo (lowercase, sem
    espaços extras) para agrupar variações da mesma característica.

    Retorna insights ordenados pela força do desvio: `reforcado` quando a
    característica aparece proporcionalmente mais entre convertidos,
    `reduzir` quando mais entre perdidos, `neutro` dentro da margem.
    """
    def _labels(factor_list):
        labels = []
        for factors in factor_list or []:
            if not isinstance(factors, list):
                continue
            seen_in_lead: set = set()
            for f in factors:
                if not isinstance(f, dict):
                    continue
                label = str(f.get("label") or "").strip().lower()
                if label and label not in seen_in_lead:
                    seen_in_lead.add(label)
            labels.extend(seen_in_lead)
        return labels

    converted_labels = _labels(converted_factors)
    lost_labels = _labels(lost_factors)

    converted_leads = sum(1 for fl in converted_factors or [] if isinstance(fl, list))
    lost_leads = sum(1 for fl in lost_factors or [] if isinstance(fl, list))

    from collections import Counter

    conv_counter = Counter(converted_labels)
    lost_counter = Counter(lost_labels)

    # Sem base dos dois lados a taxa é enganosa (1 conversão = 100%).
    if converted_leads < min_occurrences or lost_leads < min_occurrences:
        return {
            "insights": [],
            "converted_total": converted_leads,
            "lost_total": lost_leads,
            "min_occurrences": min_occurrences,
            "min_gap_pp": min_gap_pp,
            "rationale": (
                f"Amostra pequena ({converted_leads} convertidos × {lost_leads} "
                f"perdidos; mínimo {min_occurrences} de cada). As sugestões "
                "aparecem conforme o time trabalha mais leads."
            ),
        }

    insights = []
    for label in sorted(set(conv_counter) | set(lost_counter)):
        c_count = conv_counter.get(label, 0)
        l_count = lost_counter.get(label, 0)
        if c_count + l_count < min_occurrences:
            continue
        c_rate = compute_rate(c_count, converted_leads)
        l_rate = compute_rate(l_count, lost_leads)
        gap = round(c_rate - l_rate, 1)
        if abs(gap) < min_gap_pp:
            suggestion = "neutro"
        elif gap > 0:
            suggestion = "reforcar"
        else:
            suggestion = "reduzir"
        insights.append({
            "label": label,
            "converted": c_count,
            "lost": l_count,
            "converted_rate": c_rate,
            "lost_rate": l_rate,
            "gap_pp": gap,
            "suggestion": suggestion,
        })

    insights.sort(key=lambda i: -abs(i["gap_pp"]))
    return {
        "insights": insights,
        "converted_total": converted_leads,
        "lost_total": lost_leads,
        "min_occurrences": min_occurrences,
        "min_gap_pp": min_gap_pp,
        "rationale": (
            f"Base: {converted_leads} convertidos × {lost_leads} perdidos. "
            "Características com amostra pequena ficam de fora; sugestões não "
            "alteram pesos automaticamente."
        ),
    }


def compute_rate(part: float, whole: float) -> float:
    """Porcentagem (0–100, 1 casa) de `part` sobre `whole`. 0 quando `whole` é 0."""
    return round(part / whole * 100, 1) if whole else 0.0


def mean(values: list) -> float:
    """Média aritmética simples (0 quando lista vazia)."""
    return sum(values) / len(values) if values else 0.0


def interval_days(start, end) -> int:
    """Dias decorridos entre `start` e `end` (mínimo 0; tolera naive/None).

    Usado para cadência (pitch → resposta) e avaliação do tempo de ciclo.
    """
    if not start or not end:
        return 0
    s = start if getattr(start, "tzinfo", None) else start.replace(tzinfo=timezone.utc)
    e = end if getattr(end, "tzinfo", None) else end.replace(tzinfo=timezone.utc)
    return max(0, int((e - s).total_seconds() // 86400))


def build_planilha_kpis(
    *,
    assigned_leads: int,
    pitch_sent: int,
    responded_leads: int,
    contracts_approved: int,
    contracts_total: int,
    ticket_sum: float,
    ticket_count: int,
    cadence_days: list,
    close_days: list,
) -> dict:
    """Compacta os KPIs da planilha em um dict pronto para a UI.

    - `pitch_rate`: % de leads de carteira com abertura (pitch) enviada.
    - `response_rate`: % de pitches enviados que receberam resposta.
    - `contract_approval_rate`: % de contratos registrados aprovados.
    - `ticket_medio`: média dos valores de conversão.
    - `avg_cadence_days`: média do intervalo pitch → resposta (dias).
    - `avg_close_days`: média do `Conversion.time_to_close_days`.
    """
    return {
        "pitch_rate": compute_rate(pitch_sent, assigned_leads),
        "response_rate": compute_rate(responded_leads, pitch_sent),
        "contract_approval_rate": compute_rate(contracts_approved, contracts_total),
        "ticket_medio": round(ticket_sum / ticket_count, 2) if ticket_count else 0.0,
        "avg_cadence_days": round(mean(cadence_days), 1) if cadence_days else 0.0,
        "avg_close_days": round(mean(close_days), 1) if close_days else 0.0,
    }
