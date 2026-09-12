"""OfferMatcher — associação genérica entre lead e múltiplos OfferProfiles."""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from services.prospecting.offer_profile import OfferProfile, OfferProfileRegistry, OfferProfileResolver


def _signal_present(lead: Dict[str, Any], signal: str) -> bool:
    """Interpreta presença explícita e a equivalência semântica NO_X/has_X."""
    sig_l = signal.lower()
    if lead.get(sig_l) is True:
        return True
    if sig_l.startswith("no_"):
        return lead.get("has_" + sig_l[3:]) is False
    return False


@dataclass(frozen=True)
class LeadOpportunity:
    offer_key: str
    profile_key: str
    score: int
    offer_version: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    resolved_from: str = "explicit"
    signals_matched: List[str] = field(default_factory=list)
    signals_missing: List[str] = field(default_factory=list)
    score_breakdown: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LeadOpportunity":
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})


class OfferMatcher:
    """Ranqueia ofertas sem assumir uma vertical específica.

    ``positive`` preserva o denominator histórico do perfil. ``optional_positive``
    funciona como evidência incremental: quando observada pode elevar o score,
    mas sua ausência nunca reduz um lead com dados ainda desconhecidos.
    """

    def __init__(self, registry: OfferProfileRegistry):
        self.registry = registry
        self.resolver = OfferProfileResolver(registry)

    def match(
        self,
        lead_data: Dict[str, Any],
        min_score: int = 0,
        top_k: Optional[int] = None,
    ) -> List[LeadOpportunity]:
        results: List[LeadOpportunity] = []
        for profile in self.registry.list():
            opp = self._score_profile(profile, lead_data)
            if opp is not None and opp.score >= min_score:
                results.append(opp)
        results.sort(key=lambda o: o.score, reverse=True)
        return results[:top_k] if top_k is not None else results

    def _score_profile(self, profile: OfferProfile, lead: Dict[str, Any]) -> Optional[LeadOpportunity]:
        icp = profile.icp or {}
        signals = profile.signals or {}
        positive_signals = list(signals.get("positive", []))
        optional_signals = list(signals.get("optional_positive", []))
        disqualifiers = signals.get("disqualifiers", [])

        for dq in disqualifiers:
            if lead.get(dq.lower()) is True:
                return LeadOpportunity(
                    offer_key=profile.key,
                    profile_key=profile.archetype,
                    score=0,
                    offer_version=profile.version,
                    evidence=[f"DISQUALIFIED_BY_{dq}"],
                    score_breakdown={
                        "signal_score": 0,
                        "optional_bonus": 0,
                        "icp_score": 0,
                        "matched_weight": 0,
                        "total_weight": 0,
                        "weighted": False,
                        "disqualified_by": dq,
                    },
                )

        matched = [sig for sig in positive_signals if _signal_present(lead, sig)]
        missing = [sig for sig in positive_signals if sig not in matched]
        optional_matched = [sig for sig in optional_signals if _signal_present(lead, sig)]

        icp_hits: List[str] = []
        if icp.get("segments") and lead.get("segment") in icp["segments"]:
            icp_hits.append("segment")
        if icp.get("cnaes") and str(lead.get("cnae", "")).startswith(tuple(icp["cnaes"])):
            icp_hits.append("cnae")
        if icp.get("company_sizes") and lead.get("company_size") in icp["company_sizes"]:
            icp_hits.append("company_size")

        weights = signals.get("weights") or {}
        weighted = any(s in weights for s in positive_signals)
        if positive_signals and weighted:
            total_weight = sum(float(weights.get(s, 1)) for s in positive_signals)
            matched_weight = sum(float(weights.get(s, 1)) for s in matched)
            signal_score = matched_weight / total_weight * 70 if total_weight else 0
        elif positive_signals:
            total_weight = float(len(positive_signals))
            matched_weight = float(len(matched))
            signal_score = len(matched) / len(positive_signals) * 70
        else:
            total_weight = 0.0
            matched_weight = 0.0
            signal_score = 50.0

        # Sinais opcionais têm ganho limitado e jamais entram no denominator.
        # O peso relativo continua sendo configurado pelo OfferProfile.
        optional_weight = sum(float(weights.get(s, 1)) for s in optional_matched)
        optional_bonus = min(15.0, optional_weight * 3.0)
        icp_score = min(30, len(icp_hits) * 10)
        score = int(min(100, signal_score + optional_bonus + icp_score))
        breakdown = {
            "signal_score": int(signal_score),
            "optional_bonus": int(optional_bonus),
            "icp_score": icp_score,
            "matched_weight": matched_weight,
            "total_weight": total_weight,
            "weighted": weighted,
            "optional_signals_matched": optional_matched,
        }

        all_matched = [*matched, *optional_matched]
        evidence = all_matched + [f"icp:{hit}" for hit in icp_hits]
        try:
            from services.learning_service import match_golden_patterns
            observed = {sig: True for sig in all_matched}
            for pattern in match_golden_patterns(profile.key, observed, archetype=profile.archetype):
                evidence.append(f"golden:{pattern['pattern_id']}")
        except ImportError:  # pragma: no cover
            pass
        if not evidence:
            return None

        return LeadOpportunity(
            offer_key=profile.key,
            profile_key=profile.archetype,
            score=score,
            offer_version=profile.version,
            evidence=evidence,
            resolved_from="explicit",
            signals_matched=all_matched,
            signals_missing=missing,
            score_breakdown=breakdown,
        )
