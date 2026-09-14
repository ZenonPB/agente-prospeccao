"""Bloco C — learning calibrado e coaching comercial baseado em evidência.

O módulo é deliberadamente human-in-the-loop. Ele nunca publica pesos sozinho:
mede resultados atribuídos, simula um OfferProfile candidato sobre o mesmo
histórico observado, persiste a comparação e reutiliza o fluxo explícito de
aprovação/publicação/rollback já existente.

Regras importantes:
- somente outcomes atribuídos à oportunidade correta entram na calibração;
- ausência de sinal continua UNKNOWN, nunca vira FALSE no replay;
- recomendações de coaching descrevem associação observada, não causalidade;
- todo cálculo é tenant-scoped por ``organization_id``.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import (
    CommercialComparison,
    CommercialOutcomeRow,
    Lead,
    LeadActivity,
    LeadOpportunityRow,
    LeadUsefulnessFeedback,
    OrganizationMember,
    ScoringFeedback,
    User,
)
from services.prospecting.effective_offer_registry import build_effective_registry
from services.prospecting.offer_matcher import OfferMatcher
from services.prospecting.offer_profile import OfferProfile, OfferProfileRegistry
from services.prospecting.offer_profile_validator import validate_profile

_REPLY = {"REPLY", "RESPONDED", "POSITIVE_REPLY"}
_MEETING = {"MEETING", "MEETING_SCHEDULED", "MEETING_HELD"}
_WON = {"WON", "CONVERTED", "SALE", "CLOSED_WON"}
_CONTACT_ACTIONS = {"CONTACTED", "WHATSAPP_SENT", "LINKEDIN_ASSOCIATED"}
_PROPOSAL_ACTIONS = {"PROPOSAL_SENT"}


def _bucket(value: Any) -> str:
    normalized = str(getattr(value, "value", value) or "").strip().upper()
    if normalized in _WON:
        return "won"
    if normalized in _MEETING:
        return "meeting"
    if normalized in _REPLY:
        return "reply"
    return "other"


def _signal_keys(raw: Any) -> set[str]:
    if isinstance(raw, list):
        values: set[str] = set()
        for item in raw:
            if isinstance(item, str):
                values.add(item)
            elif isinstance(item, dict):
                key = item.get("key") or item.get("signal") or item.get("name")
                if key:
                    values.add(str(key))
        return values
    if isinstance(raw, dict):
        return {str(key) for key, value in raw.items() if value not in (False, None, 0, "")}
    return set()


def _version_next(value: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)", str(value or ""))
    if not match:
        raise ValueError("versão ativa precisa seguir o formato major.minor")
    return f"{int(match.group(1))}.{int(match.group(2)) + 1}"


def _metric_row(rows: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    if not rows:
        return {
            "sample_size": 0,
            "top_k": 0,
            "reply_precision": None,
            "meeting_precision": None,
            "win_precision": None,
            "meeting_recall": None,
            "win_recall": None,
            "mean_score": None,
        }
    ordered = sorted(rows, key=lambda item: (item["score"], item["id"]), reverse=True)
    selected = ordered[: max(1, min(top_k, len(ordered)))]
    total_meetings = sum(1 for item in rows if item["bucket"] in {"meeting", "won"})
    total_wins = sum(1 for item in rows if item["bucket"] == "won")
    replies = sum(1 for item in selected if item["bucket"] in {"reply", "meeting", "won"})
    meetings = sum(1 for item in selected if item["bucket"] in {"meeting", "won"})
    wins = sum(1 for item in selected if item["bucket"] == "won")
    size = len(selected)
    return {
        "sample_size": len(rows),
        "top_k": size,
        "reply_precision": round(replies / size, 4),
        "meeting_precision": round(meetings / size, 4),
        "win_precision": round(wins / size, 4),
        "meeting_recall": round(meetings / total_meetings, 4) if total_meetings else None,
        "win_recall": round(wins / total_wins, 4) if total_wins else None,
        "mean_score": round(sum(float(item["score"]) for item in selected) / size, 2),
    }


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return round(b - a, 4)


def _safe_rate(value: int, total: int) -> float | None:
    return round(value / total, 4) if total else None


class LearningCalibrationService:
    """Mede, propõe e simula calibrações sem alterar produção automaticamente."""

    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def _profile(self, offer_key: str) -> OfferProfile:
        profile = build_effective_registry(self.db, self.organization_id).get(offer_key)
        if profile is None:
            raise ValueError("Oferta não encontrada no registry efetivo deste workspace")
        return profile

    def _offer_opportunities(self, offer_key: str) -> list[LeadOpportunityRow]:
        return self.db.query(LeadOpportunityRow).filter(
            LeadOpportunityRow.organization_id == self.organization_id,
            LeadOpportunityRow.offer_key == offer_key,
        ).all()

    def _offer_outcomes(self, offer_key: str) -> list[CommercialOutcomeRow]:
        return self.db.query(CommercialOutcomeRow).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
            CommercialOutcomeRow.offer_key == offer_key,
        ).all()

    def calibration_report(self, offer_key: str, *, min_samples: int = 20) -> dict[str, Any]:
        if min_samples < 3:
            raise ValueError("min_samples deve ser pelo menos 3")
        profile = self._profile(offer_key)
        opportunities = self._offer_opportunities(offer_key)
        outcomes = self._offer_outcomes(offer_key)
        attributed = [row for row in outcomes if row.lead_opportunity_id is not None]
        by_opp: dict[str, list[CommercialOutcomeRow]] = defaultdict(list)
        for row in attributed:
            by_opp[str(row.lead_opportunity_id)].append(row)

        observed = [row for row in opportunities if str(row.id) in by_opp]
        terminal_wins = 0
        observed_rows: list[tuple[LeadOpportunityRow, str]] = []
        for opportunity in observed:
            buckets = {_bucket(item.outcome) for item in by_opp[str(opportunity.id)]}
            bucket = "won" if "won" in buckets else "meeting" if "meeting" in buckets else "reply" if "reply" in buckets else "other"
            terminal_wins += int(bucket == "won")
            observed_rows.append((opportunity, bucket))

        signal_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"sample": 0, "reply": 0, "meeting": 0, "won": 0})
        for opportunity, bucket in observed_rows:
            for signal in _signal_keys(opportunity.signals_matched):
                stat = signal_stats[signal]
                stat["sample"] += 1
                stat["reply"] += int(bucket in {"reply", "meeting", "won"})
                stat["meeting"] += int(bucket in {"meeting", "won"})
                stat["won"] += int(bucket == "won")

        associations = []
        per_signal_floor = max(3, min_samples // 2)
        for signal, stat in signal_stats.items():
            sample = stat["sample"]
            associations.append({
                "signal": signal,
                "sample_size": sample,
                "reply_rate": _safe_rate(stat["reply"], sample),
                "meeting_rate": _safe_rate(stat["meeting"], sample),
                "win_rate": _safe_rate(stat["won"], sample),
                "enough_sample": sample >= per_signal_floor,
                "interpretation": "associação observada; não implica causalidade",
            })
        associations.sort(key=lambda item: (item["enough_sample"], item["win_rate"] or 0, item["meeting_rate"] or 0, item["sample_size"]), reverse=True)

        opportunity_ids = {str(row.id) for row in opportunities}
        lead_ids = {row.lead_id for row in opportunities}
        usefulness = self.db.query(LeadUsefulnessFeedback).filter(
            LeadUsefulnessFeedback.organization_id == self.organization_id,
            LeadUsefulnessFeedback.lead_id.in_(lead_ids) if lead_ids else False,
        ).all() if lead_ids else []
        score_feedback = self.db.query(ScoringFeedback).filter(
            ScoringFeedback.organization_id == self.organization_id,
            ScoringFeedback.lead_id.in_(lead_ids) if lead_ids else False,
        ).all() if lead_ids else []
        useful_count = sum(1 for row in usefulness if bool(row.useful))
        score_deltas = [int(row.suggested_score) - int(row.original_score) for row in score_feedback]

        attribution_rate = round(len(attributed) / len(outcomes), 4) if outcomes else None
        min_wins = max(2, math.ceil(min_samples * 0.1))
        gates = {
            "observed_opportunities": len(observed),
            "required_observed_opportunities": min_samples,
            "wins": terminal_wins,
            "required_wins": min_wins,
            "attribution_rate": attribution_rate,
            "required_attribution_rate": 0.8,
            "enough_sample": len(observed) >= min_samples,
            "enough_wins": terminal_wins >= min_wins,
            "enough_attribution": attribution_rate is not None and attribution_rate >= 0.8,
        }
        gates["eligible_for_proposal"] = bool(gates["enough_sample"] and gates["enough_wins"] and gates["enough_attribution"])

        return {
            "offer_key": offer_key,
            "active_version": profile.version,
            "opportunities_total": len(opportunities),
            "outcomes_total": len(outcomes),
            "attributed_outcomes": len(attributed),
            "sample_quality": gates,
            "associations": associations,
            "human_feedback": {
                "usefulness_total": len(usefulness),
                "useful": useful_count,
                "not_useful": len(usefulness) - useful_count,
                "useful_rate": _safe_rate(useful_count, len(usefulness)),
                "score_feedback_total": len(score_feedback),
                "mean_score_delta": round(sum(score_deltas) / len(score_deltas), 2) if score_deltas else None,
                "note": "feedback de lead é contexto humano e não é tratado como causalidade da oferta quando o lead possui múltiplas oportunidades",
            },
        }

    def suggested_candidate(self, offer_key: str, *, min_samples: int = 20) -> dict[str, Any]:
        report = self.calibration_report(offer_key, min_samples=min_samples)
        if not report["sample_quality"]["eligible_for_proposal"]:
            raise ValueError("amostra ainda não atende aos gates mínimos de calibração")
        current = self._profile(offer_key)
        snapshot = deepcopy(current.to_dict())
        snapshot["version"] = _version_next(current.version)
        positive = list((snapshot.get("signals") or {}).get("positive") or [])
        current_weights = dict((snapshot.get("signals") or {}).get("weights") or {})
        observed = {item["signal"]: item for item in report["associations"] if item["enough_sample"]}
        total_observed = report["sample_quality"]["observed_opportunities"]
        total_wins = report["sample_quality"]["wins"]
        baseline_win = total_wins / total_observed if total_observed else 0.0

        changes = []
        new_weights: dict[str, float] = dict(current_weights)
        for signal in positive:
            item = observed.get(signal)
            if not item:
                continue
            old = float(current_weights.get(signal, 1.0))
            win_lift = float(item["win_rate"] or 0) - baseline_win
            meeting_rate = float(item["meeting_rate"] or 0)
            # Mudança conservadora: no máximo ±25% por ciclo. O objetivo é
            # produzir um candidato testável, não "otimizar" o passado.
            factor = max(0.75, min(1.25, 1.0 + 0.8 * win_lift + 0.15 * (meeting_rate - baseline_win)))
            new = round(max(0.25, old * factor), 2)
            new_weights[signal] = new
            if new != old:
                changes.append({"signal": signal, "from": old, "to": new, "reason": "taxa comercial observada na amostra atribuída"})

        snapshot.setdefault("signals", {})["weights"] = new_weights
        errors = [item for item in validate_profile(OfferProfile.from_dict(snapshot)) if not str(item).startswith("aviso:")]
        if errors:
            raise ValueError("candidato gerado é inválido: " + "; ".join(errors))
        return {"profile_snapshot": snapshot, "changes": changes, "report": report}

    @staticmethod
    def _lead_facts(opportunity: LeadOpportunityRow, lead: Lead | None) -> dict[str, Any]:
        # Importante: apenas fatos observados viram True. Sinais ausentes não
        # recebem False; isso preserva UNKNOWN != FALSE no replay.
        facts: dict[str, Any] = {}
        for signal in _signal_keys(opportunity.signals_matched):
            facts[signal.lower()] = True
        if lead is not None:
            if lead.category:
                facts["segment"] = lead.category
            # CNAE/porte podem existir em provenance; só promovemos quando há
            # valor explícito para não inventar contexto.
            provenance = lead.discovery_provenance if isinstance(lead.discovery_provenance, dict) else {}
            cnae = provenance.get("cnae")
            company_size = provenance.get("company_size") or provenance.get("porte")
            if cnae:
                facts["cnae"] = str(cnae)
            if company_size:
                facts["company_size"] = str(company_size)
        return facts

    def replay(self, offer_key: str, candidate_snapshot: dict[str, Any], *, min_samples: int = 20, top_k: int = 20) -> dict[str, Any]:
        if not 1 <= top_k <= 100:
            raise ValueError("top_k deve ficar entre 1 e 100")
        report = self.calibration_report(offer_key, min_samples=min_samples)
        current = self._profile(offer_key)
        candidate = OfferProfile.from_dict(deepcopy(candidate_snapshot or {}))
        if candidate.key != offer_key:
            raise ValueError("o candidato não pertence à oferta informada")
        if candidate.version == current.version:
            raise ValueError("o candidato precisa usar uma nova versão")
        errors = [item for item in validate_profile(candidate) if not str(item).startswith("aviso:")]
        if errors:
            raise ValueError("OfferProfile candidato inválido: " + "; ".join(errors))

        registry_a = OfferProfileRegistry(); registry_a.register(current)
        registry_b = OfferProfileRegistry(); registry_b.register(candidate)
        matcher_a = OfferMatcher(registry_a)
        matcher_b = OfferMatcher(registry_b)

        opportunities = self._offer_opportunities(offer_key)
        outcomes = [row for row in self._offer_outcomes(offer_key) if row.lead_opportunity_id is not None]
        by_opp: dict[str, list[CommercialOutcomeRow]] = defaultdict(list)
        for outcome in outcomes:
            by_opp[str(outcome.lead_opportunity_id)].append(outcome)
        lead_ids = {row.lead_id for row in opportunities}
        leads = {row.id: row for row in self.db.query(Lead).filter(
            Lead.organization_id == self.organization_id,
            Lead.id.in_(lead_ids) if lead_ids else False,
        ).all()} if lead_ids else {}

        rows_a: list[dict[str, Any]] = []
        rows_b: list[dict[str, Any]] = []
        rank_rows: list[dict[str, Any]] = []
        for opportunity in opportunities:
            related = by_opp.get(str(opportunity.id), [])
            if not related:
                continue
            buckets = {_bucket(item.outcome) for item in related}
            bucket = "won" if "won" in buckets else "meeting" if "meeting" in buckets else "reply" if "reply" in buckets else "other"
            facts = self._lead_facts(opportunity, leads.get(opportunity.lead_id))
            scored_a = matcher_a._score_profile(current, facts)  # replay determinístico do profile isolado
            scored_b = matcher_b._score_profile(candidate, facts)
            a_score = scored_a.score if scored_a is not None else 0
            b_score = scored_b.score if scored_b is not None else 0
            rows_a.append({"id": str(opportunity.id), "score": a_score, "bucket": bucket})
            rows_b.append({"id": str(opportunity.id), "score": b_score, "bucket": bucket})
            rank_rows.append({"opportunity_id": str(opportunity.id), "current_score": a_score, "candidate_score": b_score, "delta": b_score - a_score, "bucket": bucket})

        metrics_a = _metric_row(rows_a, top_k)
        metrics_b = _metric_row(rows_b, top_k)
        sample_ok = bool(report["sample_quality"]["eligible_for_proposal"])
        win_delta = _delta(metrics_a["win_precision"], metrics_b["win_precision"])
        meeting_delta = _delta(metrics_a["meeting_precision"], metrics_b["meeting_precision"])
        reply_delta = _delta(metrics_a["reply_precision"], metrics_b["reply_precision"])
        recall_delta = _delta(metrics_a["win_recall"], metrics_b["win_recall"])

        improves = sample_ok and (
            (win_delta is not None and win_delta >= 0.02)
            or ((win_delta or 0) >= 0 and meeting_delta is not None and meeting_delta >= 0.05)
        ) and (reply_delta is None or reply_delta >= -0.05) and (recall_delta is None or recall_delta >= -0.05)
        worsens = sample_ok and (
            (win_delta is not None and win_delta <= -0.02)
            or ((win_delta or 0) <= 0 and meeting_delta is not None and meeting_delta <= -0.05)
        )
        verdict = "v2" if improves else "v1" if worsens else "inconclusive"
        recommendation = (
            f"Candidato {candidate.version} melhora o ranking histórico dentro dos gates definidos; submeter à aprovação humana."
            if verdict == "v2" else
            f"Manter {current.version}; o replay do candidato {candidate.version} piora métricas comerciais observadas."
            if verdict == "v1" else
            "Não publicar mudança: evidência insuficiente ou diferença não conclusiva."
        )

        rank_rows.sort(key=lambda item: abs(item["delta"]), reverse=True)
        return {
            "offer_key": offer_key,
            "version_a": current.version,
            "version_b": candidate.version,
            "verdict": verdict,
            "recommendation": recommendation,
            "delta": {
                "reply_precision": reply_delta,
                "meeting_precision": meeting_delta,
                "win_precision": win_delta,
                "win_recall": recall_delta,
            },
            "v1": metrics_a,
            "v2": metrics_b,
            "sample_quality": report["sample_quality"],
            "associations": report["associations"],
            "baseline_profile_snapshot": current.to_dict(),
            "candidate_profile_snapshot": candidate.to_dict(),
            "rank_movements": rank_rows[:25],
            "methodology": {
                "observations": "somente oportunidades com outcome atribuído entram no replay",
                "unknown_semantics": "sinal ausente permanece UNKNOWN; não é convertido em FALSE",
                "causality": "replay mede associação histórica e ranking contrafactual; não prova causalidade",
                "publication": "nenhuma alteração é aplicada sem aprovação e publicação humanas explícitas",
            },
        }

    def create_calibration_comparison(self, offer_key: str, candidate_snapshot: dict[str, Any] | None, *, min_samples: int = 20, top_k: int = 20) -> CommercialComparison:
        if candidate_snapshot is None:
            candidate_snapshot = self.suggested_candidate(offer_key, min_samples=min_samples)["profile_snapshot"]
        result = self.replay(offer_key, candidate_snapshot, min_samples=min_samples, top_k=top_k)
        if result["verdict"] != "v2":
            raise ValueError("o replay não produziu evidência conclusiva a favor do candidato")
        row = CommercialComparison(
            organization_id=self.organization_id,
            offer_key=offer_key,
            version_a=result["version_a"],
            version_b=result["version_b"],
            result=result,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def overview(self, *, min_samples: int = 20) -> dict[str, Any]:
        registry = build_effective_registry(self.db, self.organization_id)
        items = []
        for profile in registry.list():
            # O perfil genérico não representa uma oferta vendável.
            if profile.key == "__generic__":
                continue
            report = self.calibration_report(profile.key, min_samples=min_samples)
            if report["opportunities_total"] or report["outcomes_total"]:
                items.append(report)
        items.sort(key=lambda item: (item["sample_quality"]["eligible_for_proposal"], item["sample_quality"]["observed_opportunities"]), reverse=True)
        return {"items": items, "min_samples": min_samples}


class CommercialCoachingService:
    """Diagnóstico do time com recomendações rastreáveis até contagens reais."""

    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def dashboard(self) -> dict[str, Any]:
        members = self.db.query(OrganizationMember).filter(OrganizationMember.organization_id == self.organization_id).all()
        member_user_ids = {row.user_id for row in members}
        users = {row.id: row for row in self.db.query(User).filter(User.id.in_(member_user_ids) if member_user_ids else False).all()} if member_user_ids else {}
        leads = self.db.query(Lead).filter(Lead.organization_id == self.organization_id).all()
        lead_by_id = {row.id: row for row in leads}
        activities = self.db.query(LeadActivity).join(Lead, Lead.id == LeadActivity.lead_id).filter(Lead.organization_id == self.organization_id).all()
        outcomes = self.db.query(CommercialOutcomeRow).filter(CommercialOutcomeRow.organization_id == self.organization_id).all()

        first_contact: dict[Any, datetime] = {}
        proposals: set[Any] = set()
        for activity in activities:
            action = str(getattr(activity.action, "value", activity.action))
            if action in _CONTACT_ACTIONS and activity.created_at is not None:
                previous = first_contact.get(activity.lead_id)
                if previous is None or activity.created_at < previous:
                    first_contact[activity.lead_id] = activity.created_at
            if action in _PROPOSAL_ACTIONS:
                proposals.add(activity.lead_id)

        buckets_by_lead: dict[Any, set[str]] = defaultdict(set)
        for outcome in outcomes:
            buckets_by_lead[outcome.lead_id].add(_bucket(outcome.outcome))

        now = datetime.now(timezone.utc)
        consultant_rows = []
        for user_id in sorted(member_user_ids, key=str):
            assigned = [lead for lead in leads if lead.assigned_to_id == user_id]
            if not assigned:
                continue
            contacted = [lead for lead in assigned if lead.id in first_contact]
            replied = [lead for lead in assigned if buckets_by_lead.get(lead.id, set()) & {"reply", "meeting", "won"}]
            meetings = [lead for lead in assigned if buckets_by_lead.get(lead.id, set()) & {"meeting", "won"}]
            wins = [lead for lead in assigned if "won" in buckets_by_lead.get(lead.id, set())]
            proposal_count = sum(1 for lead in assigned if lead.id in proposals)
            overdue = sum(1 for lead in assigned if lead.next_action_at is not None and _aware(lead.next_action_at) < now and "won" not in buckets_by_lead.get(lead.id, set()))

            fast: list[Lead] = []
            slow: list[Lead] = []
            for lead in contacted:
                if lead.created_at is None:
                    continue
                hours = (_aware(first_contact[lead.id]) - _aware(lead.created_at)).total_seconds() / 3600
                (fast if hours <= 24 else slow).append(lead)
            fast_meetings = sum(1 for lead in fast if buckets_by_lead.get(lead.id, set()) & {"meeting", "won"})
            slow_meetings = sum(1 for lead in slow if buckets_by_lead.get(lead.id, set()) & {"meeting", "won"})
            row = {
                "user_id": str(user_id),
                "name": getattr(users.get(user_id), "name", None) or getattr(users.get(user_id), "email", None) or "Consultor",
                "assigned_leads": len(assigned),
                "contacted": len(contacted),
                "replies": len(replied),
                "meetings": len(meetings),
                "proposals": proposal_count,
                "wins": len(wins),
                "overdue_followups": overdue,
                "reply_rate": _safe_rate(len(replied), len(contacted)),
                "meeting_rate": _safe_rate(len(meetings), len(contacted)),
                "proposal_rate": _safe_rate(proposal_count, len(meetings)),
                "win_rate": _safe_rate(len(wins), len(contacted)),
                "first_contact_under_24h_rate": _safe_rate(len(fast), len(fast) + len(slow)),
                "timing_evidence": {
                    "under_24h_sample": len(fast),
                    "under_24h_meeting_rate": _safe_rate(fast_meetings, len(fast)),
                    "over_24h_sample": len(slow),
                    "over_24h_meeting_rate": _safe_rate(slow_meetings, len(slow)),
                },
            }
            consultant_rows.append(row)

        team_contacted = sum(item["contacted"] for item in consultant_rows)
        team = {
            "consultants": len(consultant_rows),
            "assigned_leads": sum(item["assigned_leads"] for item in consultant_rows),
            "contacted": team_contacted,
            "replies": sum(item["replies"] for item in consultant_rows),
            "meetings": sum(item["meetings"] for item in consultant_rows),
            "proposals": sum(item["proposals"] for item in consultant_rows),
            "wins": sum(item["wins"] for item in consultant_rows),
            "overdue_followups": sum(item["overdue_followups"] for item in consultant_rows),
        }
        team["reply_rate"] = _safe_rate(team["replies"], team_contacted)
        team["meeting_rate"] = _safe_rate(team["meetings"], team_contacted)
        team["win_rate"] = _safe_rate(team["wins"], team_contacted)

        for row in consultant_rows:
            recommendations = []
            if row["overdue_followups"] >= 3 and row["overdue_followups"] / max(1, row["assigned_leads"]) >= 0.2:
                recommendations.append({
                    "kind": "FOLLOW_UP_SLA",
                    "title": "Reduzir follow-ups vencidos",
                    "recommendation": "Priorize a fila vencida antes de abrir novos contatos.",
                    "evidence": {"overdue_followups": row["overdue_followups"], "assigned_leads": row["assigned_leads"]},
                    "association_not_causation": True,
                })
            timing = row["timing_evidence"]
            fast_rate = timing["under_24h_meeting_rate"]
            slow_rate = timing["over_24h_meeting_rate"]
            if timing["under_24h_sample"] >= 5 and timing["over_24h_sample"] >= 5 and fast_rate is not None and slow_rate is not None and fast_rate >= slow_rate + 0.1 and (row["first_contact_under_24h_rate"] or 0) < 0.7:
                recommendations.append({
                    "kind": "FIRST_CONTACT_TIMING",
                    "title": "Antecipar o primeiro contato",
                    "recommendation": "Neste histórico, contatos em até 24h aparecem associados a mais reuniões. Tente aumentar a parcela atendida nesse intervalo.",
                    "evidence": timing,
                    "association_not_causation": True,
                })
            if row["replies"] >= 5 and row["meetings"] >= 3 and row["proposals"] / max(1, row["meetings"]) < 0.5:
                recommendations.append({
                    "kind": "MEETING_TO_PROPOSAL",
                    "title": "Trabalhar conversão de reunião em proposta",
                    "recommendation": "Há volume suficiente de reuniões, mas menos da metade avançou para proposta registrada. Revise qualificação, registro e próximo passo pós-reunião.",
                    "evidence": {"meetings": row["meetings"], "proposals": row["proposals"], "proposal_rate": row["proposal_rate"]},
                    "association_not_causation": True,
                })
            row["recommendations"] = recommendations

        consultant_rows.sort(key=lambda item: (len(item["recommendations"]), item["overdue_followups"], item["assigned_leads"]), reverse=True)
        return {
            "team": team,
            "consultants": consultant_rows,
            "methodology": {
                "assignment": "métricas por consultor usam o responsável atual do lead",
                "outcomes": "respostas/reuniões/vendas vêm de outcomes reais do workspace",
                "timing": "primeiro contato deriva da primeira atividade comercial registrada",
                "causality": "recomendações descrevem associação observada; não afirmam causalidade",
            },
        }


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
