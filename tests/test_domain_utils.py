"""Testes do utilitário de normalização de domínio (item 4.3)."""
from services.domain_utils import normalize_domain


def test_scheme_e_www_removidos():
    assert normalize_domain("https://www.Firma.com.br/pagina") == "firma.com.br"


def test_http_e_caminho():
    assert normalize_domain("http://exemplo.com/sobre") == "exemplo.com"


def test_sem_scheme():
    assert normalize_domain("www.exemplo.com.br") == "exemplo.com.br"


def test_query_e_anchor_removidos():
    assert normalize_domain("https://exemplo.com/abc?x=1#top") == "exemplo.com"


def test_lowercase():
    assert normalize_domain("HTTPS://EXEMPLO.COM.BR") == "exemplo.com.br"


def test_none_e_vazio():
    assert normalize_domain(None) is None
    assert normalize_domain("") is None
    assert normalize_domain("   ") is None
