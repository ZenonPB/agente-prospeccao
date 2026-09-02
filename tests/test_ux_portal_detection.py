"""Detecção determinística de área logada/portal e menção a sistema no HTML.

O template "Aplicações Web / ERP" marca "área logada/portal" e "menção a
sistema/ERP" como critérios a CONFIRMAR no HTML, mas o enrichment não media
nada disso — a LLM inferia. Estes testes garantem que `_check_ux` passa a
medir e que `extract_technical_facts` transforma a medição em fact ancorado.
Sem rede — funções puras.
"""
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import extract_technical_facts


def _ux(html, website_url=None):
    return TechnicalEnrichmentService()._check_ux(html, website_url=website_url)


# ---- detecção de área logada / portal / painel ----

def test_detecta_login():
    result = _ux('<a href="/login">Entrar</a>')
    assert result["login_portal_found"] is True


def test_detecta_area_do_cliente():
    result = _ux('<a href="/area-do-cliente">Área do cliente</a>')
    assert result["login_portal_found"] is True


def test_detecta_portal_do_aluno():
    result = _ux('<div>Portal do aluno</div>')
    assert result["login_portal_found"] is True


def test_detecta_painel():
    result = _ux('<a href="/painel">Meu painel</a>')
    assert result["login_portal_found"] is True


def test_nao_detecta_portal_em_site_institucional():
    result = _ux('<h1>Academia Fit</h1><p>Bem-vindo</p>')
    assert result["login_portal_found"] is False


def test_nao_detecta_portal_com_site_vazio():
    result = _ux(None)
    assert result["login_portal_found"] is False


# ---- detecção de menção a sistema / ERP / software ----

def test_detecta_menção_erp():
    result = _ux('<p>Nosso ERP integra vendas e estoque</p>')
    assert result["system_mention_found"] is True


def test_detecta_menção_sistema_gestao():
    # Regex refinada: exige contexto de GESTÃO (ERP, CRM, sistema integrado,
    # software/plataforma de gestão, API). "Acessar sistema" sozinho, sem
    # contexto, NÃO conta — esse era o falso-positivo histórico que fazia o
    # scoring de ERP considerar SaaS de delivery como "lead já tem sistema".
    result = _ux('<a href="/sistema">Acessar sistema</a>')
    assert result["system_mention_found"] is False
    result = _ux('<p>Nosso sistema de gestão integra vendas e estoque</p>')
    assert result["system_mention_found"] is True


def test_detecta_menção_software():
    result = _ux('<p>Software de gestão próprio</p>')
    assert result["system_mention_found"] is True


def test_detecta_crm():
    result = _ux('<p>Use nosso CRM para gerenciar clientes</p>')
    assert result["system_mention_found"] is True


def test_detecta_plataforma_integrada():
    result = _ux('<p>Plataforma integrada com API REST pública</p>')
    assert result["system_mention_found"] is True


def test_nao_detecta_sistema_em_site_institucional():
    result = _ux('<h1>Academia Fit</h1><p>Bem-vindo</p>')
    assert result["system_mention_found"] is False


def test_nao_detecta_sistema_em_delivery():
    # Texto típico de anota.ai/iFood — não confundir "sistema de pedidos" com
    # ERP próprio. O regex só aciona em contexto de GESTÃO.
    result = _ux('<p>Sistema de pedidos online para seu restaurante</p>')
    assert result["system_mention_found"] is False


def test_saas_terceiros_suprime_login_e_sistema():
    # Quando o site é hospedado em plataforma SaaS de terceiros (anota.ai,
    # iFood, Rappi), os sinais de login/portal e sistema NÃO podem ser
    # contados como evidência do lead (pertencem ao SaaS).
    result = _ux(
        '<html><body>'
        '<a href="/login">Entrar</a>'
        '<p>Nosso sistema de pedidos online</p>'
        '</body></html>',
        website_url='https://pedido.anota.ai/loja/restaurante-teste',
    )
    assert result["is_third_party_saas"] is True
    # `third_party_platform` guarda o host completo para preservar a informação
    # do subdomínio (anota.ai vs pedido.anota.ai). A normalização para a raiz
    # social está em `normalize_domain` / `_is_non_own_website_domain`.
    assert result["third_party_platform"] == "pedido.anota.ai"
    assert result["login_portal_found"] is False
    assert result["system_mention_found"] is False


def test_saas_terceiros_mantem_sinais_de_ux_basicos():
    # Sinais básicos de UX (viewport, formulário, canais) AINDA são do lead —
    # o que suprimimos é só login_portal_found/system_mention_found.
    result = _ux(
        '<html><head><meta name="viewport" content="width=device-width"></head>'
        '<body>'
        '<form action="/pedido"><input name="item"></form>'
        '<a href="https://wa.me/5511999999999">WhatsApp</a>'
        '<a href="/login">Entrar</a>'
        '</body></html>',
        website_url='https://pedido.ifood.com.br/loja/restaurante-teste',
    )
    assert result["is_third_party_saas"] is True
    assert result["viewport_ok"] is True
    assert result["contact_form_found"] is True
    assert result["whatsapp_link_found"] is True
    assert result["login_portal_found"] is False  # suprimido por SaaS


def test_dominio_proprio_mantem_login_e_sistema():
    # Quando o site é domínio próprio, detecção funciona normalmente.
    result = _ux(
        '<html><body>'
        '<a href="/login">Entrar</a>'
        '<p>Nosso ERP integra vendas e estoque</p>'
        '</body></html>',
        website_url='https://metalurgica-alfa.com.br',
    )
    assert result["is_third_party_saas"] is False
    assert result["login_portal_found"] is True
    assert result["system_mention_found"] is True


# ---- facts ancorados para o scoring ----

def test_facts_indicam_area_logada_presente():
    report = {"ux": {"login_portal_found": True, "system_mention_found": False}}
    facts = extract_technical_facts(report)
    assert any("área logada" in f.lower() or "portal" in f.lower() for f in facts)
    assert not any("nenhuma área logada" in f.lower() for f in facts)


def test_facts_indicam_ausencia_de_area_logada():
    report = {"ux": {"login_portal_found": False, "system_mention_found": False}}
    facts = extract_technical_facts(report)
    assert any("nenhuma área logada" in f.lower() or "nenhum portal" in f.lower() for f in facts)


def test_facts_indicam_menção_a_sistema():
    report = {"ux": {"login_portal_found": False, "system_mention_found": True}}
    facts = extract_technical_facts(report)
    assert any("sistema" in f.lower() and "erp" in f.lower() or "menção" in f.lower() and "sistema" in f.lower() for f in facts)