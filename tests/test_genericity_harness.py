"""Genericity Test Harness — lado comportamental (Task 2).

Cada capability é exercitada com as três verticais do contrato (Troféus,
Sistemas Web/ERP e Engenharia Mecânica) usando **a mesma implementação**. O que
muda é apenas o OfferProfile. Um teste que só passe para uma vertical indica
que a capability embutiu conhecimento de domínio.
"""
import pytest

from services.prospecting.buyer_persona import (
    KNOWN_BUYER_ROLES,
    infer_buyer_role,
    resolve_buyer_role,
)
from services.prospecting.discovery_executor import (
    DiscoveryExecutor,
    DiscoveryProviderRegistry,
    _StubProvider,
)
from services.prospecting.intent_provider import IntentScorer
from services.prospecting.next_best_action_service import NextBestActionService
from services.prospecting.offer_matcher import OfferMatcher
from services.prospecting.offer_profile_validator import validate_profile

from genericity.contract import (
    DISCOVERY_RESULT_KEYS,
    INTENT_SCORE_KEYS,
    NEXT_ACTION_KEYS,
    OPPORTUNITY_KEYS,
    declared_providers,
    discovery_plan_from_profile,
    disqualified_lead,
    ideal_lead,
    intent_config,
)
from genericity.profiles import (
    CONTRACT_KEYS,
    ENGINEERING_KEY,
    PRODUCTION_KEYS,
    TROPHIES_KEY,
    WEB_ERP_KEY,
    contract_profiles,
    contract_registry,
)

PROFILES = contract_profiles()


@pytest.fixture(scope="module")
def registry():
    return contract_registry()


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_perfil_do_contrato_e_valido(key):
    problems = validate_profile(PROFILES[key])
    errors = [p for p in problems if not p.startswith("aviso:")]
    assert errors == [], f"{key}: {errors}"


@pytest.mark.parametrize("key", PRODUCTION_KEYS)
def test_verticais_de_producao_existem_no_registry_padrao(key):
    from services.prospecting.default_profiles import get_default_registry
    assert get_default_registry().get(key) is not None


def test_contrato_cobre_duas_verticais_opostas_e_engenharia():
    trophies = PROFILES[TROPHIES_KEY]
    web_erp = PROFILES[WEB_ERP_KEY]
    engineering = PROFILES[ENGINEERING_KEY]
    assert len({trophies.vertical, web_erp.vertical, engineering.vertical}) == 3
    assert trophies.intent["decay_days"] < web_erp.intent["decay_days"]
    assert set(declared_providers(trophies)) != set(declared_providers(web_erp))


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_matcher_produz_o_mesmo_formato_para_toda_vertical(registry, key):
    matches = OfferMatcher(registry).match(ideal_lead(key), min_score=1)
    assert matches, f"{key}: nenhuma oportunidade gerada para o lead ideal"
    for opportunity in matches:
        assert set(opportunity.to_dict()) == OPPORTUNITY_KEYS


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_matcher_ranqueia_a_vertical_certa_por_configuracao(registry, key):
    matches = OfferMatcher(registry).match(ideal_lead(key), min_score=1)
    assert matches[0].offer_key == key
    assert matches[0].score > 0
    assert matches[0].signals_matched


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_matcher_desqualifica_pelo_sinal_declarado_no_perfil(registry, key):
    """Só exige caminho binário quando o perfil declara um desqualificador.

    Perfis podem modelar contra-sinais como penalidades graduais. O contrato não
    inventa uma semântica de desqualificação que a configuração comercial não
    declarou.
    """
    profile = PROFILES[key]
    lead = disqualified_lead(profile)
    if lead is None:
        assert not (profile.signals or {}).get("disqualifiers")
        return
    matches = OfferMatcher(registry).match(lead, min_score=0)
    target = next((m for m in matches if m.offer_key == key), None)
    assert target is not None
    assert target.score == 0
    assert any(item.startswith("DISQUALIFIED_BY_") for item in target.evidence)


def test_matcher_e_uma_unica_implementacao_para_as_tres_verticais(registry):
    matcher = OfferMatcher(registry)
    scored = {key: matcher.match(ideal_lead(key), min_score=1)[0] for key in CONTRACT_KEYS}
    assert {key: opportunity.offer_key for key, opportunity in scored.items()} == {
        key: key for key in CONTRACT_KEYS
    }


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_intent_mantem_formato_para_toda_vertical(key):
    config = intent_config(PROFILES[key])
    scorer = IntentScorer(**config)
    result = scorer.score({"key": "HIRING", "confidence": 0.9, "observed_at": None})
    assert INTENT_SCORE_KEYS <= set(result)


