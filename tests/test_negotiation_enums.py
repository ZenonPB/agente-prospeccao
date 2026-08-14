"""Testes do funil de negociação.

Validam os enums e a regra conservada: o funil interno (RD/ORÇAMENTO/RP) e o
resultado do contrato (APROVADO/REPROVADO/EM_ANÁLISE) — que espelham a planilha
Alphamec para o sistema.
"""
from src.db.models import NegotiationStage, ContractOutcome


def test_negotiation_stage_valores_planilha():
    assert {s.value for s in NegotiationStage} == {"RD", "ORCAMENTO", "RP"}


def test_negotiation_stage_ordem_progressiva():
    assert list(NegotiationStage) == [
        NegotiationStage.RD,
        NegotiationStage.ORCAMENTO,
        NegotiationStage.RP,
    ]


def test_contract_outcome_valores_planilha():
    assert {o.value for o in ContractOutcome} == {"APROVADO", "REPROVADO", "EM_ANALISE"}


def test_contract_outcome_aprovado_fecha():
    assert ContractOutcome.APROVADO.value == "APROVADO"
    assert ContractOutcome.EM_ANALISE.value == "EM_ANALISE"