"""Signal Registry universal + status epistêmico (docs/melhorias/20 e 29).

Contrato único de sinal observável:
    {key, value, source, confidence, observed_at, evidence,
     evidence_refs, epistemic, contributing_sources}

Regras epistêmicas (doc 29):
- FACT exige fonte observável E evidência — sem elas o sinal é rebaixado
  para INFERENCE (nunca "fato sem prova").
- INFERENCE deriva de sinais existentes (fonte opcional).
- HYPOTHESIS é possibilidade a validar em contato — exige `evidence_refs`
  apontando para os sinais que a motivam.
- UNKNOWN não carrega valor: preencher por conveniência é proibido.

Verticais aplicam pesos diferentes ao MESMO signal — por isso as chaves são
canônicas aqui e os pesos ficam no template/perfil, nunca neste módulo.
"""
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EpistemicStatus(str, Enum):
    """Nível de certeza epistêmica de um sinal/afirmação (doc 29)."""

    FACT = "FACT"                # observado com fonte + evidência
    INFERENCE = "INFERENCE"      # derivado de fatos existentes
    HYPOTHESIS = "HYPOTHESIS"    # possibilidade a validar em contato
    UNKNOWN = "UNKNOWN"          # desconhecido — não inventar valor


# Ordem de força: o merge nunca funde num epistêmico mais fraco que o mais
# forte dos contribuidores; FACT só se AMBOS os lados forem FACT.
_EPISTEMIC_RANK = {
    EpistemicStatus.UNKNOWN: 0,
    EpistemicStatus.HYPOTHESIS: 1,
    EpistemicStatus.INFERENCE: 2,
    EpistemicStatus.FACT: 3,
}


class SignalKey:
    """Chaves canônicas do registry. Chaves novas entram aqui, não soltas em
    strings por serviço — é o que permite peso por vertical sem colisão
    semântica."""

    HAS_OWN_WEBSITE = "HAS_OWN_WEBSITE"
    NO_OWN_WEBSITE = "NO_OWN_WEBSITE"
    HAS_INSTAGRAM = "HAS_INSTAGRAM"
    HAS_PHONE = "HAS_PHONE"
    GOOGLE_RATING = "GOOGLE_RATING"
    GOOGLE_RATING_COUNT = "GOOGLE_RATING_COUNT"
    HAS_CATEGORY = "HAS_CATEGORY"
    CNAE = "CNAE"
    COMPANY_SIZE = "COMPANY_SIZE"
    NO_WEBSITE = "NO_WEBSITE"
    HAS_CUSTOMER_PORTAL = "HAS_CUSTOMER_PORTAL"
    HAS_CNC = "HAS_CNC"
    HIRING = "HIRING"
    EXPANDING = "EXPANDING"
    NEW_EQUIPMENT = "NEW_EQUIPMENT"
    NEW_BRANCH = "NEW_BRANCH"
    DECISION_MAKER_FOUND = "DECISION_MAKER_FOUND"
    VERIFIED_EMAIL = "VERIFIED_EMAIL"


# Metadados do registry: tipo de valor esperado e descrição semântica.
SIGNAL_REGISTRY: Dict[str, Dict[str, str]] = {
    SignalKey.HAS_OWN_WEBSITE: {
        "type": "bool", "description": "possui site próprio (não rede social)"},
    SignalKey.NO_OWN_WEBSITE: {
        "type": "bool", "description": "não possui site próprio"},
    SignalKey.HAS_INSTAGRAM: {
        "type": "bool", "description": "possui perfil ativo no Instagram"},
    SignalKey.HAS_PHONE: {
        "type": "bool", "description": "possui telefone público"},
    SignalKey.GOOGLE_RATING: {
        "type": "number", "description": "nota média no Google Maps"},
    SignalKey.GOOGLE_RATING_COUNT: {
        "type": "number", "description": "volume de avaliações no Google Maps"},
    SignalKey.HAS_CATEGORY: {
        "type": "str", "description": "categoria/places type do estabelecimento"},
    SignalKey.CNAE: {
        "type": "str", "description": "CNAE principal (Receita Federal)"},
    SignalKey.COMPANY_SIZE: {
        "type": "str", "description": "porte da empresa (MEI/ME/EPP/...)"},
    SignalKey.NO_WEBSITE: {
        "type": "bool", "description": "sem presença de site detectada"},
    SignalKey.HAS_CUSTOMER_PORTAL: {
        "type": "bool", "description": "opera portal/painel de cliente"},
    SignalKey.HAS_CNC: {
        "type": "bool", "description": "opera máquina CNC / comando numérico"},
    SignalKey.HIRING: {
        "type": "bool", "description": "com vagas abertas no momento"},
    SignalKey.EXPANDING: {
        "type": "bool", "description": "em expansão (obra, nova unidade, filial)"},
    SignalKey.NEW_EQUIPMENT: {
        "type": "bool", "description": "investiu em equipamento recente"},
    SignalKey.NEW_BRANCH: {
        "type": "bool", "description": "abriu unidade/filial recente"},
    SignalKey.DECISION_MAKER_FOUND: {
        "type": "bool", "description": "decisor identificado (nome + cargo)"},
    SignalKey.VERIFIED_EMAIL: {
        "type": "bool", "description": "e-mail verificado (deliverable)"},
}

