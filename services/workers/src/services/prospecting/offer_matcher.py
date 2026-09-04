"""OfferMatcher (Fase C — consolidação §Fase C).

Associa uma empresa (lead) a múltiplas oportunidades simultâneas,
uma por OfferProfile relevante, com score (0-100), evidência e cascata
de resolução rastreável.

Critério da Fase C: "Uma empresa pode possuir múltiplas oportunidades
simultâneas" — modelo N:N entre lead e oferta.
"""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from services.prospecting.offer_profile import (
    OfferProfile,
    OfferProfileRegistry,
    OfferProfileResolver,
)


@dataclass(frozen=True)
class LeadOpportunity:
    """Uma oportunidade de venda associando um lead a um OfferProfile."""
    offer_key: str
    profile_key: str
    score: int  # 0-100
    evidence: List[str] = field(default_factory=list)
    resolved_from: str = "explicit"  # explicit|vertical|archetype|generic
    signals_matched: List[str] = field(default_factory=list)
    signals_missing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LeadOpportunity":
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})


class OfferMatcher:
    """Combina um lead com todos os OfferProfiles do registry e ranqueia.

    Score = (signals_positivos_presentes / signals_positivos_declarados) * 100
    + ajuste por ICP (segments, cnaes, company_sizes).
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
        """Retorna lista de LeadOpportunity ordenadas por score desc."""
        results: List[LeadOpportunity] = []
        for profile in self.registry.list():
            opp = self._score_profile(profile, lead_data)
            if opp is not None and opp.score >= min_score:
                results.append(opp)
        # Ordena por score decrescente
        results.sort(key=lambda o: o.score, reverse=True)
        if top_k is not None:
            results = results[:top_k]
        return results

    def _score_profile(
        self, profile: OfferProfile, lead: Dict[str, Any],
    ) -> Optional[LeadOpportunity]:
        """Calcula score de aderência entre um lead e um OfferProfile."""
        icp = profile.icp or {}
        signals = profile.signals or {}
        positive_signals = signals.get("positive", [])
        disqualifiers = signals.get("disqualifiers", [])

        # 1. Desqualificadores: se lead match, retorna score=0
        for dq in disqualifiers:
            if lead.get(dq.lower()) is True:
                return LeadOpportunity(
                    offer_key=profile.key,
                    profile_key=profile.archetype,
                    score=0,
                    evidence=[f"DISQUALIFIED_BY_{dq}"],
                    resolved_from="explicit",
                )

        # 2. Sinais positivos: quais estão presentes
        matched, missing = [], []
        for sig in positive_signals:
            if lead.get(sig.lower()) is True:
                matched.append(sig)
            else:
                missing.append(sig)

        # 3. ICP checks: segments, cnaes, company_sizes
        icp_hits = []
        if icp.get("segments") and lead.get("segment") in icp["segments"]:
            icp_hits.append("segment")
        if icp.get("cnaes") and (str(lead.get("cnae", "")).startswith(tuple(icp["cnaes"]))):
            icp_hits.append("cnae")
        if icp.get("company_sizes") and lead.get("company_size") in icp["company_sizes"]:
            icp_hits.append("company_size")

        # 4. Score combinado
        if positive_signals:
            signal_score = len(matched) / len(positive_signals) * 70
        else:
            signal_score = 50  # sem sinais declarados → neutro
        icp_score = min(30, len(icp_hits) * 10)
        score = int(min(100, signal_score + icp_score))

        evidence = matched + [f"icp:{h}" for h in icp_hits]
        if not evidence:
            # Sem match nenhum: não retorna
            return None

        return LeadOpportunity(
            offer_key=profile.key,
            profile_key=profile.archetype,
            score=score,
            evidence=evidence,
            resolved_from="explicit",
            signals_matched=matched,
            signals_missing=missing,
        )
