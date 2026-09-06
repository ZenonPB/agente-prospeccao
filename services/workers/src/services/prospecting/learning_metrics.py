"""Learning & Metrics (Fase H — consolidação §Fase H).

Outcomes persistentes, métricas comerciais e comparação de versões.
Permite provar se uma alteração AUMENTOU ou REDUZIU a qualidade comercial.

Critério: "É possível provar se uma alteração aumentou ou reduziu a
qualidade comercial."
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


# ============================================================
# OutcomesRegistry — persistência de outcomes
# ============================================================

@dataclass
class Outcome:
    """Outcome comercial registrado para um lead."""
    id: str
    org_id: str
    offer_key: str
    outcome: str  # WON | LOST | NO_RESPONSE | MEETING | QUALIFIED
    lead_id: str
    value: float = 0.0
    provider: Optional[str] = None
    offer_version: Optional[str] = None
    outreach_at: Optional[str] = None  # ISO date
    recorded_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "org_id": self.org_id, "offer_key": self.offer_key,
            "outcome": self.outcome, "lead_id": self.lead_id, "value": self.value,
            "provider": self.provider, "offer_version": self.offer_version,
            "outreach_at": self.outreach_at, "recorded_at": self.recorded_at,
        }


class OutcomesRegistry:
    """Registry de outcomes comerciais. In-memory (v1); plugar DB depois."""

    def __init__(self):
        self._outcomes: List[Outcome] = []

    def record(
        self,
        org_id: str,
        offer_key: str,
        outcome: str,
        lead_id: str,
        value: float = 0.0,
        provider: Optional[str] = None,
        offer_version: Optional[str] = None,
        outreach_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registra um outcome e retorna como dict."""
        o = Outcome(
            id=str(uuid.uuid4()),
            org_id=org_id,
            offer_key=offer_key,
            outcome=outcome,
            lead_id=lead_id,
            value=value,
            provider=provider,
            offer_version=offer_version,
            outreach_at=outreach_at,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        self._outcomes.append(o)
        return o.to_dict()

    def query(
        self,
        org_id: Optional[str] = None,
        offer_key: Optional[str] = None,
        offer_version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filtra outcomes por org/offer/version."""
        results = [o.to_dict() for o in self._outcomes]
        if org_id is not None:
            results = [o for o in results if o["org_id"] == org_id]
        if offer_key is not None:
            results = [o for o in results if o["offer_key"] == offer_key]
        if offer_version is not None:
            results = [o for o in results if o["offer_version"] == offer_version]
        return results


# ============================================================
# CommercialMetrics — métricas por oferta/provider
# ============================================================

class CommercialMetrics:
    """Métricas comerciais agregadas a partir do OutcomesRegistry."""

    POSITIVE_OUTCOMES = frozenset({"WON", "MEETING", "QUALIFIED"})

    def __init__(self, registry: OutcomesRegistry):
        self.registry = registry

    def conversion_rate_by_offer(
        self, offer_key: str, offer_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Taxa de conversão (% WON) para uma oferta."""
        outcomes = self.registry.query(offer_key=offer_key, offer_version=offer_version)
        total = len(outcomes)
        wins = sum(1 for o in outcomes if o["outcome"] == "WON")
        rate = (wins / total * 100) if total else 0.0
        return {
            "offer_key": offer_key,
            "offer_version": offer_version,
            "total": total,
            "wins": wins,
            "conversion_rate": round(rate, 2),
        }

    def average_ticket(
        self, offer_key: str, offer_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ticket médio dos WONs de uma oferta."""
        outcomes = self.registry.query(offer_key=offer_key, offer_version=offer_version)
        won = [o for o in outcomes if o["outcome"] == "WON" and o.get("value", 0) > 0]
        if not won:
            return {"offer_key": offer_key, "average_ticket": 0.0, "sample_size": 0}
        avg = sum(o["value"] for o in won) / len(won)
        return {
            "offer_key": offer_key,
            "average_ticket": round(avg, 2),
            "sample_size": len(won),
        }

    def metrics_by_provider(
        self, offer_key: str, offer_version: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Métricas agrupadas por provider (qual provider tem melhor conversion?)."""
        outcomes = self.registry.query(offer_key=offer_key, offer_version=offer_version)
        by_provider: Dict[str, Dict[str, Any]] = {}
        for o in outcomes:
            prov = o.get("provider") or "unknown"
            if prov not in by_provider:
                by_provider[prov] = {"total": 0, "wins": 0, "value": 0.0}
            by_provider[prov]["total"] += 1
            if o["outcome"] == "WON":
                by_provider[prov]["wins"] += 1
                by_provider[prov]["value"] += o.get("value", 0.0)
        for prov, data in by_provider.items():
            data["conversion_rate"] = round(
                data["wins"] / data["total"] * 100, 2
            ) if data["total"] else 0.0
        return by_provider

    def time_to_conversion(
        self, offer_key: str, offer_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tempo médio (em dias) entre outreach e WON."""
        outcomes = self.registry.query(offer_key=offer_key, offer_version=offer_version)
        won_with_dates = [
            o for o in outcomes
            if o["outcome"] == "WON" and o.get("outreach_at")
        ]
        if not won_with_dates:
            return {"offer_key": offer_key, "average_days": 0.0, "sample_size": 0}
        deltas = []
        for o in won_with_dates:
            try:
                outreach = datetime.fromisoformat(
                    o["outreach_at"].replace("Z", "+00:00")
                )
                recorded = datetime.fromisoformat(
                    o["recorded_at"].replace("Z", "+00:00")
                )
                if outreach.tzinfo is None:
                    outreach = outreach.replace(tzinfo=timezone.utc)
                if recorded.tzinfo is None:
                    recorded = recorded.replace(tzinfo=timezone.utc)
                delta = (recorded - outreach).days
                if delta >= 0:
                    deltas.append(delta)
            except (ValueError, TypeError):
                continue
        if not deltas:
            return {"offer_key": offer_key, "average_days": 0.0, "sample_size": 0}
        return {
            "offer_key": offer_key,
            "average_days": round(sum(deltas) / len(deltas), 1),
            "sample_size": len(deltas),
        }


# ============================================================
# VersionComparator — A/B testing de versões
# ============================================================

class VersionComparator:
    """Compara duas versões da mesma oferta para detectar regressão/melhoria.

    Critério Fase H: 'provar se alteração aumentou ou reduziu a qualidade
    comercial'. A recomendação (`verdict`/`recommendation`) só é emitida com
    amostras mínimas nos dois lados E intervalos de Wilson (z=1.96) separados —
    nunca apenas pela taxa bruta (P1.8: aprendizado controlado).
    """

    Z_95 = 1.96

    def __init__(
        self, registry: OutcomesRegistry, min_samples: int = 10,
        regression_threshold: float = -5.0,  # -5pp = regressão
    ):
        self.registry = registry
        self.min_samples = min_samples
        self.regression_threshold = regression_threshold

    def _wilson_interval_pct(self, wins: int, total: int) -> Dict[str, float]:
        """Intervalo de confiança de Wilson (95%) em percentual 0-100."""
        if total <= 0:
            return {"low": 0.0, "high": 100.0}
        p = wins / total
        z2 = self.Z_95 ** 2
        center = (p + z2 / (2 * total)) / (1 + z2 / total)
        half = (
            self.Z_95
            * ((p * (1 - p) / total + z2 / (4 * total ** 2)) ** 0.5)
            / (1 + z2 / total)
        )
        return {
            "low": round(max(0.0, center - half) * 100, 2),
            "high": round(min(100.0, center + half) * 100, 2),
        }

    def compare(
        self, offer_key: str, v1: str, v2: str,
    ) -> Dict[str, Any]:
        """Compara v1 vs v2 da mesma oferta.

        Returns:
            {
                "offer_key": str,
                "v1": str, "v2": str,
                "v1_total": int, "v2_total": int,
                "v1_conversion": float, "v2_conversion": float,
                "delta": float,  # v2 - v1
                "is_regression": bool,
                "is_improvement": bool,
                "is_conclusive": bool,
                "reason": str | None,
                "v1": {..., "confidence_interval": {"low", "high"}},
                "v2": {..., "confidence_interval": {"low", "high"}},
                "verdict": "v1" | "v2" | "empate" | "inconclusivo",
                "recommendation": str | None,
                "is_statistically_significant": bool,
            }
        """
        m = CommercialMetrics(self.registry)
        r1 = m.conversion_rate_by_offer(offer_key, offer_version=v1)
        r2 = m.conversion_rate_by_offer(offer_key, offer_version=v2)
        v1_total = r1["total"]
        v2_total = r2["total"]
        v1_ci = self._wilson_interval_pct(r1["wins"], v1_total)
        v2_ci = self._wilson_interval_pct(r2["wins"], v2_total)

        def _base(significant: bool) -> Dict[str, Any]:
            return {
                "offer_key": offer_key,
                "v1": {"version": v1, "confidence_interval": v1_ci},
                "v2": {"version": v2, "confidence_interval": v2_ci},
                "v1_total": v1_total,
                "v2_total": v2_total,
                "v1_conversion": r1["conversion_rate"],
                "v2_conversion": r2["conversion_rate"],
                "delta": round(r2["conversion_rate"] - r1["conversion_rate"], 2),
                "is_statistically_significant": significant,
            }

        # Inconclusivo se samples insuficientes — nenhuma recomendação sai.
        if v1_total < self.min_samples or v2_total < self.min_samples:
            return {
                **_base(False),
                "is_regression": False,
                "is_improvement": False,
                "is_conclusive": False,
                "reason": "insufficient_samples",
                "verdict": "inconclusivo",
                "recommendation": None,
            }

        delta = round(r2["conversion_rate"] - r1["conversion_rate"], 2)
        is_regression = delta < self.regression_threshold
        is_improvement = delta > abs(self.regression_threshold)  # melhoria >= 5pp
        # Gate estatístico: intervalos separados ⇔ sem sobreposição.
        separated = v1_ci["high"] < v2_ci["low"] or v2_ci["high"] < v1_ci["low"]
        if not separated:
            return {
                **_base(False),
                "is_regression": is_regression,
                "is_improvement": is_improvement,
                "is_conclusive": True,
                "reason": "confidence_intervals_overlap",
                "verdict": "empate",
                "recommendation": None,
            }
        if v2_ci["low"] > v1_ci["high"]:
            verdict, winner = "v2", v2
        else:
            verdict, winner = "v1", v1
        return {
            **_base(True),
            "is_regression": is_regression,
            "is_improvement": is_improvement,
            "is_conclusive": True,
            "reason": None,
            "verdict": verdict,
            "recommendation": (
                f"Recomendado: versão {winner} da oferta {offer_key} "
                f"(intervalo de confiança 95% sem sobreposição). "
                f"Aplicação requer aprovação humana e registro de versão/autor."
            ),
        }