# Registro de chaves legadas que NÃO devem receber novos usos.
DEPRECATED_KEYS: Dict[str, str] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_signal(
    key: str,
    value: Any,
    *,
    source: Optional[str] = None,
    confidence: float = 1.0,
    evidence: Optional[str] = None,
    observed_at: Optional[str] = None,
    epistemic: EpistemicStatus = EpistemicStatus.FACT,
    evidence_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Fábrica do contrato de sinal — aplica as regras epistêmicas do doc 29.

    FACT sem fonte ou sem evidência é rebaixado para INFERENCE (com warning),
    nunca retorna como fato sem prova. UNKNOWN exige `value=None`.
    """
    if not isinstance(key, str) or not key.strip():
        raise ValueError("signal key obrigatória")
    if key in DEPRECATED_KEYS:
        logger.warning("Sinal legado %s: %s", key, DEPRECATED_KEYS[key])

    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError(f"confidence fora de [0,1]: {confidence}")

    epistemic = EpistemicStatus(epistemic)

    if epistemic is EpistemicStatus.UNKNOWN:
        if value is not None:
            raise ValueError("UNKNOWN não pode carregar valor — não invente")
        value = None
    elif value is None:
        raise ValueError(f"{epistemic.value} exige value")

    if epistemic is EpistemicStatus.FACT:
        if not source or not evidence:
            logger.warning(
                "Sinal %s com epistemic FACT sem fonte/evidência — rebaixado "
                "para INFERENCE (doc 29: fato sem prova não é fato)", key)
            epistemic = EpistemicStatus.INFERENCE

    return {
        "key": key,
        "value": value,
        "source": source,
        "confidence": float(confidence),
        "observed_at": observed_at or _now_iso(),
        "evidence": evidence,
        "evidence_refs": list(evidence_refs) if evidence_refs else [],
        "epistemic": epistemic.value,
        "contributing_sources": [source] if source else [],
    }


def validate_signal(sig: Dict[str, Any]) -> List[str]:
    """Valida um sinal (dict) contra o contrato; retorna lista de problemas
    (vazia = válido). Não lança — para uso em auditoria/testes sobre dados
    que podem ter vindo de fontes antigas."""
    problems: List[str] = []
    if not sig.get("key"):
        problems.append("sem key")
    conf = sig.get("confidence")
    if conf is None or not 0.0 <= float(conf) <= 1.0:
        problems.append(f"confidence inválida: {conf}")
    ep = sig.get("epistemic")
    try:
        status = EpistemicStatus(ep)
    except ValueError:
        problems.append(f"epistemic inválido: {ep}")
        return problems
    if status is EpistemicStatus.FACT and (not sig.get("source") or not sig.get("evidence")):
        problems.append("FACT sem fonte/evidência")
    if status is EpistemicStatus.UNKNOWN and sig.get("value") is not None:
        problems.append("UNKNOWN com valor")
    if status is not EpistemicStatus.UNKNOWN and sig.get("value") is None:
        problems.append(f"{status.value} sem valor")
    refs = sig.get("evidence_refs")
    if refs is not None and not isinstance(refs, list):
        problems.append("evidence_refs não é lista")
    return problems


def _norm_evidence(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def merge_signals(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Funde dois sinais da MESMA chave contribuídos por providers distintos
    (critério de aceite do doc 20: evidência sem duplicação semântica).

    - evidence: união com dedupe por texto normalizado (case/space-insensitive)
    - contributing_sources: união das fontes
    - confidence: máximo dos dois
    - observed_at: o mais recente
    - epistemic: FACT se ambos forem FACT; senão o mais forte disponível
      (a fábrica ainda pode rebaixar se o resultado perder fonte/evidência)
    """
    if a.get("key") != b.get("key"):
        raise ValueError(
            f"merge exige mesma key: {a.get('key')!r} != {b.get('key')!r}")

    merged_evidence: List[str] = []
    seen: set = set()
    for e in (a.get("evidence"), b.get("evidence")):
        if e:
            n = _norm_evidence(e)
            if n not in seen:
                seen.add(n)
                merged_evidence.append(e)
    evidence = "; ".join(merged_evidence) if merged_evidence else None

    sources = [s for s in (a.get("source"), b.get("source")) if s]
    contributing = sorted({
        s for sig in (a, b) for s in (sig.get("contributing_sources") or []) if s
    } | set(sources))

    statuses = [
        EpistemicStatus(s.get("epistemic", EpistemicStatus.INFERENCE.value))
        for s in (a, b)
    ]
    if all(st is EpistemicStatus.FACT for st in statuses):
        epistemic = EpistemicStatus.FACT
    else:
        epistemic = max(statuses, key=lambda st: _EPISTEMIC_RANK[st])

    refs: List[str] = []
    for sig in (a, b):
        for r in sig.get("evidence_refs") or []:
            if r not in refs:
                refs.append(r)

    conf = max(float(a.get("confidence") or 0), float(b.get("confidence") or 0))
    observed = max(a.get("observed_at") or "", b.get("observed_at") or "") or None

    # Providers divergem no valor: mantém o de maior confiança, mas o conflito
    # permanece auditável nas duas evidências concatenadas.
    if a.get("value") != b.get("value"):
        winner = a if float(a.get("confidence") or 0) >= float(b.get("confidence") or 0) else b
        value = winner.get("value")
    else:
        value = a.get("value")

    merged = make_signal(
        a["key"], value, source=sources[0] if sources else None,
        confidence=conf, evidence=evidence, observed_at=observed,
        epistemic=epistemic, evidence_refs=refs,
    )
    merged["contributing_sources"] = contributing
    return merged


def to_statement(sig: Dict[str, Any]) -> Dict[str, Any]:
    """Converte um sinal no contrato de afirmação do doc 29:
    {statement, epistemic_status, confidence, evidence_refs}."""
    return {
        "statement": str(sig.get("evidence") or sig.get("key")),
        "epistemic_status": sig.get("epistemic", EpistemicStatus.UNKNOWN.value),
        "confidence": sig.get("confidence"),
        "evidence_refs": list(sig.get("evidence_refs") or []),
    }


