"""Validação semântica de OfferProfile.

Função pura: `validate_profile(profile)` devolve a lista de problemas
(vazia = válido). Avisos representam extensões possivelmente legítimas; erros
representam contratos que o motor não consegue executar com segurança.
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"^\d+\.\d+$")
_UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

KNOWN_CHANNELS = frozenset({"email", "phone", "whatsapp", "instagram", "linkedin"})
KNOWN_BUYER_TYPES = frozenset({
    "ECONOMIC_BUYER", "TECHNICAL_BUYER", "CHAMPION", "END_USER", "INFLUENCER",
})
KNOWN_INSUFFICIENT_DATA = frozenset({"discard", "promote", "review"})
KNOWN_DISCOVERY_PROVIDERS = frozenset({
    "google_places", "cnae_discovery", "instagram_search", "event_search",
    "csv_import", "pncp_search", "job_search", "company_news",
})
LEGACY_ENRICHMENT_STEPS = frozenset({"cnpj_qsa"})


def validate_profile(profile: Any) -> List[str]:
    problems: List[str] = []
    get = (lambda k, d=None: profile.get(k, d)) if isinstance(profile, dict) \
        else (lambda k, d=None: getattr(profile, k, d))

    key = get("key")
    if not isinstance(key, str) or not key.strip():
        problems.append("key vazia ou ausente")
    archetype = get("archetype")
    if not isinstance(archetype, str) or not archetype.strip():
        problems.append("archetype vazio ou ausente")
    vertical = get("vertical")
    if not isinstance(vertical, str) or not vertical.strip():
        problems.append("vertical vazio ou ausente")
    version = get("version")
    if not isinstance(version, str) or not _VERSION_RE.match(version.strip()):
        problems.append(f"version fora do formato X.Y: {version!r}")

    problems.extend(_validate_prescoring(get("prescoring") or {}))
    problems.extend(_validate_intent(get("intent") or {}))
    problems.extend(_validate_decision_makers(get("decision_makers") or {}))
    problems.extend(_validate_channels(get("channels") or {}))
    problems.extend(_validate_enrichment(get("enrichment") or {}))
    problems.extend(_validate_discovery(get("discovery") or {}))
    problems.extend(_validate_quality_gates(get("qualification") or {}))
    problems.extend(_validate_signals(get))
    return problems


def _validate_prescoring(prescoring: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(prescoring, dict):
        return ["prescoring não é um objeto"]
    threshold = prescoring.get("threshold")
    if threshold is not None and (not isinstance(threshold, (int, float)) or not 0 <= threshold <= 100):
        problems.append(f"prescoring.threshold fora de [0,100]: {threshold!r}")
    top_k = prescoring.get("top_k")
    if top_k is not None and (not isinstance(top_k, int) or top_k <= 0):
        problems.append(f"prescoring.top_k deve ser inteiro positivo: {top_k!r}")
    weights = prescoring.get("weights")
    if weights is not None:
        if not isinstance(weights, dict):
            problems.append("prescoring.weights não é um objeto")
        else:
            for signal, weight in weights.items():
                if not isinstance(weight, (int, float)) or weight < 0:
                    problems.append(f"prescoring.weights[{signal}] inválido: {weight!r}")
    on_insufficient = prescoring.get("on_insufficient_data")
    if on_insufficient is not None and on_insufficient not in KNOWN_INSUFFICIENT_DATA:
        problems.append(f"prescoring.on_insufficient_data desconhecido: {on_insufficient!r}")
    required = prescoring.get("required_signals")
    if required is not None and (not isinstance(required, list) or not all(isinstance(s, str) and s.strip() for s in required)):
        problems.append("prescoring.required_signals deve ser lista de strings")
    return problems


def _validate_intent(intent: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(intent, dict):
        return ["intent não é um objeto"]
    event_weights = intent.get("event_weights")
    if event_weights is not None:
        if not isinstance(event_weights, dict):
            problems.append("intent.event_weights não é um objeto")
        else:
            for event, weight in event_weights.items():
                if not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
                    problems.append(f"intent.event_weights[{event}] fora de [0,1]: {weight!r}")
    decay_days = intent.get("decay_days")
    if decay_days is not None and (not isinstance(decay_days, (int, float)) or decay_days <= 0):
        problems.append(f"intent.decay_days deve ser positivo: {decay_days!r}")
    trigger = intent.get("trigger_threshold")
    if trigger is not None and (not isinstance(trigger, (int, float)) or not 0 <= trigger <= 1):
        problems.append(f"intent.trigger_threshold fora de [0,1]: {trigger!r}")
    return problems


def _validate_decision_makers(decision_makers: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(decision_makers, dict):
        return ["decision_makers não é um objeto"]
    roles = decision_makers.get("roles")
    if not isinstance(roles, list) or not roles or not all(isinstance(r, str) and r.strip() for r in roles):
        problems.append("decision_makers.roles vazio ou inválido")
    buyer_types = decision_makers.get("buyer_types")
    if buyer_types is not None:
        if not isinstance(buyer_types, list):
            problems.append("decision_makers.buyer_types não é lista")
        else:
            for buyer in buyer_types:
                if buyer not in KNOWN_BUYER_TYPES:
                    problems.append(f"decision_makers.buyer_types desconhecido: {buyer!r}")
    return problems


def _validate_channels(channels: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(channels, dict):
        return ["channels não é um objeto"]
    priority = channels.get("priority")
    if priority is not None:
        if not isinstance(priority, list) or not priority:
            problems.append("channels.priority vazio ou inválido")
        else:
            for channel in priority:
                if channel not in KNOWN_CHANNELS:
                    problems.append(f"channels.priority desconhecido: {channel!r}")
    return problems


def _validate_enrichment(enrichment: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(enrichment, dict):
        return ["enrichment não é um objeto"]
    try:
        from services.enrichment_capability_registry import ENRICHMENT_STEP_KEYS
        known_steps = set(ENRICHMENT_STEP_KEYS) | set(LEGACY_ENRICHMENT_STEPS)
    except ImportError:  # pragma: no cover
        known_steps = set(LEGACY_ENRICHMENT_STEPS)
    steps = enrichment.get("steps")
    if steps is not None:
        if not isinstance(steps, list):
            problems.append("enrichment.steps não é lista")
        else:
            for step in steps:
                if step in LEGACY_ENRICHMENT_STEPS:
                    problems.append(f"aviso: enrichment.steps legado: {step!r} (coberto por cnpj_receita)")
                elif step not in known_steps:
                    problems.append(f"enrichment.steps desconhecido: {step!r}")
    people = enrichment.get("people_discovery")
    if people is not None:
        if not isinstance(people, dict):
            problems.append("enrichment.people_discovery não é um objeto")
        else:
            max_cost = people.get("max_cost")
            if max_cost is not None and (not isinstance(max_cost, (int, float)) or not 0 <= max_cost <= 1000):
                problems.append(f"enrichment.people_discovery.max_cost fora de [0,1000]: {max_cost!r}")
            max_steps = people.get("max_steps")
            if max_steps is not None and (not isinstance(max_steps, int) or not 1 <= max_steps <= 20):
                problems.append(f"enrichment.people_discovery.max_steps fora de [1,20]: {max_steps!r}")
            min_role_fit = people.get("min_role_fit")
            if min_role_fit is not None and (not isinstance(min_role_fit, (int, float)) or not 0 <= min_role_fit <= 100):
                problems.append(f"enrichment.people_discovery.min_role_fit fora de [0,100]: {min_role_fit!r}")
            min_identity = people.get("min_identity_confidence")
            if min_identity is not None and (not isinstance(min_identity, (int, float)) or not 0 <= min_identity <= 100):
                problems.append(f"enrichment.people_discovery.min_identity_confidence fora de [0,100]: {min_identity!r}")
            required_buyer = people.get("required_buyer_role")
            if required_buyer is not None:
                candidates = [required_buyer] if isinstance(required_buyer, str) else required_buyer if isinstance(required_buyer, list) else None
                if candidates is None or not all(isinstance(item, str) and item.strip() for item in candidates):
                    problems.append(f"enrichment.people_discovery.required_buyer_role deve ser string ou lista de strings: {required_buyer!r}")
                else:
                    for item in candidates:
                        if item.strip().upper() not in KNOWN_BUYER_TYPES:
                            problems.append(f"enrichment.people_discovery.required_buyer_role desconhecido: {item!r}")
    return problems


def _validate_discovery(discovery: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(discovery, dict):
        return ["discovery não é um objeto"]
    providers = discovery.get("providers")
    if providers is not None:
        if not isinstance(providers, list) or not providers:
            problems.append("discovery.providers vazio ou inválido")
        else:
            for provider in providers:
                if provider not in KNOWN_DISCOVERY_PROVIDERS:
                    problems.append(f"aviso: discovery.providers desconhecido: {provider!r}")
    return problems


def _validate_quality_gates(qualification: Any) -> List[str]:
    if not isinstance(qualification, dict):
        return ["qualification não é um objeto"]
    gates = qualification.get("quality_gates")
    if gates is None:
        return []
    if not isinstance(gates, dict):
        return ["qualification.quality_gates não é um objeto"]
    problems: List[str] = []
    evidence = gates.get("strong_evidence_any")
    if evidence is not None and (not isinstance(evidence, list) or not all(isinstance(item, str) and item for item in evidence)):
        problems.append("quality_gates.strong_evidence_any deve ser lista de sinais")
    min_observed = gates.get("min_observed_signals")
    if min_observed is not None and (not isinstance(min_observed, int) or min_observed < 0):
        problems.append("quality_gates.min_observed_signals deve ser inteiro >= 0")
    for key in ("max_score_without_strong_evidence", "max_score_with_sparse_evidence", "high_confidence_score"):
        value = gates.get(key)
        if value is not None and (not isinstance(value, (int, float)) or not 0 <= value <= 100):
            problems.append(f"quality_gates.{key} fora de [0,100]: {value!r}")
    return problems


def _signal_refs(get) -> List[str]:
    refs: List[str] = []
    prescoring = get("prescoring") or {}
    if isinstance(prescoring, dict):
        weights = prescoring.get("weights")
        if isinstance(weights, dict):
            refs.extend(weights.keys())
        required = prescoring.get("required_signals")
        if isinstance(required, list):
            refs.extend(s for s in required if isinstance(s, str))
    signals = get("signals") or {}
    if isinstance(signals, dict):
        for section in ("positive", "optional_positive", "negative", "disqualifiers"):
            values = signals.get(section)
            if isinstance(values, list):
                refs.extend(s for s in values if isinstance(s, str))
        weights = signals.get("weights")
        if isinstance(weights, dict):
            refs.extend(s for s in weights if isinstance(s, str))
    outreach = get("outreach") or {}
    if isinstance(outreach, dict):
        evidence = outreach.get("evidence_requirements")
        if isinstance(evidence, list):
            refs.extend(s for s in evidence if isinstance(s, str))
    qualification = get("qualification") or {}
    gates = qualification.get("quality_gates") if isinstance(qualification, dict) else None
    if isinstance(gates, dict):
        evidence = gates.get("strong_evidence_any")
        if isinstance(evidence, list):
            refs.extend(s for s in evidence if isinstance(s, str))
    return refs


def _validate_signals(get) -> List[str]:
    problems: List[str] = []
    try:
        from services.signal_registry import SIGNAL_REGISTRY
        known = set(SIGNAL_REGISTRY)
    except ImportError:  # pragma: no cover
        known = set()
    for ref in _signal_refs(get):
        if not _UPPER_SNAKE_RE.match(ref):
            problems.append(f"signal fora do padrão UPPER_SNAKE: {ref!r}")
        elif ref not in known:
            problems.append(f"signal desconhecido no registry: {ref!r}")
    intent = get("intent") or {}
    event_weights = intent.get("event_weights") if isinstance(intent, dict) else None
    if isinstance(event_weights, dict):
        for event in event_weights:
            if not isinstance(event, str) or not _UPPER_SNAKE_RE.match(event):
                problems.append(f"intent.event_weights fora do padrão: {event!r}")
            elif event not in known:
                problems.append(f"aviso: intent.event_weights fora do registry: {event!r}")
    return problems


def validate_registry(registry: Any) -> Dict[str, List[str]]:
    invalid: Dict[str, List[str]] = {}
    for profile in registry.list():
        problems = validate_profile(profile)
        errors = [p for p in problems if not p.startswith("aviso:")]
        warnings = [p for p in problems if p.startswith("aviso:")]
        for warning in warnings:
            logger.warning("OfferProfile %s: %s", profile.key, warning)
        if errors:
            invalid[profile.key] = errors
    return invalid
