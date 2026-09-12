"""Contratos puros do motor de engagement e workflows."""
import pytest

from src.services.engagement_service import validate_sequence_steps
from src.services.workflow_service import WorkflowService, validate_workflow


def test_sequence_normaliza_etapas_suportadas():
    steps = validate_sequence_steps([
        {"type": "email", "delay_minutes": 0, "subject": "Olá", "content": "Mensagem"},
        {"type": "wait", "delay_minutes": 60},
        {
            "type": "condition",
            "config": {"field": "lead.status", "operator": "eq", "value": "RESPONDIDO", "on_false": "stop"},
        },
        {"type": "linkedin", "title": "Contatar no LinkedIn"},
    ])

    assert [step["type"] for step in steps] == ["EMAIL", "WAIT", "CONDITION", "LINKEDIN"]
    assert steps[0]["subject"] == "Olá"
    assert steps[2]["config"]["on_false"] == "stop"


@pytest.mark.parametrize("step", [
    {"type": "sms"},
    {"type": "email", "delay_minutes": -1},
    {"type": "condition", "config": {"field": "lead.password", "operator": "eq", "value": "x"}},
])
def test_sequence_rejeita_configuracao_fora_do_contrato(step):
    with pytest.raises(ValueError):
        validate_sequence_steps([step])


def test_workflow_normaliza_trigger_condicoes_e_acoes():
    trigger, conditions, actions = validate_workflow(
        "lead_scored",
        [{"field": "score", "operator": "gte", "value": 80}],
        [
            {"type": "create_task", "config": {"title": "Revisar lead"}},
            {"type": "notify", "config": {"title": "Lead quente"}},
        ],
    )

    assert trigger == "LEAD_SCORED"
    assert conditions == [{"field": "score", "operator": "gte", "value": 80}]
    assert [item["type"] for item in actions] == ["CREATE_TASK", "NOTIFY"]


def test_workflow_rejeita_campos_e_acoes_nao_permitidos():
    with pytest.raises(ValueError, match="Campo de condição"):
        validate_workflow(
            "LEAD_SCORED",
            [{"field": "secret", "operator": "eq", "value": "x"}],
            [{"type": "NOTIFY"}],
        )

    with pytest.raises(ValueError, match="Ação não suportada"):
        validate_workflow("LEAD_SCORED", [], [{"type": "RUN_SHELL"}])


def test_conditions_match_preserva_semantica_deterministica():
    context = {"score": 82, "offer_key": "trophies", "channel": None}

    assert WorkflowService._conditions_match(
        [
            {"field": "score", "operator": "gte", "value": 80},
            {"field": "offer_key", "operator": "in", "value": ["trophies", "landing_page"]},
            {"field": "channel", "operator": "exists", "value": False},
        ],
        context,
    )
    assert not WorkflowService._conditions_match(
        [{"field": "score", "operator": "gte", "value": 90}],
        context,
    )
