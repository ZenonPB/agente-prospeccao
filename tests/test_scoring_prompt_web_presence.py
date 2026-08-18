"""Testes de coerência da instrução 8 do prompt de scoring.

A instrução "vende presença digital → sem site é público-alvo" deve ser
decidida pelo template de critérios, não por heurística no nome do serviço:
um serviço como "Aplicações web completas" (ERP) NÃO trata ausência de site
como dor, mesmo contendo a palavra "web".
"""
from services.scoring_service import build_prompt


def _template(label: str):
    return {
        "service_label": label,
        "positive_signals": [],
        "negative_signals": [],
        "context_signals": [],
    }


def test_template_desenvolvimento_de_sites_ativa_publico_alvo():
    p = build_prompt(
        target_service="Desenvolvimento de Sites",
        target_segment="Comércios",
        template=_template("Desenvolvimento de Sites"),
        technical_facts=[],
        business_facts=[],
    )
    assert "SEM site" in p
    assert "PÚBLICO-ALVO" in p


def test_template_erp_com_web_no_servico_nao_ativa_publico_alvo():
    p = build_prompt(
        target_service="Aplicações web completas",
        target_segment="Comércios",
        template=_template("Aplicações Web / ERP"),
        technical_facts=[],
        business_facts=[],
    )
    assert "PÚBLICO-ALVO" not in p
    assert "NEUTRA" in p


def test_template_engenharia_nao_ativa_publico_alvo():
    p = build_prompt(
        target_service="Projetos de Engenharia Mecânica",
        target_segment="Indústrias",
        template=_template("Engenharia Mecânica"),
        technical_facts=[],
        business_facts=[],
    )
    assert "PÚBLICO-ALVO" not in p


def test_sem_template_fallback_regex_por_servico():
    p = build_prompt(
        target_service="Desenvolvimento de Sites",
        target_segment="",
        template=None,
        technical_facts=[],
        business_facts=[],
    )
    assert "PÚBLICO-ALVO" in p


def test_sem_template_erp_web_solto_nao_ativa_publico_alvo():
    p = build_prompt(
        target_service="Aplicações web completas",
        target_segment="",
        template=None,
        technical_facts=[],
        business_facts=[],
    )
    assert "PÚBLICO-ALVO" not in p


def test_template_generico_usa_fallback_regex():
    p = build_prompt(
        target_service="Landing pages para clínicas",
        target_segment="",
        template=_template("Genérico"),
        technical_facts=[],
        business_facts=[],
    )
    assert "PÚBLICO-ALVO" in p