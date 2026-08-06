"""Testes das funções puras do importador de CSV (item 2.1/4.3).

Não tocam o banco — cobrem sanitização, place_id determinístico e mapeamento
de cabeçalhos.
"""
from src.services.csv_import_service import (
    clean_url,
    clean_cnpj,
    generate_csv_place_id,
    normalize_header,
    normalize_import_website,
)


def test_clean_url_forca_https():
    assert clean_url("firma.com.br") == "https://firma.com.br"
    assert clean_url("http://firma.com.br") == "http://firma.com.br"
    assert clean_url(" https://firma.com.br/x ") == "https://firma.com.br/x"
    assert clean_url(None) is None
    assert clean_url("  ") is None


def test_clean_cnpj_so_digitos():
    assert clean_cnpj("12.345.678/0001-95") == "12345678000195"
    assert clean_cnpj("12345678") is None  # CNPJ inválido (curto)
    assert clean_cnpj(None) is None


def test_place_id_deterministico():
    a = generate_csv_place_id("Padaria Estrela", "Araraquara", "https://padaria.com")
    b = generate_csv_place_id("Padaria Estrela", "Araraquara", "https://padaria.com")
    c = generate_csv_place_id("Padaria Estrela", "Araraquara", "https://outro.com")
    assert a == b
    assert a != c


def test_normalize_header_aliases():
    assert normalize_header("Nome da Empresa") == "name"
    assert normalize_header("telefone") == "phone"
    assert normalize_header("whatsapp") == "whatsapp"
    assert normalize_header("documento") == "cnpj"
    assert normalize_header("linkedin") == "linkedin"
    assert normalize_header("coluna desconhecida") == "coluna_desconhecida"


def test_normalize_import_website_mantem_site_proprio():
    assert normalize_import_website("firma.com.br") == "https://firma.com.br"
    assert normalize_import_website("https://www.boxkoru.com.br/sobre") == "https://www.boxkoru.com.br/sobre"
    assert normalize_import_website(None) is None


def test_normalize_import_website_anula_sem_site_proprio():
    # Ferramenta (Canva/WhatsApp), rede social e marketplace = "sem site próprio"
    # (roadmap-leads S3 no caminho CSV) — o lead não deve ser tratado como "tem site".
    assert normalize_import_website("canva.link/artigo") is None
    assert normalize_import_website("https://api.whatsapp.com/send?phone=55") is None
    assert normalize_import_website("https://www.instagram.com/loja") is None
    assert normalize_import_website("https://instadelivery.com.br/perfil") is None
