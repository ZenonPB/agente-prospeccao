"""Registry extensível de intent providers sobre evidências já coletadas.

Nesta fase os adapters são passivos e gratuitos: classificam evidências que o
pipeline já conhece. Providers pagos/web futuros implementam o mesmo contrato.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from services.prospecting.intent_engine import extract_intent_signals


@dataclass(frozen=True)
class IntentProviderResult:
    provider: str
    status: str
    evidence: tuple[dict[str, Any], ...]
    signals: tuple[dict[str, Any], ...]
    error_code: str | None = None


class IntentProvider(Protocol):
    name: str
    source_aliases: tuple[str, ...]

    def collect(self, evidence: list[dict[str, Any]]) -> IntentProviderResult: ...


class _EvidenceIntentProvider:
    name = "evidence"
    source_aliases: tuple[str, ...] = ()

    def collect(self, evidence: list[dict[str, Any]]) -> IntentProviderResult:
        selected: list[dict[str, Any]] = []
        for item in evidence:
            source = str(item.get("source") or item.get("provider") or "").lower()
            if any(alias in source for alias in self.source_aliases):
                selected.append(item)
        if not selected:
            return IntentProviderResult(self.name, "empty", (), ())
        signals = extract_intent_signals(selected)
        return IntentProviderResult(self.name, "success", tuple(selected), tuple(signals))


class JobPostingIntentProvider(_EvidenceIntentProvider):
    name = "job_postings"
    source_aliases = ("job", "vaga", "career", "linkedin_jobs")


class CompanyNewsIntentProvider(_EvidenceIntentProvider):
    name = "company_news"
    source_aliases = ("news", "noticia", "press", "company_news")


class ProcurementIntentProvider(_EvidenceIntentProvider):
    name = "procurement"
    source_aliases = ("pncp", "procurement", "licitacao", "tender")


class SocialIntentProvider(_EvidenceIntentProvider):
    name = "social"
    source_aliases = ("social", "instagram", "linkedin", "facebook")


class EventIntentProvider(_EvidenceIntentProvider):
    name = "events"
    source_aliases = ("event", "evento", "mej")


class IntentProviderRegistry:
    def __init__(self, providers: list[IntentProvider] | None = None) -> None:
        self.providers = providers or [
            JobPostingIntentProvider(),
            CompanyNewsIntentProvider(),
            ProcurementIntentProvider(),
            SocialIntentProvider(),
            EventIntentProvider(),
        ]

    def run(self, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        results = [provider.collect(evidence) for provider in self.providers]
        merged: dict[str, dict[str, Any]] = {}
        for result in results:
            for signal in result.signals:
                current = merged.get(signal["signal"])
                if current is None or signal["contribution"] > current["contribution"]:
                    merged[signal["signal"]] = {**signal, "provider": result.provider}
        return {
            "providers": [
                {
                    "provider": result.provider,
                    "status": result.status,
                    "result_count": len(result.evidence),
                    "signal_count": len(result.signals),
                    "error_code": result.error_code,
                }
                for result in results
            ],
            "signals": sorted(merged.values(), key=lambda item: (-item["contribution"], item["signal"])),
        }
