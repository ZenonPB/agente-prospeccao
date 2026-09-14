from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest

from src.services.historical_import_parser import ImportParseError, parse_source
from src.services.lead_bulk_command_service import (
    BulkCommandConflict,
    LeadBulkCommandService,
    _replay_existing,
)
from database.models import Lead, LeadStatus, OrganizationRole, SalesRole


ORG_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
LEAD_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


class _Query:
    column_descriptions = [{"entity": Lead}]

    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_criteria):
        return self

    def all(self):
        return self.rows


class _DB:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return _Query(self.rows if model is Lead else [])


def _member():
    return SimpleNamespace(
        user_id=USER_ID,
        organization_id=ORG_ID,
        role=OrganizationRole.MEMBER,
        sales_role=SalesRole.MANAGER,
    )


def _lead():
    return SimpleNamespace(
        id=LEAD_ID,
        organization_id=ORG_ID,
        assigned_to_id=None,
        updated_at=datetime(2026, 9, 14, 12, tzinfo=timezone.utc),
        status=LeadStatus.NOVO,
        lost_reason=None,
    )


def test_bulk_fail_closed_quando_expected_updated_at_esta_ausente():
    lead = _lead()
    service = LeadBulkCommandService(_DB([lead]), ORG_ID, _member(), SimpleNamespace(id=USER_ID))

    preview = service.preview({
        "operation": "status",
        "lead_ids": [str(LEAD_ID)],
        "status": "CONTATADO",
        "lost_reason": None,
        "assigned_to_id": None,
        "expected_updated_at": {},
    })

    assert preview["accepted_ids"] == []
    assert preview["rejected"] == [{"id": str(LEAD_ID), "reason": "VERSION_CONFLICT"}]
    assert lead.status == LeadStatus.NOVO


def test_replay_bulk_nao_devolve_payload_vazio_enquanto_vencedor_esta_running():
    operation = SimpleNamespace(
        payload_hash="abc",
        status="RUNNING",
        result=None,
    )
    with pytest.raises(BulkCommandConflict, match="em andamento"):
        _replay_existing(operation, "abc")


def test_replay_bulk_rejeita_reuso_da_chave_com_payload_diferente():
    operation = SimpleNamespace(
        payload_hash="abc",
        status="COMPLETED",
        result={"accepted": 1},
    )
    with pytest.raises(BulkCommandConflict, match="outro payload"):
        _replay_existing(operation, "def")


def test_parser_aceita_telefone_internacional_com_mais():
    parsed = parse_source(
        b"Nome,Telefone\nEmpresa,+5516999999999\n",
        "historico.csv",
        "text/csv",
    )
    assert parsed.rows == [["Empresa", "+5516999999999"]]


@pytest.mark.parametrize(
    "payload",
    [
        b"Nome,Telefone\nEmpresa,=HYPERLINK(\"http://evil\")\n",
        b"Nome,Telefone\nEmpresa,+HYPERLINK(\"http://evil\")\n",
        b"Nome,Telefone\nEmpresa,@SUM(1,2)\n",
    ],
)
def test_parser_continua_bloqueando_formula_injetavel(payload: bytes):
    with pytest.raises(ImportParseError, match="fórmula"):
        parse_source(payload, "historico.csv", "text/csv")


def test_parser_aplica_limite_de_celulas_tambem_no_csv(monkeypatch):
    import src.services.historical_import_parser as parser

    monkeypatch.setattr(parser, "MAX_CELLS", 4)
    with pytest.raises(ImportParseError) as error:
        parser.parse_source(
            b"Nome,Telefone\nA,1\nB,2\n",
            "historico.csv",
            "text/csv",
        )
    assert error.value.code == "CELL_LIMIT"
