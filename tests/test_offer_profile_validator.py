"""Validação semântica de OfferProfile (P1.4).

Seam sob teste: `validate_profile(profile)` — função pura que devolve a
lista de problemas (vazia = válido). Valores esperados vêm de literais
conhecidos, nunca recomputados pelo código sob teste.
"""
from services.prospecting.default_profiles import build_default_registry
from services.prospecting.offer_profile import OfferProfile
from services.prospecting.offer_profile_validator import (
    validate_profile,
    validate_registry,
)


def _erros(problems):
    """Só erros invalidam; itens 'aviso: ...' são observabilidade."""
    return [p for p in problems if not p.startswith("aviso:")]


def test_profiles_padrao_sao_estruturalmente_validos():
    registry = build_default_registry()
    assert len(registry.list()) >= 5
    for profile in registry.list():
        problems = validate_profile(profile)
        assert _erros(problems) == [], f"{profile.key}: {problems}"


def test_profiles_padrao_usam_sinais_registrados():
    from services.signal_registry import SIGNAL_REGISTRY
    registry = build_default_registry()
    for profile in registry.list():
        problems = validate_profile(profile)
        desconhecidos = [p for p in _erros(problems) if "signal" in p]
        assert desconhecidos == [], f"{profile.key}: {desconhecidos}"
    assert "HAS_CNPJ" in SIGNAL_REGISTRY
    assert "HOSTS_EVENTS" in SIGNAL_REGISTRY


def test_registry_padrao_sem_erros_operacional():
    """O build valida e expõe só erros; registry padrão deve ter zero."""
    registry = build_default_registry()
    assert validate_registry(registry) == {}


def test_perfil_invalido_reporta_todos_os_problemas_estruturais():
    bad = OfferProfile(
        key="",
        archetype="",
        vertical="",
        version="versao-qualquer",
        prescoring={
            "weights": {"HAS_PHONE": -3},
            "threshold": 999,
            "top_k": 0,
            "on_insufficient_data": "explodir",
        },
        intent={"event_weights": {"HIRING": 42.0}, "decay_days": -1,
                "trigger_threshold": 9.0},
        decision_makers={"roles": [], "buyer_types": ["DONO_DE_TUDO"]},
        channels={"priority": ["correio", "email"]},
        enrichment={"people_discovery": {"max_cost": -1, "max_steps": 99,
                                         "min_role_fit": 101}},
        signals={"positive": ["SINAL_INEXISTENTE_XYZ"]},
    )
    problems = validate_profile(bad)
    texto = " ".join(problems)
    assert "key" in texto
    assert "version" in texto
    assert "threshold" in texto
    assert "top_k" in texto
    assert "weights" in texto
    assert "event_weights" in texto
    assert "roles" in texto
    assert "buyer_types" in texto
    assert "channels" in texto
    assert "people_discovery" in texto
    assert "signal" in texto
