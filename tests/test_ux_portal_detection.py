"""Detecção determinística de área logada/portal e menção a sistema no HTML.

O template "Aplicações Web / ERP" marca "área logada/portal" e "menção a
sistema/ERP" como critérios a CONFIRMAR no HTML, mas o enrichment não media
nada disso — a LLM inferia. Estes testes garantem que `_check_ux` passa a
medir e que `extract_technical_facts` transforma a medição em fact ancorado.
Sem rede — funções puras.
"""
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import extract_technical_facts


def _ux(html):
    return TechnicalEnrichmentService()._check_ux(html)


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
    result = _ux('<a href="/sistema">Acessar sistema</a>')
    assert result["system_mention_found"] is True


def test_detecta_menção_software():
    result = _ux('<p>Software de gestão próprio</p>')
    assert result["system_mention_found"] is True


def test_nao_detecta_sistema_em_site_institucional():
    result = _ux('<h1>Academia Fit</h1><p>Bem-vindo</p>')
    assert result["system_mention_found"] is False


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