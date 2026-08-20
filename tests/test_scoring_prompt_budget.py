"""Testes do orçamento de tokens do prompt de scoring (Frente A — eficiência).

O modelo de scoring (`openai/gpt-oss-20b`) tem janela de TPM pequena (8k no
tier free). Truncar o que é injetado no prompt - listas longas (seo issues,
caminhos expostos, avisos) e descrições de sinais - reduz os tokens de entrada
por chamada sem perder a natureza do fato. Estes testes garantem que todo
texto injetado fica abaixo de um teto.
"""
from services.scoring_service import (
    _cap,
    _cap_items,
    _format_signals,
    extract_technical_facts,
)


def test_cap_preserva_inicio_e_corta_em_limite_de_palavra():
    text = ("palavra " * 60).strip()  # ~460 chars
    out = _cap(text, 100)
    assert len(out) <= 101
    assert out.startswith("palavra palavra palavra")
    assert out.endswith("…")


def test_cap_curto_inalterado():
    assert _cap("curto", 100) == "curto"
    assert _cap("", 100) == ""
    assert _cap(None, 100) == ""


def test_cap_items_limita_quantidade_e_tamanho():
    items = ["x" * 300] * 10
    out = _cap_items(items, limit=4, per_item=50)
    # 4 itens capados + marcador de continuação
    assert len(out) == 5
    assert out[-1] == "…"
    assert all(len(i) <= 51 for i in out[:4])


def test_format_signals_cap_descricoes_longas():
    sinais = [
        {
            "label": "Porte industrial com demanda recorrente de usinagem",
            "description": "x" * 500,
            "weight_hint": "high",
        }
    ]
    texto = _format_signals(sinais, "Sinais positivos")
    # A descrição de 500 chars entra capada (label 120 + desc 200) — a
    # linha de sinal fica bem abaixo do total bruto.
    assert len(texto) < 400
    assert max(len(line) for line in texto.splitlines()) < 320


def test_extract_technical_facts_cap_listas_longas():
    report = {
        "ssl": {"ssl_ok": True},
        "http_headers": {"status_code": 200, "load_time_ms": 4800},
        "cms_detection": "WordPress",
        "seo": {"issues": ["x" * 200] * 20},
        "exposed_paths": ["y" * 200] * 20,
        "warnings": ["z" * 200] * 20,
        "errors": ["w" * 200] * 20,
        "ux": {
            "viewport_ok": True,
            "contact_form_found": True,
            "tel_link_found": True,
            "login_portal_found": True,
        },
    }
    facts = extract_technical_facts(report)
    # Cada fato é uma linha curta (nada de listas de 20 itens × 200 chars)
    assert all(len(f) <= 400 for f in facts)
    assert any("SEO/LGPD issues" in f and "…" in f for f in facts)


def test_snippet_continue_limitado():
    report = {
        "ssl": {"ssl_ok": True},
        "http_headers": {"status_code": 200, "load_time_ms": 1000},
        "cms_detection": "WordPress",
        "domain_copy": {"snippet": "s" * 5000},
    }
    facts = extract_technical_facts(report)
    trecho = next(f for f in facts if "Trecho resumo" in f)
    assert len(trecho) <= 226  # prefixo (24) + 200 chars capados + reticências
    assert trecho.endswith("…")