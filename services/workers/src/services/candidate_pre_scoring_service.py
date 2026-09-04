"""CandidatePreScoringService — pré-ranking barato, determinístico e explicável.

Primeira camada de qualificação (docs/melhorias/01 e 06): roda sobre os dados
já coletados no discovery (Places), ANTES de CNPJ, auditoria de site, LLM e
contato. Sem chamada externa, sem LLM — mesma entrada + mesma configuração
produzem o mesmo score.

Oportunidade comercial ≠ ausência técnica: para Landing Pages, empresa sem
site MAS com Instagram, telefone e boa reputação Google pontua alto; empresa
sem nenhuma presença ativa pontua baixo. Os pesos vêm do perfil/vertical
(`prospecting_profile_service.resolve_prospecting_profile`), nunca hardcoded
aqui.

Cada sinal carrega o contrato do Signal Registry (docs/melhorias/20):
{key, value, source, confidence, observed_at, evidence} + `epistemic`
(SEMPRE "FACT" nesta fase — tudo aqui é dado observado na coleta, não
inferência).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SIGNAL_FACT = "FACT"


class CandidatePreScoringService:
    """Pré-scoring determinístico de candidatos pós-discovery."""

    def collect_signals(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extrai os sinais FACT do item bruto de coleta.

        Args:
            item: resultado do discovery (Places) já normalizado — chaves
                `name`, `website`, `phone`, `category`, `rating`,
                `rating_count`, `instagram_url`.

        Returns:
            Lista de sinais no contrato do registry v0 (dicts com key, value,
            source, confidence, observed_at, evidence, epistemic).
        """
        observed_at = datetime.now(timezone.utc).isoformat()

        def _signal(key, value, evidence, confidence=1.0):
            return {
                "key": key,
                "value": value,
                "source": "google_places",
                "confidence": confidence,
                "observed_at": observed_at,
                "evidence": evidence,
                "epistemic": SIGNAL_FACT,
            }

        signals: List[Dict[str, Any]] = []

        # `website` já chega normalizado: domínio social (Instagram etc.) vem
        # como None (places_service), então site presente = site próprio.
        if item.get("website"):
            signals.append(_signal("HAS_OWN_WEBSITE", True, f"site: {item['website']}"))
        else:
            signals.append(_signal("NO_OWN_WEBSITE", True, "sem site próprio registrado"))

        if item.get("instagram_url"):
            signals.append(_signal("HAS_INSTAGRAM", True, f"instagram: {item['instagram_url']}"))

        if item.get("phone"):
            signals.append(_signal("HAS_PHONE", True, f"telefone: {item['phone']}"))

        rating = item.get("rating")
        if rating is not None:
            signals.append(_signal("GOOGLE_RATING", rating, f"nota Google {rating}"))

        rating_count = item.get("rating_count")
        if rating_count:
            signals.append(
                _signal("GOOGLE_RATING_COUNT", rating_count, f"{rating_count} avaliações")
            )

        if item.get("category"):
            signals.append(_signal("HAS_CATEGORY", item["category"], f"categoria: {item['category']}"))

        return signals

    def score_candidate(self, item, profile):
        """Pontua um candidato com os pesos do perfil da vertical.

        Args:
            item: item bruto de coleta (mesmo formato de `collect_signals`).
            profile: saída de `resolve_prospecting_profile` — usa apenas
                `profile_key` e `prescoring.weights`/`threshold`.

        Returns:
            Dict com `discovery_score` (0-100), `score_factors`
            [{signal, impact, evidence}], `signals` (registry v0),
            `eligible_for_enrichment` (score >= threshold) e `summary`.
        """
        weights: Dict[str, Any] = profile.get("prescoring", {}).get("weights", {})
        threshold = profile.get("prescoring", {}).get("threshold", 0)

        signals = self.collect_signals(item)
        by_key = {s["key"]: s for s in signals}

        factors: List[Dict[str, Any]] = []
        score = 0
        # Itera os pesos (não os sinais) — ordem do dict do perfil é
        # determinística e um sinal sem peso simplesmente não pontua.
        for key, weight in weights.items():
            signal = by_key.get(key)
            if signal is None:
                continue
            try:
                w = int(weight)
            except (TypeError, ValueError):
                continue
            value = signal["value"]
            # Escala proporcional para sinais quantitativos (determinística).
            if key == "GOOGLE_RATING":
                impact = round(w * (float(value) / 5.0))
            elif key == "GOOGLE_RATING_COUNT":
                impact = round(w * min(float(value), 50.0) / 50.0)
            else:
                impact = w
            if impact == 0:
                continue
            score += impact
            factors.append({
                "signal": key,
                "impact": impact,
                "evidence": signal["evidence"],
            })

        score = max(0, min(100, score))
        factors.sort(key=lambda f: -f["impact"])

        top = ", ".join(f["signal"] for f in factors[:3]) if factors else "sem sinais"
        return {
            "discovery_score": score,
            "score_factors": factors,
            "signals": signals,
            "eligible_for_enrichment": score >= threshold,
            "summary": f"{profile.get('profile_key', '')} score={score} ({top})",
        }

    def select_candidates(self, items, profile):
        """Aplica o gate de promoção Candidate → Lead sobre o lote coletado.

        Args:
            items: itens brutos de coleta já deduplicados.
            profile: perfil resolvido (`resolve_prospecting_profile`).

        Returns:
            Tupla (selecionados, stats). Selecionados são os itens originais
            com `discovery_score`/`prescoring_summary` anotados, ordenados por
            score desc (empate: ordem original — estável). Respeita
            `prescoring.top_k` quando definido. Stats traz
            evaluated/eligible/discarded/top_score para o summary do job.
        """
        prescoring = profile.get("prescoring", {})
        if not prescoring.get("enabled"):
            return items, {"evaluated": 0, "eligible": len(items), "discarded": 0, "top_score": None}

        scored = [(item, self.score_candidate(item, profile)) for item in items]
        eligible = [(i, s) for i, s in scored if s["eligible_for_enrichment"]]
        # Ordenação estável: score desc, empates mantêm a ordem da coleta.
        eligible.sort(key=lambda pair: -pair[1]["discovery_score"])

        top_k = prescoring.get("top_k")
        if top_k:
            eligible = eligible[:top_k]

        selected: List[Dict[str, Any]] = []
        for item, s in eligible:
            annotated = {**item, "discovery_score": s["discovery_score"],
                         "prescoring_summary": s["summary"]}
            selected.append(annotated)

        discarded = len(items) - len(selected)
        top_score = eligible[0][1]["discovery_score"] if eligible else None
        stats = {
            "evaluated": len(items),
            "eligible": len(selected),
            "discarded": discarded,
            "top_score": top_score,
        }
        if discarded:
            logger.info(
                "Pre-scoring: %d/%d candidatos descartados (threshold=%s, perfil=%s)",
                discarded, len(items), prescoring.get("threshold"), profile.get("profile_key"),
            )
        return selected, stats
