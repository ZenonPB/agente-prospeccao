import pytest

from services.prospecting.commercial_analysis_output import (
    CommercialAnalysisValidationError,
    validate_commercial_analysis_output,
)


def _input():
    return {
        "contract_version": "commercial-analysis-input-v1",
        "analysis_metadata": {
            "analyzer_version": "commercial-analyst-v1",
            "policy_version": "grounded-analysis-v1",
            "provider": "test",
            "model": "test-model",
        },
        "offer": {"key": "landing_pages", "version": "1.0"},
        "evidence_context": {
            "context_hash": "ctx-1",
            "observations": [
                {
                    "epistemic": "FACT",
                    "reference": "registry:cnpj:1",
                    "evidence_refs": [],
                },
                {
                    "epistemic": "INFERENCE",
                    "reference": "web:site:1",
                    "evidence_refs": ["web:cta:1"],
                },
            ],
        },
    }


def test_fact_exige_referencia_fact_grounded():
    out = validate_commercial_analysis_output(
        {
            "why_company": [
                {
                    "statement": "Cadastro ativo.",
                    "epistemic": "FACT",
                    "confidence": 0.95,
                    "evidence_refs": ["registry:cnpj:1"],
                },
                {
                    "statement": "Conversão baixa.",
                    "epistemic": "FACT",
                    "confidence": 0.9,
                    "evidence_refs": ["web:cta:1"],
                },
            ]
        },
        analysis_input=_input(),
    )
    assert out["why_company"][0]["epistemic"] == "FACT"
    assert out["why_company"][1]["epistemic"] == "INFERENCE"


def test_remove_referencia_inventada():
    out = validate_commercial_analysis_output(
        {
            "why_offer": [{
                "statement": "Pode haver oportunidade.",
                "epistemic": "INFERENCE",
                "evidence_refs": ["invented:123", "web:site:1"],
            }]
        },
        analysis_input=_input(),
    )
    assert out["why_offer"][0]["evidence_refs"] == ["web:site:1"]


def test_hipotese_nunca_vira_fact():
    out = validate_commercial_analysis_output(
        {
            "opportunity_hypotheses": [{
                "statement": "Uma landing page pode reduzir fricção.",
                "epistemic": "FACT",
                "evidence_refs": ["registry:cnpj:1"],
            }]
        },
        analysis_input=_input(),
    )
    assert out["opportunity_hypotheses"][0]["epistemic"] == "HYPOTHESIS"


def test_metadata_e_hash_sao_persistiveis():
    out = validate_commercial_analysis_output({}, analysis_input=_input())
    assert out["contract_version"] == "commercial-analysis-output-v1"
    assert out["analysis_metadata"]["evidence_context_hash"] == "ctx-1"
    assert out["analysis_metadata"]["offer_key"] == "landing_pages"
    assert len(out["analysis_hash"]) == 64


def test_input_contract_desconhecido_falha_fechado():
    bad = _input()
    bad["contract_version"] = "future-v99"
    with pytest.raises(CommercialAnalysisValidationError):
        validate_commercial_analysis_output({}, analysis_input=bad)


def test_secao_explicativa_sem_grounding_e_descartada():
    out = validate_commercial_analysis_output(
        {
            "why_now": [{
                "statement": "A empresa está expandindo agora.",
                "epistemic": "INFERENCE",
                "confidence": 0.8,
                "evidence_refs": ["invented:expansion"],
            }]
        },
        analysis_input=_input(),
    )
    assert out["why_now"] == []


def test_hipotese_sem_grounding_permanece_explicitamente_hipotese():
    out = validate_commercial_analysis_output(
        {
            "opportunity_hypotheses": [{
                "statement": "Vale investigar uma página dedicada.",
                "epistemic": "INFERENCE",
            }]
        },
        analysis_input=_input(),
    )
    assert out["opportunity_hypotheses"][0]["epistemic"] == "HYPOTHESIS"
    assert out["opportunity_hypotheses"][0]["evidence_refs"] == []


def test_analysis_hash_ignora_timestamp_de_validacao():
    raw = {
        "why_company": [{
            "statement": "Cadastro ativo.",
            "epistemic": "FACT",
            "evidence_refs": ["registry:cnpj:1"],
        }]
    }
    first = validate_commercial_analysis_output(raw, analysis_input=_input())
    second = validate_commercial_analysis_output(raw, analysis_input=_input())
    assert first["analysis_hash"] == second["analysis_hash"]
