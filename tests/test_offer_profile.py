"""Testes do OfferProfile Resolver (Fase B — consolidação §3).

Seam: `OfferProfileResolver.resolve(offer_key|vertical|archetype)`,
       `OfferProfileRegistry.list()`.
Capacidade: resolver uma oferta comercial completa (ICP + discovery +
prescoring + signals + intent + decision_makers + channels + outreach) a
partir de uma chave, com fallback em cascata:
    explicit offer_profile
       ↓ fallback
    vertical
       ↓ fallback
    archetype
       ↓ fallback
    generic
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.prospecting.offer_profile import (  # noqa: E402
    OfferProfile,
    OfferProfileResolver,
    OfferProfileRegistry,
)


class TestOfferProfile:
    def test_perfil_basico_tem_todas_as_secoes_obrigatorias(self):
        p = OfferProfile(key="landing_page", archetype="web_presence", vertical="digital")
        # Defaults vazios para cada seção do contrato consolidação §3.3
        assert p.icp == {}
        assert p.discovery == {}
        assert p.prescoring == {}
        assert p.enrichment == {}
        assert p.signals == {}
        assert p.intent == {}
        assert p.decision_makers == {}
        assert p.channels == {}
        assert p.qualification == {}
        assert p.outreach == {}
        assert p.version == "1.0"  # default version

    def test_to_dict_e_from_dict_sao_inversos(self):
        p = OfferProfile(
            key="trophies",
            archetype="custom_products",
            vertical="awards",
            version="2.1",
            icp={"segments": ["esportivos", "corporativos"]},
            discovery={"providers": ["google_places", "instagram_search"]},
        )
        d = p.to_dict()
        p2 = OfferProfile.from_dict(d)
        assert p2.key == "trophies"
        assert p2.version == "2.1"
        assert p2.icp["segments"] == ["esportivos", "corporativos"]

    def test_perfil_imutavel(self):
        """OfferProfile é declarativo, não mutável após criação."""
        p = OfferProfile(key="x", archetype="a", vertical="v")
        try:
            p.key = "y"  # type: ignore
            assert False, "OfferProfile deveria ser imutável"
        except (AttributeError, TypeError):
            pass


class TestOfferProfileRegistry:
    def test_registry_list_retorna_lista(self):
        registry = OfferProfileRegistry()
        profiles = registry.list()
        assert isinstance(profiles, list)

    def test_registry_get_inexistente_retorna_none(self):
        registry = OfferProfileRegistry()
        assert registry.get("perfil_que_nao_existe_xyz") is None

    def test_registry_registra_e_recupera(self):
        registry = OfferProfileRegistry()
        p = OfferProfile(key="custom", archetype="a", vertical="v")
        registry.register(p)
        assert registry.get("custom") is p


class TestOfferProfileResolver:
    def test_resolver_explicit_offer_profile_tem_prioridade_maxima(self):
        registry = OfferProfileRegistry()
        registry.register(OfferProfile(
            key="explicit", archetype="a", vertical="v",
            icp={"segments": ["explicit"]},
        ))
        registry.register(OfferProfile(
            key="vertical_fallback", archetype="a", vertical="v",
            icp={"segments": ["vertical"]},
        ))
        resolver = OfferProfileResolver(registry)
        result = resolver.resolve(offer_profile_key="explicit", vertical_key="v")
        assert result.icp["segments"] == ["explicit"]

    def test_resolver_cai_no_vertical_quando_offer_inexistente(self):
        registry = OfferProfileRegistry()
        # Registra um perfil com vertical="mechanical_engineering"
        registry.register(OfferProfile(
            key="mechanical_project", archetype="industrial", vertical="mechanical_engineering",
            icp={"segments": ["vertical"]},
        ))
        resolver = OfferProfileResolver(registry)
        # Pede via vertical_key (sem offer_profile_key explícito) — deve cair no vertical
        result = resolver.resolve(
            offer_profile_key="nao_existe",
            vertical_key="mechanical_engineering",
        )
        assert result.icp["segments"] == ["vertical"]
        assert result.resolved_from == "vertical"

    def test_resolver_cai_no_archetype(self):
        registry = OfferProfileRegistry()
        registry.register(OfferProfile(
            key="a_test", archetype="web_presence", vertical="any",
            icp={"segments": ["archetype"]},
        ))
        resolver = OfferProfileResolver(registry)
        result = resolver.resolve(
            offer_profile_key="nope", vertical_key="nope_v",
            archetype_key="web_presence",
        )
        assert result.icp["segments"] == ["archetype"]
        assert result.resolved_from == "archetype"

    def test_resolver_cai_no_generic_se_nada_encontrar(self):
        resolver = OfferProfileResolver(OfferProfileRegistry())
        result = resolver.resolve(
            offer_profile_key="nope",
            vertical_key="nope",
            archetype_key="nope",
        )
        # Não explode e retorna um perfil generic
        assert result is not None
        assert result.archetype == "generic"
        assert result.resolved_from == "generic"

    def test_cascata_resolvida_retorna_origem(self):
        """Resolver deve indicar qual nível da cascata foi usado."""
        registry = OfferProfileRegistry()
        registry.register(OfferProfile(
            key="v_test", archetype="a", vertical="mechanical_engineering",
            icp={"segments": ["vertical"]},
        ))
        resolver = OfferProfileResolver(registry)
        result = resolver.resolve(
            offer_profile_key=None, vertical_key="mechanical_engineering",
        )
        # Resultado indica que veio do vertical
        assert result.resolved_from == "vertical"


class TestDefaultRegistry:
    def test_registry_padrao_tem_5_profiles_iniciais(self):
        from services.prospecting.default_profiles import get_default_registry
        registry = get_default_registry()
        profiles = {p.key for p in registry.list()}
        assert "landing_page" in profiles
        assert "mechanical_project" in profiles
        assert "technical_drawing" in profiles
        assert "machine_manual" in profiles
        assert "trophies" in profiles

    def test_landing_page_tem_vertical_digital(self):
        from services.prospecting.default_profiles import get_default_registry
        p = get_default_registry().get("landing_page")
        assert p.vertical == "digital"
        assert p.icp["company_sizes"] == ["ME", "PE"]

    def test_mechanical_project_tem_cnaes_industriais(self):
        from services.prospecting.default_profiles import get_default_registry
        p = get_default_registry().get("mechanical_project")
        # CNAEs industriais (25, 28, 33 = metalúrgica, máquinas, instalação)
        assert "25" in p.icp["cnaes"]
        assert p.decision_makers["roles"][0] in ("plant_engineer", "operations_director")

    def test_trophies_tem_decay_curto_eventos(self):
        from services.prospecting.default_profiles import get_default_registry
        p = get_default_registry().get("trophies")
        # Eventos têm ciclo curto → decay 30d
        assert p.intent["decay_days"] <= 60
        assert "whatsapp" in p.channels["priority"]

    def test_industrial_3_ofertas_diferentes_mesmo_vertical(self):
        """Consolidação §3.2: vertical mechanical_engineering tem múltiplas ofertas."""
        from services.prospecting.default_profiles import get_default_registry
        registry = get_default_registry()
        mech = registry.by_vertical("mechanical_engineering")
        assert len(mech) == 3  # mechanical_project, technical_drawing, machine_manual
        # Cada uma tem ICP distinto (consolidação §27: "Não duplicar inteligência")
        cnaes_list = [tuple(p.icp.get("cnaes", [])) for p in mech]
        assert len(set(cnaes_list)) == 3  # CNAEs únicos

    def test_registry_substituir_chave_nao_deixa_indices_stale(self):
        """Re-registrar uma key deve remover os índices da versão anterior."""
        from services.prospecting import OfferProfile, OfferProfileRegistry

        registry = OfferProfileRegistry()
        registry.register(OfferProfile(key="x", archetype="old", vertical="old"))
        registry.register(OfferProfile(key="x", archetype="new", vertical="new"))
        assert registry.get("x").archetype == "new"
        assert registry.by_archetype("old") == []
        assert registry.by_vertical("old") == []
        assert registry.by_archetype("new")[0].key == "x"

    def test_from_dict_com_campo_ausente_usa_defaults_corretos(self):
        from services.prospecting import OfferProfile

        profile = OfferProfile.from_dict({
            "key": "minimal",
            "archetype": "generic",
            "vertical": "generic",
        })
        assert profile.version == "1.0"
        assert profile.discovery == {}
        assert profile.outreach == {}
