"""Testes dos sinais determinísticos de qualidade de site no scoring.

Site próprio de BAIXA qualidade (plataforma gratuita, sem domínio próprio,
vários problemas de UX/SEO) deve aparecer como fact e ser tratado como
público-alvo em campanhas de presença digital — não como "tem site, pronto".
"""
from services.scoring_service import build_prompt, extract_technical_facts
from services.technical_enrichment_service import TechnicalEnrichmentService


def _template(label: str):
    return {
        "service_label": label,
        "positive_signals": [],
        "negative_signals": [],
        "context_signals": [],
    }


# ---------------------------------------------------------------- plataforma

def test_blogspot_url_detecta_plataforma_gratuita_sem_dominio():
    svc = TechnicalEnrichmentService()
    pq = svc._detect_platform_quality(
        "https://famacabeleireiros.blogspot.com/",
        "<html><body>salao</body></html>",
        {},
    )
    assert pq["is_free_platform"] is True
    assert pq["custom_domain"] is False
    assert "Blogger" in pq["platform"]


def test_dominio_proprio_sem_plataforma_gratuita():
    svc = TechnicalEnrichmentService()
    pq = svc._detect_platform_quality(
        "https://www.salaocheiadecharme.com.br/unidade-araraquara",
        "<html><body>salao</body></html>",
        {},
    )
    assert pq["is_free_platform"] is False
    assert pq["custom_domain"] is True
    assert pq["platform"] is None


def test_wixsite_subdomino_detecta_plataforma_gratuita():
    svc = TechnicalEnrichmentService()
    pq = svc._detect_platform_quality(
        "https://loja123.wixsite.com/meusite",
        "<html><body></body></html>",
        {},
    )
    assert pq["is_free_platform"] is True
    assert "Wix" in pq["platform"]


# -------------------------------------------------------------------- facts

def test_fact_plataforma_gratuita_no_relatorio_tecnico():
    report = {
        "ssl": {"ssl_ok": True, "https_redirect_ok": True},
        "http_headers": {"status_code": 200, "load_time_ms": 800},
        "cms_detection": "Blogger/Blogspot",
        "platform_quality": {"platform": "Blogger/Blogspot", "is_free_platform": True, "custom_domain": False},
    }
    facts = extract_technical_facts(report)
    assert any("Plataforma gratuita/amadora detectada" in f and "sem domínio próprio" in f for f in facts)


def test_fact_resumo_qualidade_com_varios_problemas():
    report = {
        "ssl": {"ssl_ok": True},
        "http_headers": {"status_code": 200},
        "seo": {"issues": ["Tag <title> ausente ou vazia", "Meta description ausente ou vazia", "Nenhum <h1> encontrado"]},
        "ux": {"issues": ["Nenhum formulário de contato (<form>) na página"]},
    }
    facts = extract_technical_facts(report)
    assert any("problemas de UX/SEO detectados" in f and "candidato a redesign" in f for f in facts)


def test_sem_fact_resumo_qualidade_com_poucos_problemas():
    report = {
        "ssl": {"ssl_ok": True},
        "http_headers": {"status_code": 200},
        "seo": {"issues": []},
        "ux": {"issues": ["Nenhum formulário de contato (<form>) na página"]},
    }
    facts = extract_technical_facts(report)
    assert not any("problemas de UX/SEO detectados" in f for f in facts)


# ------------------------------------------------------------------- prompt

def test_prompt_web_presence_cita_site_de_baixa_qualidade_como_publico_alvo():
    p = build_prompt(
        target_service="Desenvolvimento de Sites",
        target_segment="Comércios",
        template=_template("Desenvolvimento de Sites"),
        technical_facts=[],
        business_facts=[],
    )
    assert "BAIXA QUALIDADE" in p
    assert "Plataforma gratuita/amadora" in p
    assert "RENOVAR" in p


def test_prompt_erp_nao_cita_qualidade_de_site_como_sinal():
    p = build_prompt(
        target_service="Aplicações web completas",
        target_segment="Indústrias",
        template=_template("Aplicações Web / ERP"),
        technical_facts=[],
        business_facts=[],
    )
    assert "BAIXA QUALIDADE" not in p
