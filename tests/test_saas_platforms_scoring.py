"""Detecção de plataformas SaaS de delivery/pedidos e impacto no scoring.

Correção do falso-positivo histórico: leads hospedados em anota.ai, iFood,
Rappi, Aimpire, Pedidosky etc. eram pontuados como se o "login/portal" do
SaaS fosse evidência de sistema próprio do lead. Estes testes fixam:

- `normalize_domain` devolve None para hosts de SaaS de terceiros.
- `extract_technical_facts` injeta fact "Lead usa plataforma SaaS de
  terceiros" quando `is_third_party_saas` é True.
- `build_prompt` (template "Aplicações Web / ERP") carrega a instrução 8b
  separando SaaS de delivery de sistema de gestão próprio, e a instrução
  8c que prioriza porte/CNAE/idade na venda de ERP.
"""
import pytest

from services.domain_utils import normalize_domain, is_social_domain
from services.scoring_service import extract_technical_facts, build_prompt


@pytest.mark.parametrize("url", [
    "https://pedido.anota.ai/loja/restaurante-novo-terrao",
    "https://www.anota.ai/",
    "https://pedidos.ifood.com.br/loja/x",
    "https://www.ifood.com.br/restaurante/x",
    "https://pedidosja.com.br/loja/x",
    "https://rappi.com.br/restaurante/x",
    "https://www.rappi.com/restaurante/x",
    "https://aimpire.com/loja/x",
    "https://pedidosky.com.br/loja/x",
])
def test_normalize_domain_devolve_none_para_saas_delivery(url):
    assert normalize_domain(url) is None
    assert is_social_domain(url) is True


def test_normalize_domain_dominio_proprio_normal():
    assert normalize_domain("https://www.MetalurgicaAlfa.com.br/pagina") == "metalurgicaalfa.com.br"
    assert normalize_domain("http://academiafit.com.br") == "academiafit.com.br"


def test_normalize_domain_instagram_seguinte_como_social():
    assert normalize_domain("https://www.instagram.com/academiafit") is None
    assert normalize_domain("https://api.whatsapp.com/send") is None


def test_extract_technical_facts_inclui_saas_de_terceiros():
    report = {
        "ux": {
            "login_portal_found": False,
            "system_mention_found": False,
            "is_third_party_saas": True,
            "third_party_platform": "anota.ai",
        }
    }
    facts = extract_technical_facts(report)
    joined = " ".join(facts).lower()
    assert "anota.ai" in joined
    assert "saas" in joined
    assert "delivery" in joined or "pedidos" in joined
    # Garantir que NÃO emite os facts antigos (que induziriam o erro).
    assert "nenhuma área logada" not in joined
    assert "nenhuma menção a sistema" not in joined


def test_extract_technical_facts_sem_saas_mantem_facts_originais():
    report = {
        "ux": {
            "login_portal_found": False,
            "system_mention_found": False,
            "is_third_party_saas": False,
            "third_party_platform": None,
        }
    }
    facts = extract_technical_facts(report)
    joined = " ".join(facts).lower()
    assert "nenhuma área logada" in joined
    assert "nenhuma menção a sistema" in joined
    assert "saas" not in joined

def _erp_template():
    return {
        "service_label": "Aplicações Web / ERP",
        "positive_signals": [
            {"label": "Sem área logada / portal do cliente",
             "description": "Nenhuma área logada/portal/painel", "weight_hint": "high"},
        ],
        "negative_signals": [
            {"label": "Painel / área do cliente presente",
             "description": "Área logada, painel ou portal ativo", "weight_hint": "high"},
        ],
        "context_signals": [],
    }


def test_prompt_erp_carrega_instrucao_saas_terceiros():
    p = build_prompt(
        target_service="Aplicações web completas / ERP",
        target_segment="Restaurantes",
        template=_erp_template(),
        technical_facts=[
            "Lead usa plataforma SaaS de terceiros (anota.ai): o site não é domínio próprio",
        ],
        business_facts=["Empresa: Terraço", "Categoria: Restaurante"],
    )
    assert "8b" in p
    assert "anota.ai" in p or "delivery" in p.lower()
    assert "ERP" in p or "sistema de gestão" in p.lower()
    assert "NÃO substituem" in p or "NUNCA afirme 'o lead já tem sistema próprio'" in p


def test_prompt_erp_carrega_instrucao_porte_cnae():
    p = build_prompt(
        target_service="Aplicações web completas / ERP",
        target_segment="Restaurantes",
        template=_erp_template(),
        technical_facts=[],
        business_facts=["Porte: MICRO", "Idade: 1 ano"],
    )
    assert "8c" in p
    assert "PORTE" in p or "porte" in p
    assert "CNAE" in p or "cnae" in p
    assert "MICRO" in p or "MEI" in p


def test_prompt_erp_sem_saas_com_sistema_proprio():
    # Lead com sistema de gestão PRÓPRIO no domínio próprio — score deve cair.
    p = build_prompt(
        target_service="Aplicações web completas / ERP",
        target_segment="Indústria",
        template=_erp_template(),
        technical_facts=[
            "Área logada/portal/painel presente na página (indício de sistema próprio)",
            "Menção a sistema/ERP/software na página (indício de automação)",
        ],
        business_facts=["Porte: Grande", "Idade: 15 anos"],
    )
    assert "8b" in p
    assert "10 anos" in p or "legado" in p.lower()


def test_prompt_nao_erp_nao_carrega_instrucao_8c():
    # Template de engenharia NÃO deve carregar a instrução 8c (foco ERP).
    eng_template = {
        "service_label": "Engenharia Mecânica & Desenhos Técnicos CAD",
        "positive_signals": [],
        "negative_signals": [],
        "context_signals": [],
    }
    p = build_prompt(
        target_service="Projetos mecânicos / usinagem",
        target_segment="Indústrias",
        template=eng_template,
        technical_facts=[],
        business_facts=[],
    )
    # Instrução 8b (SaaS de terceiros) é GLOBAL — sempre presente.
    assert "8b" in p
    # Instrução 8c (foco em porte/CNAE para ERP) é ESPECÍFICA — só ERP.
    assert "8c" not in p