def test_intent_diverge_apenas_por_configuracao_do_perfil():
    from datetime import datetime, timedelta, timezone

    observed = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    event = {"key": "HIRING", "confidence": 0.9, "observed_at": observed}
    scores = {}
    for key in CONTRACT_KEYS:
        scorer = IntentScorer(**intent_config(PROFILES[key]))
        scores[key] = scorer.score(event)["score"]
    assert scores[TROPHIES_KEY] == 0.0
    assert scores[WEB_ERP_KEY] > scores[ENGINEERING_KEY] > 0


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_next_best_action_mantem_formato_e_segue_a_oferta_do_dado(key):
    lead = {
        "status": "QUALIFICADO",
        "has_verified_email": True,
        "opportunities": [{"offer_key": key, "score": 90}],
    }
    action = NextBestActionService().recommend(lead)
    assert NEXT_ACTION_KEYS <= set(action)
    assert action["offer_key"] == key


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_next_best_action_bloqueia_opt_out_em_qualquer_vertical(key):
    lead = {"opt_out": True, "opportunities": [{"offer_key": key, "score": 90}]}
    action = NextBestActionService().recommend(lead)
    assert action["action"] == "STOP"


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_discovery_executa_os_providers_declarados_pelo_perfil(key):
    profile = PROFILES[key]
    expected = declared_providers(profile)
    assert expected, f"{key}: perfil não declara providers de discovery"
    registry = DiscoveryProviderRegistry()
    for index, name in enumerate(expected):
        registry.register(_StubProvider(name=name, results=[{"name": f"{name}-empresa-{index}"}]))
    plan = discovery_plan_from_profile(profile)
    result = DiscoveryExecutor(registry).execute(plan)
    assert DISCOVERY_RESULT_KEYS <= set(result)
    assert result["execution_order"] == expected
    assert result["skipped"] == []
    assert result["unique_count"] == len(expected)


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_discovery_ignora_provider_ausente_sem_derrubar_o_run(key):
    profile = PROFILES[key]
    expected = declared_providers(profile)
    registry = DiscoveryProviderRegistry()
    registry.register(_StubProvider(name=expected[0], results=[{"name": "unica"}]))
    result = DiscoveryExecutor(registry).execute(discovery_plan_from_profile(profile))
    assert result["execution_order"] == [expected[0]]
    assert set(result["skipped"]) == set(expected[1:])


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_perfil_declara_decisores_com_buyer_types_conhecidos(key):
    decision_makers = PROFILES[key].decision_makers or {}
    roles = decision_makers.get("roles") or []
    assert roles, f"{key}: perfil sem decisores declarados"
    for buyer_type in decision_makers.get("buyer_types") or []:
        assert buyer_type in KNOWN_BUYER_ROLES


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_buyer_role_e_inferido_pelos_cargos_do_perfil(key):
    for role in (PROFILES[key].decision_makers or {}).get("roles") or []:
        inferred = infer_buyer_role(role)
        assert inferred in KNOWN_BUYER_ROLES | {"UNKNOWN"}
        resolved = resolve_buyer_role({"role": role})
        assert resolved["buyer_role"] == inferred
        assert resolved["buyer_role_source"] in {"inferred", "unknown"}


def test_buyer_role_nao_inventa_papel_sem_cargo():
    assert infer_buyer_role(None) == "UNKNOWN"
    assert resolve_buyer_role({})["buyer_role_source"] == "unknown"


def test_engenharia_atravessa_o_contrato_sem_codigo_dedicado(registry):
    profile = PROFILES[ENGINEERING_KEY]
    assert validate_profile(profile) == [] or all(
        p.startswith("aviso:") for p in validate_profile(profile)
    )
    top = OfferMatcher(registry).match(ideal_lead(ENGINEERING_KEY), min_score=1)[0]
    assert top.offer_key == ENGINEERING_KEY
    assert IntentScorer(**intent_config(profile)).score(
        {"key": "NEW_EQUIPMENT", "confidence": 0.8, "observed_at": None}
    )["triggered"] is True
    action = NextBestActionService().recommend({
        "status": "QUALIFICADO",
        "has_verified_email": True,
        "opportunities": [{"offer_key": ENGINEERING_KEY, "score": 80}],
    })
    assert action["offer_key"] == ENGINEERING_KEY


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_enrichment_declara_passos_conhecidos_pelo_capability_registry(key):
    from services.enrichment_capability_registry import CAPABILITIES, ENRICHMENT_STEP_KEYS
    from services.prospecting.offer_profile_validator import LEGACY_ENRICHMENT_STEPS, validate_profile

    profile = PROFILES[key]
    warnings = [p for p in validate_profile(profile) if p.startswith("aviso:")]
    for step in (profile.enrichment or {}).get("steps") or []:
        assert step in set(ENRICHMENT_STEP_KEYS) | set(LEGACY_ENRICHMENT_STEPS), (
            f"{key}: passo {step!r} não existe no capability registry"
        )
        if step in LEGACY_ENRICHMENT_STEPS:
            assert any(step in warning for warning in warnings)
            continue
        assert "cost" in CAPABILITIES[step]
        assert "produces" in CAPABILITIES[step]


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_enrichment_declara_orcamento_de_descoberta_de_pessoas(key):
    people = (PROFILES[key].enrichment or {}).get("people_discovery") or {}
    assert people, f"{key}: perfil sem people_discovery"
    assert people["max_cost"] >= 0
    assert people["max_steps"] >= 1
    assert 0 <= people["min_role_fit"] <= 100


def test_enrichment_diverge_por_configuracao_entre_verticais():
    steps = {
        key: tuple((PROFILES[key].enrichment or {}).get("steps") or ())
        for key in CONTRACT_KEYS
    }
    assert len(set(steps.values())) > 1, steps
