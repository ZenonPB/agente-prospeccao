"""Chain Detection (#13) — detecta franquias, redes, enterprise e independentes.

Seam: lead_data (domínio, CNPJ, nome, telefone, addresses) → classificação.
Usa apenas evidências observadas (passivo), sem sondagem.
Classifica: INDEPENDENT, SMALL_CHAIN, FRANCHISE, ENTERPRISE, UNKNOWN.
"""
from typing import Any, Dict, List, Optional

INDEPENDENT = "INDEPENDENT"
SMALL_CHAIN = "SMALL_CHAIN"
FRANCHISE = "FRANCHISE"
ENTERPRISE = "ENTERPRISE"
UNKNOWN = "UNKNOWN"


def detect_chain(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """Classifica o tipo de negócio com base em evidências observadas."""
    domain = (lead_data.get("domain") or "").strip().lower()
    company_name = (lead_data.get("company_name") or lead_data.get("name") or "").strip().lower()
    cnpj = lead_data.get("cnpj") or lead_data.get("cnpj_raw")
    addresses = lead_data.get("addresses") or lead_data.get("places_addresses") or []
    phone = (lead_data.get("phone") or "").strip()

    evidence = []
    chain_score = 0  # 0=independente, alto=rede

    # Evidência 1: múltiplos endereços com mesmo nome
    same_name_addrs = [a for a in addresses if isinstance(a, dict) and company_name and company_name in (a.get("name") or "").lower()]
    if len(same_name_addrs) >= 3:
        chain_score += 3
        evidence.append({"type": "same_name_many_locations", "count": len(same_name_addrs), "weight": 3})
    elif len(same_name_addrs) == 2:
        chain_score += 1
        evidence.append({"type": "same_name_two_locations", "count": 2, "weight": 1})

    # Evidência 2: seletor de lojas no nome/endereço
    selector_hints = ["unidade", "filial", "loja", "shopping", "piso", "sala"]
    if any(h in company_name for h in selector_hints):
        chain_score += 2
        evidence.append({"type": "store_selector_in_name", "weight": 2})

    # Evidência 3: CNPJ termina com 0001-XX (matriz/filial)
    if cnpj and len(cnpj) >= 8:
        suffix = cnpj.replace(".","").replace("/","").replace("-","")[-6:]
        if suffix.startswith("0001"):
            chain_score += 2
            evidence.append({"type": "cnpj_matrix_pattern", "weight": 2})

    # Evidência 4: telefone único em vários endereços (rede usa número único)
    if phone and len(same_name_addrs) >= 2:
        chain_score += 1
        evidence.append({"type": "shared_phone_many_locations", "weight": 1})

    # Classificação por score
    classification = UNKNOWN
    confidence = 0.3
    if chain_score >= 5:
        classification = ENTERPRISE
        confidence = 0.85
    elif chain_score >= 3:
        classification = FRANCHISE
        confidence = 0.7
    elif chain_score >= 2:
        classification = SMALL_CHAIN
        confidence = 0.6
    elif chain_score == 0 and (company_name or domain):
        classification = INDEPENDENT
        confidence = 0.5  # baixa confiança sem evidência positiva

    # UNKNOWN nunca é penalizado automaticamente (regra do doc 13)
    return {
        "classification": classification,
        "confidence": min(confidence, 0.95),
        "chain_score": chain_score,
        "evidence": evidence,
        "source": "chain_detection_service",
        "profile_hint": "excluded" if classification in (FRANCHISE, ENTERPRISE) else "independent_ok",
    }
