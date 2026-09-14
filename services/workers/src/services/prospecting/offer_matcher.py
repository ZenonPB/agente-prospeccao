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

    Perfis mais maduros podem declarar ``qualification.quality_gates`` para
    impedir um score artificialmente alto sem evidência comercial forte. A
    ausência de um sinal nunca vira ``False``: ela apenas limita a confiança
    máxima até o enriquecimento produzir evidência suficiente.
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
        results.sort(key=lambda o: (o.score, len(o.evidence), o.offer_key), reverse=True)
        return results[:top_k] if top_k is not None else results

    def _score_profile(self, profile: OfferProfile, lead: Dict[str, Any]) -> Optional[LeadOpportunity]:
        icp = profile.icp or {}
        signals = profile.signals or {}
        qualification = profile.qualification or {}
        quality_gates = qualification.get("quality_gates") or {}
        positive_signals = list(signals.get("positive", []))
        optional_signals = list(signals.get("optional_positive", []))
        negative_signals = list(signals.get("negative", []))
        disqualifiers = signals.get("disqualifiers", [])

        for dq in disqualifiers:
            if _signal_present(lead, dq):
                return LeadOpportunity(
                    offer_key=profile.key,
                    profile_key=profile.archetype,
                    score=0,
                    offer_version=profile.version,
                    evidence=[f"DISQUALIFIED_BY_{dq}"],
                    score_breakdown={
                        "signal_score": 0,
                        "optional_bonus": 0,
                        "negative_penalty": 0,
                        "icp_score": 0,
                        "matched_weight": 0,
                        "total_weight": 0,
                        "weighted": False,
                        "disqualified_by": dq,
                        "confidence_band": "disqualified",
                    },
                )

        matched = [sig for sig in positive_signals if _signal_present(lead, sig)]
        missing = [sig for sig in positive_signals if sig not in matched]
        optional_matched = [sig for sig in optional_signals if _signal_present(lead, sig)]
        negative_matched = [sig for sig in negative_signals if _signal_present(lead, sig)]

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

        optional_weight = sum(float(weights.get(s, 1)) for s in optional_matched)
        optional_bonus = min(15.0, optional_weight * 3.0)
        icp_score = min(30, len(icp_hits) * 10)

        # Sinal negativo é evidência observada contra a oferta, nunca a ausência
        # de um sinal positivo. O perfil decide o tamanho da penalidade.
        negative_penalty_each = float(signals.get("negative_penalty_each") or 0)
        negative_penalty = min(40.0, negative_penalty_each * len(negative_matched))

        score = int(max(0, min(100, signal_score + optional_bonus + icp_score - negative_penalty)))

        # Gates de qualidade são deliberadamente configuráveis por oferta.
        # Eles não inventam FALSE para informação desconhecida; só impedem que
        # um lead com evidência fraca pareça "pronto para prospectar".
        strong_evidence = list(quality_gates.get("strong_evidence_any") or [])
        strong_matched = [sig for sig in strong_evidence if _signal_present(lead, sig)]
        min_observed = int(quality_gates.get("min_observed_signals") or 0)
        observed_count = len(set([*matched, *optional_matched, *negative_matched]))
        capped_by: List[str] = []

        if strong_evidence and not strong_matched:
            cap = int(quality_gates.get("max_score_without_strong_evidence") or 100)
            if score > cap:
                score = cap
                capped_by.append("missing_strong_evidence")
        if min_observed and observed_count < min_observed:
            cap = int(quality_gates.get("max_score_with_sparse_evidence") or 100)
            if score > cap:
                score = cap
                capped_by.append("sparse_evidence")

        if strong_matched and score >= int(quality_gates.get("high_confidence_score") or 80):
            confidence_band = "high"
        elif score >= 60:
            confidence_band = "medium"
        else:
            confidence_band = "low"

        breakdown = {
            "signal_score": int(signal_score),
            "optional_bonus": int(optional_bonus),
            "negative_penalty": int(negative_penalty),
            "icp_score": icp_score,
            "matched_weight": matched_weight,
            "total_weight": total_weight,
            "weighted": weighted,
            "optional_signals_matched": optional_matched,
            "negative_signals_matched": negative_matched,
            "strong_evidence_matched": strong_matched,
            "observed_signal_count": observed_count,
            "capped_by": capped_by,
            "confidence_band": confidence_band,
        }

        all_matched = [*matched, *optional_matched]
        evidence = all_matched + [f"icp:{hit}" for hit in icp_hits]
        evidence.extend(f"negative:{sig}" for sig in negative_matched)
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
