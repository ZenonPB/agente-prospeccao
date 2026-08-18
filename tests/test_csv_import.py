"""Testes das funções puras do importador de CSV.

Não tocam o banco — cobrem sanitização, place_id determinístico e mapeamento
de cabeçalhos. Inclui um test-drive do fluxo com DB fake (sem ORM real) que
garante a separação Lead/Contact (o `bulk_save_objects` com lista misturada
quebrava a FK de `contacts.lead_id`).
"""
from types import SimpleNamespace

from src.services.csv_import_service import (
    clean_url,
    clean_cnpj,
    generate_csv_place_id,
    normalize_header,
    normalize_import_website,
    CsvImportService,
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
    # (caminho CSV) — o lead não deve ser tratado como "tem site".
    assert normalize_import_website("canva.link/artigo") is None
    assert normalize_import_website("https://api.whatsapp.com/send?phone=55") is None
    assert normalize_import_website("https://www.instagram.com/loja") is None
    assert normalize_import_website("https://instadelivery.com.br/perfil") is None


class _FakeQuery:
    def filter(self, *_a, **_k):
        return self

    def all(self):
        return []


class _FakeDb:
    def __init__(self):
        self.added = []
        self.committed = 0

    def query(self, *_a):
        return _FakeQuery()

    def add_all(self, objs):
        self.added.extend(objs)

    def commit(self):
        self.committed += 1


def _campaign():
    return SimpleNamespace(
        id="c-1",
        organization_id="org-1",
        target_city=None,
        target_state=None,
        target_segment=None,
    )


def test_import_com_contato_conta_leads_e_contatos_separados():
    content = (
        "nome,contato,email\n"
        "Empresa A,Ana Souza,ana@empresaa.com.br\n"
        "Empresa B,,contato@empresab.com.br\n"
    )
    db = _FakeDb()
    out = CsvImportService.parse_and_import(db, _campaign(), content, "user-1")

    assert out["imported_count"] == 2          # só leads
    assert out["contacts_count"] == 1          # só o decisor do primeiro
    assert db.committed == 1
    assert len(db.added) == 3                  # 2 leads + 1 contato


def test_import_sem_contato_nao_conta_contatos():
    content = "nome,email\nEmpresa A,contato@empresa.com.br\n"
    db = _FakeDb()
    out = CsvImportService.parse_and_import(db, _campaign(), content, "user-1")
    assert out["imported_count"] == 1
    assert out["contacts_count"] == 0
    assert len(db.added) == 1
    assert _has_no_contact(db.added)


def _has_no_contact(objs):
    from src.db.models import Contact
    return not any(isinstance(o, Contact) for o in objs)
