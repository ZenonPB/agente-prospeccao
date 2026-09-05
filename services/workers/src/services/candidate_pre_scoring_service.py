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

Cada sinal carrega o contrato do Signal Registry (docs/melhorias/20 e 29):
{key, value, source, confidence, observed_at, evidence, evidence_refs,
epistemic, contributing_sources} — chaves canônicas em
`signal_registry.SignalKey`. SEMPRE FACT nesta fase: tudo aqui é dado
observado na coleta, não inferência.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from services.signal_registry import (
    EpistemicStatus,
    SignalKey,
    make_signal,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()



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
        observed_at = _now_iso()

        def _signal(key, value, evidence, confidence=1.0):
            return make_signal(
                key, value, source="google_places", confidence=confidence,
                evidence=evidence, observed_at=observed_at,
                epistemic=EpistemicStatus.FACT,
            )

        signals: List[Dict[str, Any]] = []

        # `website` já chega normalizado: domínio social (Instagram etc.) vem
        # como None (places_service), então site presente = site próprio.
        if item.get("website"):
            signals.append(_signal(
                SignalKey.HAS_OWN_WEBSITE, True, f"site: {item['website']}"))
        else:
            signals.append(_signal(
                SignalKey.NO_OWN_WEBSITE, True, "sem site próprio registrado"))

        if item.get("instagram_url"):
            signals.append(_signal(
                SignalKey.HAS_INSTAGRAM, True,
                f"instagram: {item['instagram_url']}"))

        if item.get("phone"):
            signals.append(_signal(
                SignalKey.HAS_PHONE, True, f"telefone: {item['phone']}"))

        rating = item.get("rating")
        if rating is not None:
            signals.append(_signal(
                SignalKey.GOOGLE_RATING, rating, f"nota Google {rating}"))

        rating_count = item.get("rating_count")
        if rating_count:
            signals.append(_signal(
                SignalKey.GOOGLE_RATING_COUNT, rating_count,
                f"{rating_count} avaliações"))

        if item.get("category"):
            signals.append(_signal(
                SignalKey.HAS_CATEGORY, item["category"],
                f"categoria: {item['category']}"))

        if item.get("cnae"):
            signals.append(_signal(
                SignalKey.CNAE, str(item["cnae"]),
                f"CNAE: {item['cnae']}"))

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
        prescoring = profile.get("prescoring", {})

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

        # Fronteira semântica do gate (Fase 2.x):
        #   1) se faltam sinais decisivos (required_signals não observados),
        #      status = INSUFFICIENT_DATA — não temos base para descartar.
        #   2) caso contrário, o velho score>=threshold:
        #      QUALIFIES se passa, DISQUALIFIES se não.
        required = [getattr(k, "value", str(k)) for k in (prescoring.get("required_signals") or [])]
        on_insufficient = prescoring.get("on_insufficient_data", "discard")
        observed_keys = {s["key"] for s in signals}
        missing_required = [k for k in required if k not in observed_keys]

        if missing_required:
            status = "INSUFFICIENT_DATA"
            eligible = (on_insufficient == "promote")
            promote_flag = eligible
        else:
            promote_flag = False
            if score >= threshold:
                status = "QUALIFIES"
                eligible = True
            else:
                status = "DISQUALIFIES"
                eligible = False

        return {
            "discovery_score": score,
            "score_factors": factors,
            "signals": signals,
            "eligible_for_enrichment": eligible,
            "discovery_status": status,
            "missing_required_signals": missing_required,
            "eligible_for_promotion_on_insufficient": promote_flag,
            "summary": f"{profile.get('profile_key', '')} score={score} ({top})"
                       + (f" [insufficient: {missing_required}]"
                          if missing_required else ""),
        }

    def select_candidates(self, items, profile, persist_fn=None, context=None):
        """Aplica o gate de promoção Candidate → Lead sobre o lote coletado.

        Args:
            items: itens brutos de coleta já deduplicados.
            profile: perfil resolvido (`resolve_prospecting_profile`).
            persist_fn: callback opcional `(records) -> None` para auditar os
                descartes (injetado pelo chamador — este serviço não toca DB).
                Falha do callback é logada e NUNCA interrompe o gate.
            context: dict opcional `{organization_id, campaign_id, job_id}`
                repassado nos records de descarte.

        Returns:
            Tupla (selecionados, stats). Selecionados são os itens originais
            com `discovery_score`/`prescoring_summary` anotados, ordenados por
            score desc (empate: ordem original — estável). Respeita
            `prescoring.top_k` quando definido. Stats separam
            `below_threshold` de `top_k_cut` (`discarded` = soma, para
            compatibilidade com consumidores do summary do job).
        """
        prescoring = profile.get("prescoring", {})
        if not prescoring.get("enabled"):
            return items, {
                "evaluated": 0, "eligible": len(items), "selected": len(items),
                "below_threshold": 0, "top_k_cut": 0, "discarded": 0,
                "top_score": None, "insufficient_data": 0,
                "insufficient_data_promoted": 0,
            }

        scored = [(item, self.score_candidate(item, profile)) for item in items]
        eligible = [
            (i, s) for i, s in scored
            if s["eligible_for_enrichment"]
            and s.get("discovery_status") != "INSUFFICIENT_DATA"
        ]
        below_threshold = [
            (i, s) for i, s in scored
            if not s["eligible_for_enrichment"]
            and s.get("discovery_status") != "INSUFFICIENT_DATA"
        ]
        insufficient = [
            (i, s) for i, s in scored
            if s.get("discovery_status") == "INSUFFICIENT_DATA"
        ]
        insufficient_promoted = [
            pair for pair in insufficient
            if pair[1].get("eligible_for_promotion_on_insufficient")
        ]
        insufficient_discarded = [
            pair for pair in insufficient if pair not in insufficient_promoted
        ]
        eligible.extend(insufficient_promoted)
        # Um mesmo par não pode entrar duas vezes quando o fluxo promove
        # insuficientes; a separação acima mantém as métricas claras.
        # Ordenação estável: score desc, empates mantêm a ordem da coleta.
        eligible.sort(key=lambda pair: -pair[1]["discovery_score"])

        top_k = prescoring.get("top_k")
        top_k_cut: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        if top_k:
            top_k_cut = eligible[top_k:]
            eligible = eligible[:top_k]

        selected: List[Dict[str, Any]] = []
        for item, s in eligible:
            annotated = {
                **item,
                "discovery_score": s["discovery_score"],
                "discovery_status": s.get("discovery_status"),
                "prescoring_summary": s["summary"],
            }
            selected.append(annotated)

        self._warn_orphan_weights(prescoring.get("weights") or {}, scored)

        discarded_records = (
            [self._discard_record(item, s, profile, prescoring, "below_threshold", context)
             for item, s in below_threshold]
            + [self._discard_record(item, s, profile, prescoring, "insufficient_data", context)
               for item, s in insufficient_discarded]
            + [self._discard_record(item, s, profile, prescoring, "top_k_cut", context)
               for item, s in top_k_cut]
        )
        if discarded_records and persist_fn:
            try:
                persist_fn(discarded_records)
            except Exception as e:
                # Auditoria é best-effort: nunca bloqueia o pipeline.
                logger.warning("Falha ao persistir descartes do pre-scoring: %s", e)

        top_score = eligible[0][1]["discovery_score"] if eligible else None
        stats = {
            "evaluated": len(items),
            "eligible": len(selected),
            "selected": len(selected),
            "below_threshold": len(below_threshold),
            "top_k_cut": len(top_k_cut),
            "discarded": len(below_threshold) + len(insufficient_discarded) + len(top_k_cut),
            "insufficient_data": len(insufficient_discarded),
            "insufficient_data_promoted": len(insufficient_promoted),
            "top_score": top_score,
        }
        if stats["discarded"]:
            logger.info(
                "Pre-scoring: %d/%d candidatos descartados "
                "(below_threshold=%d, top_k_cut=%d, threshold=%s, perfil=%s)",
                stats["discarded"], len(items), stats["below_threshold"],
                stats["top_k_cut"], prescoring.get("threshold"),
                profile.get("profile_key"),
            )
        return selected, stats

    def _discard_record(self, item, scored, profile, prescoring, reason, context):
        """Monta o registro de auditoria de um descarte."""
        ctx = context or {}
        return {
            "organization_id": ctx.get("organization_id"),
            "campaign_id": ctx.get("campaign_id"),
            "job_id": ctx.get("job_id"),
            "place_id": item.get("place_id"),
            "company_name": item.get("name") or item.get("company_name"),
            "candidate_data": item,
            "signals": scored["signals"],
            "discovery_score": scored["discovery_score"],
            "threshold": prescoring.get("threshold"),
            "profile_key": profile.get("profile_key"),
            "reason": reason,
        }

    def _warn_orphan_weights(self, weights, scored):
        """Peso declarado que não corresponde a sinal algum do lote quase
        sempre é typo de config — avisa uma vez por lote."""
        if not weights:
            return
        seen = {sig["key"] for _, s in scored for sig in s["signals"]}
        orphans = [k for k in weights if k not in seen]
        if orphans:
            logger.warning(
                "prescoring weights sem sinal correspondente no lote: %s "
                "(typo de config ou sinal nunca coletado)", orphans,
            )
