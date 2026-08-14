"""Testes da busca passiva da página da empresa no LinkedIn (company page).

Cobrem as funções puras `extract_linkedin_company_slug` (extração/validação do
slug) e `pick_linkedin_company_url` (elegge a company page cujo slug mais se
parece com o nome da empresa entre os resultados de busca).
"""
from services.contact_enrichment_service import (
    extract_linkedin_company_slug,
    pick_linkedin_company_url,
)


def test_extrai_slug_de_url_valida():
    assert extract_linkedin_company_slug("https://www.linkedin.com/company/alphamec") == "alphamec"
    assert extract_linkedin_company_slug("linkedin.com/company/empresa-x") == "empresa-x"
    assert extract_linkedin_company_slug("https://br.linkedin.com/company/mecanica-ltda") == "mecanica-ltda"
    assert extract_linkedin_company_slug("https://www.linkedin.com/company/mecanica-ltda/") == "mecanica-ltda"


def test_slug_invalido_ou_sem_url_retorna_none():
    assert extract_linkedin_company_slug("") is None
    assert extract_linkedin_company_slug(None) is None
    assert extract_linkedin_company_slug("https://www.linkedin.com/in/maria-silva") is None
    assert extract_linkedin_company_slug("https://www.linkedin.com/company/") is None
    assert extract_linkedin_company_slug("https://example.com/company/x") is None


def test_pick_escolhe_slug_com_maior_overlap():
    urls = [
        "https://www.linkedin.com/company/mecanica-xzy",
        "https://www.linkedin.com/company/mecanica-vieira",
        "https://www.linkedin.com/company/mecanica-vieira-servicos",
    ]
    assert pick_linkedin_company_url(urls, "Mecânica Vieira") == (
        "https://www.linkedin.com/company/mecanica-vieira"
    )


def test_pick_ignora_resultados_sem_overlap():
    urls = [
        "https://www.linkedin.com/company/outra-pagina",
        "https://www.linkedin.com/company/blog",
    ]
    assert pick_linkedin_company_url(urls, "Autopeças Silva") is None


def test_pick_com_lista_vazia_ou_nome_vazio():
    assert pick_linkedin_company_url([], "Empresa") is None
    assert pick_linkedin_company_url(["https://www.linkedin.com/company/x"], "") is None