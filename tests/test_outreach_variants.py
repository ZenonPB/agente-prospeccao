"""Testes das variantes A/B de outreach.

Cobre:
- `_normalize_variants` valida a estrutura e atribui labels A/B;
- `build_prompt` injeta o schema correto quando `generate_variants=True`.
"""
from services.outreach_service import (
    _normalize_variants,
    _normalize_response,
    build_prompt,
)


def test_normalize_variants_labels_e_ordem():
    """Quando a LLM responde com lista, atribui A/B pela ordem quando faltam labels."""
    raw = {
        "variants": [
            {"subject": "A: subject", "body_opening": "A body", "rationale": "gancho A"},
            {"subject": "B: subject", "body_opening": "B body", "rationale": "gancho B"},
        ]
    }
    out = _normalize_variants(raw)
    assert out is not None
    assert [v["label"] for v in out] == ["A", "B"]
    assert out[0]["subject"] == "A: subject"
    assert out[1]["rationale"] == "gancho B"


def test_normalize_variants_preserva_label_da_llm():
    raw = {
        "variants": [
            {"label": "X", "subject": "X", "body_opening": "X", "rationale": "X"},
            {"label": "Y", "subject": "Y", "body_opening": "Y", "rationale": "Y"},
        ]
    }
    out = _normalize_variants(raw)
    assert [v["label"] for v in out] == ["X", "Y"]


def test_normalize_variants_invalido_queda_none():
    """Sem `variants` (lista) → retorna None para que o caller caia no single."""
    assert _normalize_variants({"subject": "x"}) is None
    assert _normalize_variants({"variants": []}) is None
    assert _normalize_variants({"variants": [{"subject": "apenas uma"}]}) is None


def test_normalize_response_adiciona_opt_out_se_ausente():
    out = _normalize_response({"subject": "S", "body_opening": "oi"})
    assert "Responda STOP" in out["body_opening"]


def test_build_prompt_inclui_schema_variants_quando_pedido():
    lead = {"company_name": "ACME"}
    p_single = build_prompt(lead)
    p_var = build_prompt(lead, generate_variants=True)
    assert "EXATAMENTE esta estrutura" in p_single
    assert '"variants"' not in p_single
    assert '"variants"' in p_var and '"label"' in p_var
