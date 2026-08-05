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


def test_dominio_social_retorna_none():
    # Redes sociais NÃO são site da empresa; retornar o domínio faria vários
    # leads distintos colidirem em (organization_id, normalized_domain).
    assert normalize_domain("https://www.instagram.com/thribocrossfit") is None
    assert normalize_domain("https://facebook.com/BlackfishCross") is None
    assert normalize_domain("https://www.linkedin.com/company/box-koru") is None
    assert normalize_domain("wa.me/5516999757387") is None
    assert normalize_domain("linktr.ee/elitecross") is None


def test_dominio_proprio_continua_normalizado():
    assert normalize_domain("https://www.thribo.com.br/") == "thribo.com.br"
    assert normalize_domain("https://boxkoru.com.br/sobre") == "boxkoru.com.br"
