"""Detecção de leads duplicados na mesma organização.

Foco pragmático do item 4.27: identificamos matches prováveis por
identidade compartilhada, sem propor mutação (a unificação real exigirá
o modelo Company/Person/Employment — adiado). Saída normalizada para a
UI exibir "Possível duplicata" com os critérios que bateram.

Critérios checados (qualquer um verdadeiro = match):
- Empresa: mesmo `cnpj` (não vazio) ou mesmo `normalized_domain`.
- Pessoa: algum contato do lead A com `email` ou `linkedin_url`
  compatível com algum contato do lead B (mesma string normalizada).
"""
import re
from typing import Dict, Iterable, List, Optional


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _normalize_linkedin(value: Optional[str]) -> str:
    if not value:
        return ""
    raw = value.strip().lower()
    # Extrai apenas "/in/<handle>" ou "/company/<slug>" — descarta querystring.
    match = re.search(r"/(in|company)/([a-z0-9\-_.]+)", raw)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return raw


def find_duplicate_signals(target: Dict, others: Iterable[Dict]) -> List[Dict]:
    """Compara `target` contra cada lead de `others` e devolve a lista de
    matches com os critérios que bateram.

    Cada item de `target`/`others` é um dict com chaves:
    - `id`, `company_name`, `cnpj`, `normalized_domain`
    - `contacts` (lista de dicts com `email`, `linkedin_url`)

    Retorna lista de `{"lead_id", "matched_by": [...]}` — pode haver mais
    de um critério por par.
    """
    matches: List[Dict] = []
    target_cnpj = _norm(target.get("cnpj"))
    target_domain = _norm(target.get("normalized_domain"))
    target_company_id = str(target.get("company_id")) if target.get("company_id") else None
    target_person_id = str(target.get("primary_person_id")) if target.get("primary_person_id") else None
    target_emails = {_norm(c.get("email")) for c in (target.get("contacts") or []) if c.get("email")}
    target_linkedins = {_normalize_linkedin(c.get("linkedin_url")) for c in (target.get("contacts") or []) if c.get("linkedin_url")}

    for other in others:
        if str(other.get("id")) == str(target.get("id")):
            continue
        criteria: List[str] = []
        other_company_id = str(other.get("company_id")) if other.get("company_id") else None
        other_person_id = str(other.get("primary_person_id")) if other.get("primary_person_id") else None

        if target_company_id and other_company_id and target_company_id == other_company_id:
            criteria.append("company_id")
        if target_person_id and other_person_id and target_person_id == other_person_id:
            criteria.append("person_id")

        other_cnpj = _norm(other.get("cnpj"))
        if target_cnpj and other_cnpj and target_cnpj == other_cnpj and "company_id" not in criteria:
            criteria.append("cnpj")
        other_domain = _norm(other.get("normalized_domain"))
        if target_domain and other_domain and target_domain == other_domain and "company_id" not in criteria:
            criteria.append("normalized_domain")
        other_emails = {_norm(c.get("email")) for c in (other.get("contacts") or []) if c.get("email")}
        if target_emails & other_emails and "person_id" not in criteria:
            criteria.append("contact_email")
        other_linkedins = {_normalize_linkedin(c.get("linkedin_url")) for c in (other.get("contacts") or []) if c.get("linkedin_url")}
        if target_linkedins & other_linkedins and "person_id" not in criteria:
            criteria.append("contact_linkedin")

        if criteria:
            matches.append({
                "lead_id": str(other.get("id")),
                "company_name": other.get("company_name"),
                "matched_by": criteria,
                "company_id": other_company_id,
                "primary_person_id": other_person_id,
            })
    return matches
