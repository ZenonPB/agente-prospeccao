"""Contrato de maturidade para Vertentes (OfferProfiles).

Uma Vertente factory não é considerada madura só por possuir muitos campos.
Ela deve cobrir as etapas comerciais necessárias para o motor explicar quem
procurar, onde descobrir, quais evidências observar e como qualificar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MaturityCheck:
    key: str
    label: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class MaturityReport:
    score: int
    level: str
    checks: tuple[MaturityCheck, ...]

    @property
    def missing(self) -> list[str]:
        return [item.key for item in self.checks if not item.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "missing": self.missing,
            "checks": [
                {
                    "key": item.key,
                    "label": item.label,
                    "passed": item.passed,
                    "detail": item.detail,
                }
                for item in self.checks
            ],
        }


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(bool(item) for item in value)


def _has_any(mapping: dict[str, Any], keys: Iterable[str]) -> bool:
    return any(bool(mapping.get(key)) for key in keys)


def evaluate_offer_profile_maturity(profile: Any) -> MaturityReport:
    """Avalia completude comercial sem impor uma estrutura idêntica a todas as ofertas."""
    offer = _mapping(getattr(profile, "offer", None))
    icp = _mapping(getattr(profile, "icp", None))
    discovery = _mapping(getattr(profile, "discovery", None))
    prescoring = _mapping(getattr(profile, "prescoring", None))
    enrichment = _mapping(getattr(profile, "enrichment", None))
    signals = _mapping(getattr(profile, "signals", None))
    intent = _mapping(getattr(profile, "intent", None))
    decision_makers = _mapping(getattr(profile, "decision_makers", None))
    channels = _mapping(getattr(profile, "channels", None))
    qualification = _mapping(getattr(profile, "qualification", None))
    outreach = _mapping(getattr(profile, "outreach", None))

    checks = (
        MaturityCheck("identity", "Identidade comercial", bool(offer.get("name")) and bool(getattr(profile, "version", None))),
        MaturityCheck("icp", "ICP e público-alvo", _non_empty_list(icp.get("segments")) and _non_empty_list(icp.get("company_sizes"))),
        MaturityCheck("discovery", "Estratégia de descoberta", _non_empty_list(discovery.get("providers")) and bool(discovery.get("target_candidates"))),
        MaturityCheck("prescoring", "Pré-filtro", isinstance(prescoring.get("weights"), dict) and bool(prescoring.get("weights")) and prescoring.get("threshold") is not None),
        MaturityCheck("enrichment", "Enriquecimento", _non_empty_list(enrichment.get("steps")) or bool(enrichment.get("people_discovery"))),
        MaturityCheck("positive_signals", "Sinais positivos", _non_empty_list(signals.get("positive")) or _non_empty_list(signals.get("optional_positive"))),
        MaturityCheck("negative_signals", "Sinais negativos/exclusões", _non_empty_list(signals.get("negative")) or _non_empty_list(signals.get("disqualifiers")) or _non_empty_list(icp.get("exclusions"))),
        MaturityCheck("weights", "Pesos de evidência", isinstance(signals.get("weights"), dict) and bool(signals.get("weights"))),
        MaturityCheck("intent", "Timing e intenção", isinstance(intent.get("event_weights"), dict) and bool(intent.get("event_weights")) and bool(intent.get("decay_days"))),
        MaturityCheck("decision_makers", "Decisores", _non_empty_list(decision_makers.get("roles"))),
        MaturityCheck("channels", "Canais prioritários", _non_empty_list(channels.get("priority"))),
        MaturityCheck("qualification", "Qualificação", _non_empty_list(qualification.get("questions")) and isinstance(qualification.get("quality_gates"), dict)),
        MaturityCheck("outreach", "Abordagem baseada em evidência", bool(outreach.get("angle")) and _non_empty_list(outreach.get("evidence_requirements"))),
    )
    passed = sum(1 for item in checks if item.passed)
    score = round((passed / len(checks)) * 100)
    level = "madura" if score >= 85 else "em_evolucao" if score >= 65 else "incompleta"
    return MaturityReport(score=score, level=level, checks=checks)


def assert_factory_profile_mature(profile: Any, *, minimum_score: int = 85) -> None:
    report = evaluate_offer_profile_maturity(profile)
    if report.score < minimum_score:
        raise AssertionError(
            f"Vertente {getattr(profile, 'key', '<sem-chave>')} abaixo do contrato de maturidade: "
            f"{report.score}% (faltando: {', '.join(report.missing)})"
        )
