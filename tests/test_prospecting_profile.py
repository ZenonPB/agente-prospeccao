"""Resolução do ProspectingProfile a partir do template (docs/melhorias/17)."""
from services.prospecting_profile_service import (
    DEFAULT_PRESCORING_WEIGHTS,
    PROFILE_BUSINESS,
    PROFILE_INDUSTRIAL,
    PROFILE_WEB_PRESENCE,
    STEP_BUSINESS_SOCIAL,
    STEP_CNPJ_RECEITA,
    STEP_TECHNICAL_SITE,
    derive_profile_key,
    resolve_prospecting_profile,
)


def test_deriva_web_presence_pelo_step_de_site():
    profile = derive_profile_key({"enrichment_steps": ["technical_site"]})
    assert profile == PROFILE_WEB_PRESENCE


def test_deriva_business_quando_so_cnpj():
    profile = derive_profile_key({"enrichment_steps": ["cnpj_receita", "business_social"]})
    assert profile == PROFILE_BUSINESS


def test_sem_template_cai_em_web_presence():
    """Compatibilidade: template Genérico/ausente mantém o perfil histórico."""
    assert derive_profile_key(None) == PROFILE_WEB_PRESENCE
    assert resolve_prospecting_profile(None)["profile_key"] == PROFILE_WEB_PRESENCE


def test_config_do_template_sobrescreve_derivacao():
    profile = resolve_prospecting_profile({
        "enrichment_steps": ["technical_site"],
        "prescoring_config": {"profile": PROFILE_INDUSTRIAL},
    })
    assert profile["profile_key"] == PROFILE_INDUSTRIAL
    assert profile["profile_source"] == "template_config"


def test_derive_profile_key_tambem_respeita_config_do_template():
    """O score vetorial usa `derive_profile_key`; ele precisa coincidir com o
    gate (que usa `resolve_prospecting_profile`) — senão a mesma campanha
    pontua com pesos diferentes no pré-scoring e no vetor."""
    assert derive_profile_key({
        "enrichment_steps": ["technical_site"],
        "prescoring_config": {"profile": PROFILE_BUSINESS},
    }) == PROFILE_BUSINESS
    assert derive_profile_key({
        "enrichment_steps": ["cnpj_receita", "business_social"],
        "prescoring_config": {"profile": PROFILE_INDUSTRIAL},
    }) == PROFILE_INDUSTRIAL


def test_gate_desligado_por_padrao():
    """Sem prescoring_config, nenhum candidato é descartado (comportamento atual)."""
    profile = resolve_prospecting_profile({"enrichment_steps": ["technical_site"]})
    assert profile["prescoring"]["enabled"] is False


def test_pesos_default_por_perfil():
    for key in (PROFILE_WEB_PRESENCE, PROFILE_BUSINESS, PROFILE_INDUSTRIAL):
        profile = resolve_prospecting_profile({
            "enrichment_steps": ["technical_site"],
            "prescoring_config": {"profile": key},
        })
        assert profile["prescoring"]["weights"] == DEFAULT_PRESCORING_WEIGHTS[key]


def test_config_invalida_cai_no_default():
    profile = resolve_prospecting_profile({
        "enrichment_steps": ["cnpj_receita"],
        "prescoring_config": {
            "profile": "vertical-inexistente",
            "threshold": "não-numérico",
        },
    })
    assert profile["profile_key"] == PROFILE_BUSINESS
    assert profile["prescoring"]["threshold"] > 0


def test_top_k_booleano_e_ignorado():
    profile = resolve_prospecting_profile({
        "enrichment_steps": ["technical_site"],
        "prescoring_config": {"profile": "web_presence", "top_k": True},
    })
    assert profile["prescoring"]["top_k"] is None


def test_top_k_valido_e_preservado():
    profile = resolve_prospecting_profile({
        "enrichment_steps": ["technical_site"],
        "prescoring_config": {"profile": "web_presence", "top_k": 7},
    })
    assert profile["prescoring"]["top_k"] == 7


def test_step_constants_sao_a_fonte_da_derivacao():
    """Renomear um step aqui quebra a derivação — teste guarda-chuva."""
    assert STEP_TECHNICAL_SITE == "technical_site"
    assert STEP_CNPJ_RECEITA == "cnpj_receita"
    assert STEP_BUSINESS_SOCIAL == "business_social"
