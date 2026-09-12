"""Serviços determinísticos de excelência por oferta.

Nenhuma decisão aqui chama provider externo. O serviço transforma dados já
persistidos em recorrência auditável e seleciona cases cadastrados de forma
explicável.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import re
import statistics
import unicodedata
from typing import Any, Iterable

from database.models import EventOpportunityRow, Lead
from database.phase56_models import CaseStudy, EventSeries


def _norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(?:19|20)\d{2}\b", " ", text)
    text = re.sub(r"\b(?:edicao|edition|ed)\s*\d+\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def event_series_key(event: EventOpportunityRow) -> str:
    organizer = _norm(event.organizer)
    name = _norm(event.name)
    family = _norm(event.event_type)
    base = "|".join(part for part in (organizer, name, family) if part)
    return base[:180] or str(event.id)


def _median_days(events: list[EventOpportunityRow]) -> int | None:
    dates = sorted(event.event_date for event in events if event.event_date)
    if len(dates) < 2:
        return None
    deltas = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
    if not deltas:
        return None
    return max(1, int(round(statistics.median(deltas))))


def _recurrence_confidence(events: list[EventOpportunityRow], interval_days: int | None) -> float:
    if len(events) < 2:
        return 0.25
    confidence = 0.55 + min(0.25, 0.08 * (len(events) - 2))
    if interval_days is not None:
        if 300 <= interval_days <= 430:
            confidence += 0.15
        elif 150 <= interval_days <= 220 or 70 <= interval_days <= 120:
            confidence += 0.1
    organizers = [_norm(item.organizer) for item in events if item.organizer]
    if organizers and Counter(organizers).most_common(1)[0][1] >= 2:
        confidence += 0.05
    return round(min(0.99, confidence), 3)


class EventSeriesService:
    @staticmethod
    def rebuild(db, organization_id: Any) -> list[EventSeries]:
        events = (
            db.query(EventOpportunityRow)
            .filter(EventOpportunityRow.organization_id == organization_id)
            .order_by(EventOpportunityRow.event_date.asc())
            .all()
        )
        grouped: dict[str, list[EventOpportunityRow]] = {}
        for event in events:
            grouped.setdefault(event_series_key(event), []).append(event)

        result: list[EventSeries] = []
        now = datetime.now(timezone.utc)
        for key, items in grouped.items():
            items.sort(key=lambda item: item.event_date or date.min)
            latest = items[-1]
            previous = items[-2] if len(items) > 1 else None
            interval = _median_days(items)
            confidence = _recurrence_confidence(items, interval)
            expected_window = None
            if latest.event_date and interval:
                expected = latest.event_date + timedelta(days=interval)
                tolerance = max(14, min(45, round(interval * 0.12)))
                expected_window = {
                    "start": (expected - timedelta(days=tolerance)).isoformat(),
                    "end": (expected + timedelta(days=tolerance)).isoformat(),
                    "interval_days": interval,
                    "computed_at": now.isoformat(),
                }

            row = (
                db.query(EventSeries)
                .filter(EventSeries.organization_id == organization_id, EventSeries.series_key == key)
                .first()
            )
            if row is None:
                row = EventSeries(organization_id=organization_id, series_key=key, name=latest.name)
                db.add(row)
            row.name = latest.name
            row.family = latest.event_type
            row.recurrence_confidence = confidence
            row.previous_event_id = previous.id if previous else None
            row.latest_event_id = latest.id
            row.expected_next_window = expected_window
            row.series_metadata = {
                "event_count": len(items),
                "providers": sorted({str(item.provider) for item in items if item.provider}),
                "organizer": latest.organizer,
            }
            result.append(row)
        db.flush()
        return result

    @staticmethod
    def rebuy_candidates(db, organization_id: Any, *, days_from: int = 30, days_to: int = 120) -> list[dict[str, Any]]:
        today = date.today()
        lower = today + timedelta(days=days_from)
        upper = today + timedelta(days=days_to)
        rows = db.query(EventSeries).filter(EventSeries.organization_id == organization_id).all()
        candidates: list[dict[str, Any]] = []
        for row in rows:
            window = row.expected_next_window if isinstance(row.expected_next_window, dict) else {}
            try:
                start = date.fromisoformat(str(window.get("start")))
                end = date.fromisoformat(str(window.get("end")))
            except (TypeError, ValueError):
                continue
            if end < lower or start > upper or float(row.recurrence_confidence or 0) < 0.6:
                continue
            candidates.append({
                "series_id": str(row.id),
                "series_key": row.series_key,
                "name": row.name,
                "family": row.family,
                "recurrence_confidence": float(row.recurrence_confidence or 0),
                "expected_next_window": window,
                "latest_event_id": str(row.latest_event_id) if row.latest_event_id else None,
            })
        return sorted(candidates, key=lambda item: item["expected_next_window"].get("start") or "")


class CaseStudyMatcher:
    @staticmethod
    def _tokens(values: Iterable[Any]) -> set[str]:
        tokens: set[str] = set()
        for value in values:
            tokens.update(_norm(str(value)).split())
        return tokens

    @classmethod
    def match(cls, db, organization_id: Any, lead: Lead, offer_key: str) -> dict[str, Any] | None:
        cases = (
            db.query(CaseStudy)
            .filter(
                CaseStudy.offer_key == offer_key,
                CaseStudy.active.is_(True),
                (CaseStudy.organization_id == organization_id) | (CaseStudy.organization_id.is_(None)),
            )
            .all()
        )
        if not cases:
            return None
        lead_tokens = cls._tokens([
            lead.company_name,
            getattr(lead, "category", None),
            getattr(lead, "target_segment", None),
            getattr(lead, "city", None),
        ])
        ranked = []
        for case in cases:
            segments = case.segments if isinstance(case.segments, list) else []
            segment_tokens = cls._tokens(segments)
            overlap = len(lead_tokens & segment_tokens)
            coverage = overlap / max(1, len(segment_tokens)) if segment_tokens else 0.0
            score = round(0.35 + min(0.6, coverage * 0.6), 3)
            ranked.append((score, overlap, case))
        score, overlap, case = max(ranked, key=lambda item: (item[0], item[1], str(item[2].id)))
        return {
            "case_study_id": str(case.id),
            "offer_key": case.offer_key,
            "title": case.title,
            "problem": case.problem,
            "solution": case.solution,
            "proof": case.proof,
            "assets": case.assets,
            "segments": case.segments,
            "match_score": score,
            "matched_tokens": sorted(lead_tokens & cls._tokens(case.segments or [])),
        }
