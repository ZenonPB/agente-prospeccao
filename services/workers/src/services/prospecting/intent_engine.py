"""Intent v2 + technographics sobre evidências observadas."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any, Iterable

from services.prospecting.freshness_policy import parse_observed_at


@dataclass(frozen=True)
class SignalRule:
    key: str
    patterns: tuple[str, ...]
    weight: float
    family: str


SIGNAL_RULES: tuple[SignalRule, ...] = (
    SignalRule("JOB_CHANGE", (r"mudan[cç]a de empresa", r"mudan[cç]a de emprego", r"employer changed", r"job change"), 1.05, "people"),
    SignalRule("ROLE_CHANGE", (r"mudan[cç]a de cargo", r"novo cargo", r"role changed", r"promotion"), 0.8, "people"),
    SignalRule("HIRING_MECHANICAL_ENGINEER", (r"engenheir[oa] mec[aâ]nic", r"mechanical engineer"), 1.25, "jobs"),
    SignalRule("HIRING_PROJECT_DESIGNER", (r"projetista", r"desenhista t[eé]cnic", r"cad designer"), 1.05, "jobs"),
    SignalRule("HIRING_MAINTENANCE", (r"manuten[cç][aã]o", r"maintenance"), 0.9, "jobs"),
    SignalRule("HIRING_AUTOMATION", (r"automa[cç][aã]o", r"automation engineer"), 1.0, "jobs"),
    SignalRule("HIRING_CNC_OPERATOR", (r"cnc", r"operador.*usinagem"), 0.9, "jobs"),
    SignalRule("HIRING_IT", (r"desenvolvedor", r"software engineer", r"analista de sistemas", r"ti\b"), 1.0, "jobs"),
    SignalRule("HIRING_OPERATIONS", (r"opera[cç][oõ]es", r"operations", r"processos"), 0.85, "jobs"),
    SignalRule("HIRING_DATA", (r"dados", r"data analyst", r"data engineer", r"bi\b"), 0.85, "jobs"),
    SignalRule("NEW_BRANCH", (r"nova unidade", r"nova filial", r"new branch"), 1.05, "news"),
    SignalRule("EXPANSION", (r"expans[aã]o", r"expandindo", r"expansion"), 1.2, "news"),
    SignalRule("NEW_FACTORY", (r"nova f[aá]brica", r"nova planta", r"new factory"), 1.3, "news"),
    SignalRule("NEW_PRODUCT", (r"novo produto", r"lan[cç]amento", r"new product"), 0.9, "news"),
    SignalRule("FUNDING", (r"investimento", r"rodada", r"funding", r"aporte"), 1.1, "news"),
    SignalRule("MANAGEMENT_CHANGE", (r"novo ceo", r"nova diretoria", r"new ceo", r"management change"), 0.65, "news"),
    SignalRule("TENDER_OPEN", (r"licita[cç][aã]o", r"preg[aã]o", r"edital"), 1.0, "procurement"),
    SignalRule("SOFTWARE_PROCUREMENT", (r"software", r"sistema web", r"erp", r"licen[cç]a.*sistema"), 1.2, "procurement"),
    SignalRule("INDUSTRIAL_PROCUREMENT", (r"m[aá]quina", r"equipamento industrial", r"usinagem", r"projeto mec[aâ]nico"), 1.2, "procurement"),
    SignalRule("EVENT_PROCUREMENT", (r"trof[eé]u", r"premia[cç][aã]o", r"evento", r"medalha"), 1.15, "procurement"),
)

TECH_PATTERNS: dict[str, tuple[str, ...]] = {
    "WordPress": (r"wp-content", r"wordpress"),
    "WooCommerce": (r"woocommerce",),
    "Shopify": (r"cdn\.shopify\.com", r"shopify"),
    "RD Station": (r"rdstation", r"rd\.station", r"rd_station"),
    "HubSpot": (r"hubspot", r"hs-scripts", r"hsforms"),
    "Salesforce": (r"salesforce", r"force\.com"),
    "TOTVS": (r"totvs", r"protheus"),
    "Omie": (r"omie",),
    "Bling": (r"bling",),
    "Google Analytics": (r"google-analytics", r"googletagmanager", r"gtag\("),
    "Meta Pixel": (r"fbq\(", r"facebook pixel", r"connect\.facebook\.net"),
    "Cloudflare": (r"cloudflare", r"cf-ray"),
    "Next.js": (r"_next/", r"next\.js"),
}

SOURCE_RELIABILITY: dict[str, float] = {
    "pncp": 0.98,
    "company_site": 0.90,
    "website": 0.90,
    "job_posting": 0.85,
    "job_postings": 0.85,
    "employment_change": 0.88,
    "company_news": 0.78,
    "event": 0.85,
    "social": 0.55,
    "unknown": 0.50,
}


def _flatten(value: Any) -> str:
    parts: list[str] = []
    def visit(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, dict):
            for key, item in node.items():
                parts.append(str(key))
                visit(item)
        elif isinstance(node, (list, tuple, set)):
            for item in node:
                visit(item)
        else:
            parts.append(str(node))
    visit(value)
    return " ".join(parts)


def detect_technologies(*payloads: Any) -> list[dict[str, Any]]:
    haystack = _flatten(payloads).lower()
    results: list[dict[str, Any]] = []
    for technology, patterns in TECH_PATTERNS.items():
        matched = [pattern for pattern in patterns if re.search(pattern, haystack, re.IGNORECASE)]
        if matched:
            results.append({"technology": technology, "confidence": min(0.95, 0.65 + 0.1 * len(matched)), "evidence": matched[:3]})
    return sorted(results, key=lambda item: (-item["confidence"], item["technology"]))


def recency_decay(observed_at: Any, *, half_life_days: float = 30.0, now: datetime | None = None) -> float:
    observed = parse_observed_at(observed_at)
    if observed is None:
        return 0.55
    current = now or datetime.now(timezone.utc)
    age_days = max(0.0, (current - observed).total_seconds() / 86400.0)
    return math.exp(-math.log(2) * age_days / max(1.0, half_life_days))


def extract_intent_signals(evidence: Iterable[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    signals: dict[str, dict[str, Any]] = {}
    for item in evidence:
        text = _flatten(item).lower()
        source = str(item.get("source") or item.get("provider") or "unknown").lower()
        confidence = float(item.get("confidence", 0.7) or 0.7)
        reliability = float(item.get("source_reliability") or SOURCE_RELIABILITY.get(source, 0.5))
        decay = recency_decay(item.get("observed_at") or item.get("created_at"), now=now)
        for rule in SIGNAL_RULES:
            matched = [pattern for pattern in rule.patterns if re.search(pattern, text, re.IGNORECASE)]
            if not matched:
                continue
            contribution = rule.weight * confidence * reliability * decay
            current = signals.get(rule.key)
            candidate = {
                "signal": rule.key,
                "family": rule.family,
                "contribution": round(contribution, 4),
                "confidence": round(confidence, 4),
                "source_reliability": round(reliability, 4),
                "recency_decay": round(decay, 4),
                "source": source,
                "evidence": matched[:3],
                "observed_at": item.get("observed_at") or item.get("created_at"),
            }
            if current is None or candidate["contribution"] > current["contribution"]:
                signals[rule.key] = candidate
    return sorted(signals.values(), key=lambda item: (-item["contribution"], item["signal"]))


def intent_score(signals: Iterable[dict[str, Any]]) -> int:
    total = sum(max(0.0, float(item.get("contribution", 0.0))) for item in signals)
    return int(round(100.0 * (1.0 - math.exp(-total / 2.5))))


def build_opportunity_vector(
    *,
    icp_fit: float | int | None,
    need: float | int | None,
    intent: float | int | None,
    buying_power: float | int | None,
    reachability: float | int | None,
    timing: float | int | None,
    commercial_fit: float | int | None = None,
) -> dict[str, Any]:
    dimensions = {
        "icp_fit": icp_fit,
        "need": need,
        "intent": intent,
        "buying_power": buying_power,
        "reachability": reachability,
        "timing": timing,
        "commercial_fit": commercial_fit,
    }
    known = {k: max(0.0, min(100.0, float(v))) for k, v in dimensions.items() if v is not None}
    weights = {"icp_fit": 1.25, "need": 1.25, "intent": 1.2, "buying_power": 0.9, "reachability": 1.0, "timing": 1.1, "commercial_fit": 1.0}
    denominator = sum(weights[k] for k in known)
    overall = round(sum(value * weights[k] for k, value in known.items()) / denominator) if denominator else 0
    return {
        **{key: (round(float(value)) if value is not None else None) for key, value in dimensions.items()},
        "overall": overall,
        "coverage": round(len(known) / len(dimensions), 3),
        "formula_version": "opportunity-v2",
    }
