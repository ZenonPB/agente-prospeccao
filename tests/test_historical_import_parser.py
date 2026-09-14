"""Testes determinísticos do parser seguro do Historical Importer."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from src.db.models import Contact, Company, ImportAuditEvent, ImportJob, ImportJobStatus, Lead, Person
from src.services.historical_import_parser import (
    ImportParseError,
    MAX_CELLS,
    MAX_COLUMNS,
    MAX_DATA_ROWS,
    MAX_FILE_BYTES,
    PREVIEW_ROWS,
    parse_source,
    validate_mapping,
)
from src.services.import_job_service import dry_run


def _xlsx(rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_csv_utf8_bom_preview_escapa_html_e_nao_busca_url():
    parsed = parse_source(
        "\ufeffNome da empresa,Site,Contato\nEmpresa <script>alert(1)</script>,http://127.0.0.1:9,Ana\n".encode(),
        "historico.csv",
        "text/csv",
    )
    assert parsed.source_format == "csv"
    assert parsed.headers == ["Nome da empresa", "Site", "Contato"]
    assert parsed.suggested_mapping["Nome da empresa"] == "name"
    assert "&lt;script&gt;" in parsed.preview_rows[0][0]
    assert parsed.rows[0][1] == "http://127.0.0.1:9"


def test_csv_deve_ser_utf8_e_ter_mapping_explicito():
    with pytest.raises(ImportParseError, match="UTF-8"):
        parse_source("Nome,Site\nJoão,empresa.com\n".encode("latin-1"), "a.csv", "text/csv")

    parsed = parse_source(b"Nome,Site\nEmpresa,empresa.com\n", "a.csv", "text/csv")
    mapping = {"Nome": "name", "Site": "website"}
    assert validate_mapping(parsed.headers, mapping) == mapping
    with pytest.raises(ImportParseError, match="Cada coluna"):
        validate_mapping(parsed.headers, {"Nome": "name"})


def test_csv_aceita_delimitador_ponto_e_virgula_e_rejeita_sem_linha_de_dados():
    parsed = parse_source("Nome;Site\nEmpresa;empresa.com\n".encode(), "a.csv", "text/csv")
    assert parsed.headers == ["Nome", "Site"]
    assert parsed.rows == [["Empresa", "empresa.com"]]

    with pytest.raises(ImportParseError, match="linha de dados"):
        parse_source(b"Nome,Site\n", "vazio.csv", "text/csv")


def test_csv_malformado_rejeita_aspas_nao_fechadas():
    with pytest.raises(ImportParseError, match="malformado"):
        parse_source(b"Nome,Site\n\"Empresa,empresa.com\n", "a.csv", "text/csv")


def test_xlsx_e_formula_sao_validados_sem_executar_formula():
    parsed = parse_source(_xlsx([["Nome", "Site"], ["Empresa", "empresa.com"]]), "a.xlsx", None)
    assert parsed.source_format == "xlsx"
    assert parsed.rows == [["Empresa", "empresa.com"]]

    with pytest.raises(ImportParseError, match="fórmula"):
        parse_source(_xlsx([["Nome"], ["=1+1"]]), "a.xlsx", None)


def test_xlsx_malformado_e_extensao_mime_incompativeis_sao_rejeitados():
    with pytest.raises(ImportParseError, match="inválida|XLSX"):
        parse_source(b"not-an-xlsx", "a.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    xlsx = _xlsx([["Nome"], ["Empresa"]])
    with pytest.raises(ImportParseError, match="tipo|extensão|assinatura"):
        parse_source(xlsx, "a.csv", "text/csv")
    with pytest.raises(ImportParseError, match="tipo|MIME"):
        parse_source(b"Nome\nEmpresa\n", "a.csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def test_xlsx_rejeita_colunas_demais_e_mapping_duplicado():
    headers = [f"coluna-{index}" for index in range(MAX_COLUMNS + 1)]
    with pytest.raises(ImportParseError, match="colunas"):
        parse_source(_xlsx([headers, ["x"] * len(headers)]), "a.xlsx", None)

    parsed = parse_source(b"Nome,Site\nEmpresa,empresa.com\n", "a.csv", "text/csv")
    with pytest.raises(ImportParseError, match="mais de uma"):
        validate_mapping(parsed.headers, {"Nome": "name", "Site": "name"})


def test_limites_de_tamanho_linhas_e_celulas_sao_aplicados():
    with pytest.raises(ImportParseError, match="25 MiB"):
        parse_source(b"x" * (MAX_FILE_BYTES + 1), "a.csv", "text/csv")

    too_many_rows = b"Nome\n" + (b"Empresa\n" * (MAX_DATA_ROWS + 1))
    with pytest.raises(ImportParseError, match="100000"):
        parse_source(too_many_rows, "linhas.csv", "text/csv")

    headers = ",".join(f"coluna-{index}" for index in range(MAX_COLUMNS))
    row = ",".join("x" for _ in range(MAX_COLUMNS))
    too_many_cells = (headers + "\n" + (row + "\n") * (MAX_CELLS // MAX_COLUMNS + 1)).encode()
    with pytest.raises(ImportParseError, match="1000000"):
        parse_source(too_many_cells, "celulas.csv", "text/csv")


def test_preview_tem_no_maximo_cem_linhas_e_nao_expoe_html_executavel():
    content = "Nome,Site\n" + "<img src=x onerror=alert(1)>,https://example.com\n" * (PREVIEW_ROWS + 1)
    parsed = parse_source(content.encode(), "preview.csv", "text/csv")
    assert len(parsed.preview_rows) == PREVIEW_ROWS
    assert "&lt;img" in parsed.preview_rows[0][0]
    assert "onerror" in parsed.preview_rows[0][0]
    assert parsed.rows[0][1] == "https://example.com"


def test_csv_rejeita_extensao_ou_formato_nao_suportado():
    with pytest.raises(ImportParseError, match="CSV ou XLSX"):
        parse_source(b"Nome\nEmpresa\n", "a.txt", "text/plain")


class _EmptyQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _DryRunDb:
    def __init__(self, job):
        self.job = job
        self.added = []
        self.query_models = []
        self.commits = 0

    def query(self, model, *_args):
        self.query_models.append(model)
        if model is ImportJob:
            query = _EmptyQuery()
            query.first = lambda: self.job
            return query
        return _EmptyQuery()

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        return None


def test_dry_run_somente_le_fontes_e_nao_cria_entidades_canonicas():
    job = SimpleNamespace(
        id="import-1",
        organization_id="org-1",
        actor_id="user-1",
        campaign_id=None,
        correlation_id=None,
        status=ImportJobStatus.PREVIEWED,
        expected_version=1,
        source_headers=["Nome", "Site"],
        source_rows=[["Empresa <b>texto</b>", "http://127.0.0.1:9"]],
        preview_rows=[["Empresa &lt;b&gt;texto&lt;/b&gt;", "http://127.0.0.1:9"]],
        source_hash="hash",
        source_filename="preview.csv",
        source_format="csv",
        mapping_version="preview-version",
        total_rows=1,
        accepted_rows=0,
        duplicate_rows=0,
        rejected_rows=0,
        failed_rows=0,
        unprocessed_rows=1,
        attempts=0,
        error_code=None,
        error_message=None,
        created_at=None,
        started_at=None,
        completed_at=None,
        mapping={"Nome": "name", "Site": "website"},
        dry_run_report=None,
    )
    db = _DryRunDb(job)

    result = dry_run(db, "org-1", "user-1", "import-1", job.mapping, 1)

    assert result["report"]["accepted"] == 1
    assert db.commits == 1
    assert any(isinstance(item, ImportAuditEvent) for item in db.added)
    assert not any(isinstance(item, (Company, Person, Lead, Contact)) for item in db.added)
    assert {Company, Person, Lead, Contact}.isdisjoint(set(db.query_models)) is False
