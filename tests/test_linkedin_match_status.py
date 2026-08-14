"""Testes do estado de match do LinkedIn (derivado de fonte + confiança).

Cobrem a função pura `linkedin_match_status`: os quatro estados
(NOT_FOUND/CANDIDATE/NEEDS_REVIEW/VERIFIED) e as combinações relevantes de
origem (`search:*`, `heuristic`, `manual:<user>`, ausente) com confiança alta
ou baixa.
"""
from src.services.linkedin_assist_service import linkedin_match_status


def test_sem_url_eh_not_found():
    assert linkedin_match_status(None, None, None) == "NOT_FOUND"
    assert linkedin_match_status("", "search:duckduckgo", 75) == "NOT_FOUND"


def test_busca_por_nome_e_empresa_eh_verificado():
    assert linkedin_match_status(
        "https://www.linkedin.com/in/maria-silva", "search:bing", 75,
    ) == "VERIFIED"
    assert linkedin_match_status("https://www.linkedin.com/in/maria", "search:cached", 80) == "VERIFIED"


def test_heuristica_eh_candidato():
    assert linkedin_match_status(
        "https://www.linkedin.com/in/joao-silva", "heuristic", 60,
    ) == "CANDIDATE"


def test_manual_validado_eh_verificado():
    assert linkedin_match_status(
        "https://www.linkedin.com/in/maria", "manual:u1", 90,
    ) == "VERIFIED"


def test_manual_para_revisao_eh_needs_review():
    assert linkedin_match_status(
        "https://www.linkedin.com/in/maria", "manual:u1", 60,
    ) == "NEEDS_REVIEW"


def test_fonte_desconhecida_depende_da_confianca():
    assert linkedin_match_status("https://www.linkedin.com/in/maria", None, 95) == "VERIFIED"
    assert linkedin_match_status("https://www.linkedin.com/in/maria", None, 50) == "NEEDS_REVIEW"