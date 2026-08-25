"""Testes do parser de listas setoriais (FIESP/ABIMAQ e similares).

Listas de associados de federações/sindicatos costumam vir com linhas de
título antes do cabeçalho real e colunas com nomes próprios desse contexto
("Razão Social", "Município/UF", "Representante Legal", "Atividade
Econômica"...). Não tocam o banco — funções puras + DB fake.
"""
from types import SimpleNamespace

from src.services.csv_import_service import (
    CsvImportService,
    find_header_row,
    normalize_header,
)


# --- Mapeamento de cabeçalhos setoriais -------------------------------------


def test_razao_social_vira_campo_proprio():
    assert normalize_header("Razão Social") == "razao_social"
    assert normalize_header("Razao Social/Nome Empresarial") == "razao_social"


def test_nome_fantasia_vira_campo_proprio():
    assert normalize_header("Nome Fantasia") == "nome_fantasia"


def test_aliases_setoriais_mapeiam():
    assert normalize_header("Atividade Econômica") == "category"
    assert normalize_header("Ramo de Atividade") == "category"
    assert normalize_header("Produtos Fabricados") == "category"
    assert normalize_header("Representante Legal") == "contact_name"
    assert normalize_header("Dirigente") == "contact_name"
    assert normalize_header("Telefone Comercial") == "phone"
    assert normalize_header("Página Web") == "website"
    assert normalize_header("Empresa Associada") == "name"


# --- Detecção da linha de cabeçalho (preamble) ------------------------------


def test_find_header_row_em_arquivo_sem_preamble():
    rows = [["Nome", "Telefone"], ["Empresa A", "123"]]
    assert find_header_row(rows) == 0


def test_find_header_row_pula_titulos_e_linhas_vazias():
    rows = [
        ["Federação das Indústrias — Diretório Sindical Patronal"],
        [],
        ["Emitido em 01/08/2026 10:22"],
        ["Razão Social", "CNPJ", "Município", "UF"],
        ["Metalúrgica Exemplo Ltda", "12.345.678/0001-95", "São Paulo", "SP"],
    ]
    assert find_header_row(rows) == 3


def test_find_header_row_sem_cabecalho_reconhecivel():
    rows = [["a"], ["b"], ["c"]]
    assert find_header_row(rows) is None


# --- Importação ponta-a-ponta (DB fake, padrão test_csv_import) -------------


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


_FIESP_LIKE = (
    "ASSOCIAÇÃO COMERCIAL E INDUSTRIAL — RELATÓRIO DE ASSOCIADOS\n"
    "\n"
    "Emitido em 24/08/2026 às 09:00 — uso interno\n"
    "\n"
    "Razão Social;Nome Fantasia;CNPJ;Atividade Econômica;Município;UF;"
    "Telefone Comercial;E-mail;Página Web;Representante Legal\n"
    "Metalúrgica Horizonte Ltda;Horizonte Usinagem;12.345.678/0001-95;"
    "Usinagem e CNC;Piracicaba;SP;(19) 3422-1010;contato@horizonte.com.br;"
    "horizonteusinagem.com.br;João Ribeiro\n"
    "Plásticos Vale S.A.;Vale Plásticos;98.765.432/0001-10;"
    "Injeção de plásticos;Campinas;SP;(19) 3777-2020;vend@valeplast.com.br;;"
    "Maria Castro\n"
)


def test_import_layout_setorial_com_preamble():
    db = _FakeDb()
    out = CsvImportService.parse_and_import(db, _campaign(), _FIESP_LIKE, "u1")

    assert out["imported_count"] == 2
    assert out["layout_detected"] == "setorial"
    leads = [o for o in db.added if getattr(o, "company_name", None)]
    first = leads[0]
    assert first.company_name == "Metalúrgica Horizonte Ltda"
    assert first.name == "Horizonte Usinagem"
    assert first.cnpj == "12345678000195"
    assert first.city == "Piracicaba"
    assert first.state == "SP"
    assert first.phone == "(19) 3422-1010"
    assert first.category == "Usinagem e CNC"
    assert first.website == "https://horizonteusinagem.com.br"


def test_import_contato_do_representante_legal():
    db = _FakeDb()
    out = CsvImportService.parse_and_import(db, _campaign(), _FIESP_LIKE, "u1")
    contacts = [
        o for o in db.added if o.__class__.__name__ == "Contact"
    ]
    assert out["contacts_count"] == 2
    names = {c.name for c in contacts}
    assert names == {"João Ribeiro", "Maria Castro"}


def test_import_layout_padrao_reportado():
    db = _FakeDb()
    content = "nome,email\nEmpresa A,a@x.com\n"
    out = CsvImportService.parse_and_import(db, _campaign(), content, "u1")
    assert out["imported_count"] == 1
    assert out["layout_detected"] == "padrao"


def test_import_sem_coluna_de_nome_reconhecida_falha_amigavel():
    db = _FakeDb()
    content = "telefone,cidade\n123,Sorocaba\n"
    out = CsvImportService.parse_and_import(db, _campaign(), content, "u1")
    assert out["imported_count"] == 0
    assert out["error_count"] == 1
    assert "Razão Social" in out["errors"][0]["reason"] or "nome" in out["errors"][0]["reason"]
