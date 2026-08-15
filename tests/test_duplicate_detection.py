"""Testes do detector de duplicatas (item 4.27 pragmático)."""
from src.services.duplicate_detection_service import (
    find_duplicate_signals,
    _normalize_linkedin,
)


def _lead_dict(id_, company, cnpj="", domain="", contacts=None):
    return {
        "id": id_,
        "company_name": company,
        "cnpj": cnpj,
        "normalized_domain": domain,
        "contacts": contacts or [],
    }


def test_match_por_cnpj():
    target = _lead_dict("L1", "ACME", cnpj="12345678000199")
    other = _lead_dict("L2", "ACME Matriz", cnpj="12345678000199")
    matches = find_duplicate_signals(target, [other])
    assert len(matches) == 1
    assert "cnpj" in matches[0]["matched_by"]


def test_match_por_dominio_normalizado():
    target = _lead_dict("L1", "Habitus", domain="habitus.com.br")
    other = _lead_dict("L2", "Habitus Academia", domain="habitus.com.br")
    matches = find_duplicate_signals(target, [other])
    assert "normalized_domain" in matches[0]["matched_by"]


def test_match_por_email_de_contato():
    target = _lead_dict(
        "L1", "ACME", contacts=[{"email": "joao@acme.com", "linkedin_url": None}],
    )
    other = _lead_dict(
        "L2", "ACME Filial", contacts=[{"email": "joao@acme.com", "linkedin_url": None}],
    )
    matches = find_duplicate_signals(target, [other])
    assert "contact_email" in matches[0]["matched_by"]


def test_match_por_linkedin_normalizado():
    target = _lead_dict(
        "L1", "ACME",
        contacts=[{"email": None, "linkedin_url": "https://www.linkedin.com/in/joao-silva/"}],
    )
    other = _lead_dict(
        "L2", "ACME 2",
        contacts=[{"email": None, "linkedin_url": "https://linkedin.com/in/joao-silva"}],
    )
    matches = find_duplicate_signals(target, [other])
    assert "contact_linkedin" in matches[0]["matched_by"]


def test_sem_match_quando_nenhum_criterio():
    target = _lead_dict("L1", "ACME", cnpj="111", domain="acme.com",
                        contacts=[{"email": "a@a.com", "linkedin_url": "https://linkedin.com/in/a"}])
    other = _lead_dict("L2", "Outro", cnpj="222", domain="outro.com",
                       contacts=[{"email": "b@b.com", "linkedin_url": "https://linkedin.com/in/b"}])
    assert find_duplicate_signals(target, [other]) == []


def test_ignora_o_proprio_lead():
    target = _lead_dict("L1", "ACME", cnpj="111")
    matches = find_duplicate_signals(target, [target])
    assert matches == []


def test_normalize_linkedin_strip_query_e_www():
    assert _normalize_linkedin("https://www.linkedin.com/in/joao?utm=abc") == "in/joao"
    assert _normalize_linkedin("https://linkedin.com/company/acme/") == "company/acme"
    assert _normalize_linkedin(None) == ""
