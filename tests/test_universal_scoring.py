"""Testes de qualificação e scoring universal por setor.

Valida que o sistema pontua com alta precisão e evidências ricas para:
1. Desenvolvimento de Sites / Landing Pages
2. Engenharia Mecânica & Desenhos Técnicos CAD
3. Corte Laser, MDF & Produtos Personalizados (Troféus / Chaveiros)
4. Aplicações Web & ERPs
"""
import pytest
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import AIScoringService, extract_technical_facts, extract_business_facts
from seeds.scoring_templates import DEFAULT_TEMPLATES


def test_domain_copy_extraction_mechanical():
    service = TechnicalEnrichmentService()
    html = """
    <html>
      <head>
        <title>Usinagem e Projetos Mecânicos Silva</title>
        <meta name="description" content="Especialistas em usinagem CNC, torno, solda e caldeiraria pesada." />
      </head>
      <body>
        <h1>Fabricação de Peças Industriais e Usinagem CNC</h1>
        <h2>Desenho técnico 3D em SolidWorks e Engenharia Mecânica</h2>
        <p>Atendemos indústrias com projetos mecânicos sob medida e moldes para injetoras.</p>
      </body>
    </html>
    """
    domain_copy = service._extract_domain_copy(html)
    assert domain_copy["meta_description"] == "Especialistas em usinagem CNC, torno, solda e caldeiraria pesada."
    assert "Usinagem CNC" in domain_copy["headings"][0]
    assert "usinagem" in domain_copy["keywords_mechanical"]
    assert "cnc" in domain_copy["keywords_mechanical"]
    assert "desenho técnico" in domain_copy["keywords_mechanical"] or "desenho tecnico" in domain_copy["keywords_mechanical"]


def test_domain_copy_extraction_custom_mdf_trophies():
    service = TechnicalEnrichmentService()
    html = """
    <html>
      <head>
        <title>Arte Laser — Troféus e Brindes em MDF</title>
        <meta name="description" content="Fabricação de troféus, chaveiros em acrílico, placas de homenagem e produtos em MDF sob medida." />
      </head>
      <body>
        <h1>Corte e Gravação a Laser em MDF e Acrílico</h1>
        <h2>Brindes corporativos e troféus para premiações</h2>
      </body>
    </html>
    """
    domain_copy = service._extract_domain_copy(html)
    assert "mdf" in domain_copy["keywords_custom_craft"]
    assert "troféus" in domain_copy["keywords_custom_craft"] or "trofeus" in domain_copy["keywords_custom_craft"]
    assert "chaveiros" in domain_copy["keywords_custom_craft"]


def test_extract_technical_facts_includes_domain_copy():
    report = {
        "ssl": {"ssl_ok": True, "https_redirect_ok": True},
        "http_headers": {"status_code": 200, "load_time_ms": 1200},
        "domain_copy": {
            "meta_description": "Usinagem de precisão e caldeiraria.",
            "headings": ["Desenho técnico 3D"],
            "keywords_mechanical": ["usinagem", "cnc", "solda"],
            "keywords_custom_craft": [],
            "keywords_systems": [],
            "snippet": "Serviços industriais sob medida.",
        }
    }
    facts = extract_technical_facts(report)
    facts_str = " ".join(facts)
    assert "Usinagem de precisão" in facts_str
    assert "Desenho técnico 3D" in facts_str
    assert "usinagem" in facts_str


def test_extract_business_facts_cnae_and_size():
    facts = extract_business_facts(
        company_name="Metalúrgica Alfa Ltda",
        category="Indústria Mecânica",
        city="Piracicaba",
        state="SP",
        website="https://metalurgicaalfa.com.br",
        google_rating=4.8,
        google_rating_count=25,
        cnae_info="2539-0/01 Usinagem, solda e caldeiraria",
        company_size_info="Médio porte — Capital R$ 500.000,00",
    )
    facts_str = " ".join(facts)
    assert "Atividade econômica (CNAE/Receita): 2539-0/01" in facts_str
    assert "Médio porte" in facts_str


def test_seed_scoring_templates_contain_new_verticals():
    labels = [t["service_label"] for t in DEFAULT_TEMPLATES]
    assert "Engenharia Mecânica & Desenhos Técnicos CAD" in labels
    assert "Corte Laser, MDF & Produtos Personalizados" in labels
    assert "Aplicações Web / ERP" in labels
    assert "Desenvolvimento de Sites" in labels
