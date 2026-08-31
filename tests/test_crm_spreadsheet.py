"""Testes do serviço de preenchimento da planilha de CRM.

Foca na lógica pura: `build_planilha_row` (mapeamento LEAD/pitch/follow-ups)
e a regra de LEAD (contato primário vs empresa). Sem banco real — usa objetos
simples com os atributos usados.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from src.services.crm_spreadsheet_service import (
    PITCH_ENVIADO_STATUSES,
    RESPONDEU_STATUSES,
    build_planilha_row,
)


def _lead(status="NOVO", company="Clinica Maua Ltda", assigned=None, last_contacted=None, notes=None):
    return SimpleNamespace(
        id="lead-1", company_name=company, name="Clinica Maua",
        assigned_at=assigned or datetime(2026, 7, 29, tzinfo=timezone.utc),
        created_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        last_contacted_at=last_contacted,
        notes=notes,
        status=SimpleNamespace(value=status),
    )


def _contact(name="Fabio Prada Perez", role="CEO", is_primary=True):
    return SimpleNamespace(name=name, role_label=role, is_primary=is_primary)


def test_lead_usa_contato_primario():
    row = build_planilha_row(
        _lead(status="NOVO"), _contact(), {},
    )
    # Col LEAD (1) = contato, Empresa (2) = empresa, CARGO (10) = CEO.
    assert row[0] == "Fabio Prada Perez"
    assert row[1] == "Clinica Maua Ltda"
    assert row[9] == "CEO"


def test_lead_sem_contato_usa_empresa():
    row = build_planilha_row(_lead(status="NOVO"), None, {})
    assert row[0] == "Clinica Maua Ltda"
    assert row[9] is None


def test_respondeu_sim_para_status_validos():
    for status in RESPONDEU_STATUSES:
        row = build_planilha_row(_lead(status=status.value), None, {})
        assert row[8] == "SIM"


def test_pitch_enviado_boolean():
    row = build_planilha_row(_lead(status="CONTATADO"), None, {})
    assert row[3] is True
    # Sem pitch e status NOVO → False.
    row = build_planilha_row(_lead(status="NOVO"), None, {})
    assert row[3] is False


def test_followups_vem_do_mapa():
    fu1 = datetime(2026, 8, 7, tzinfo=timezone.utc)
    fu2 = datetime(2026, 8, 10, tzinfo=timezone.utc)
    from src.db.models import FollowUpStep
    row = build_planilha_row(_lead(status="CONTATADO", last_contacted=datetime(2026, 8, 3, tzinfo=timezone.utc)), None, {
        FollowUpStep.FOLLOWUP_1: fu1,
        FollowUpStep.FOLLOWUP_2: fu2,
    })
    # Col FU1 (6) e FU2 (7). PITCH (5) usa last_contacted_at.
    assert row[5] == fu1.replace(tzinfo=None)
    assert row[6] == fu2.replace(tzinfo=None)
    assert row[4].year == 2026 and row[4].month == 8 and row[4].day == 3