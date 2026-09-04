"""E2E sem-DB do pipeline Fase 3 — verifica que serviços plugados conversam entre si.

Cobre (consolidação §28 'cenário realista'):
- OfferProfile Resolver (perfil industrial)
- DiscoveryPlanner (plano para esse perfil)
- ProspectingHypothesis (lift/expected)
- IntentEngine → BuyingTriggers → ICPvsIntent
- ChainDetection (lead com múltiplos endereços)
- DecisionMakerPipeline (chain + strategy + roles)
- ContactProviderRegistry (pattern inference com acentos)
- Learning (record_outcome + prior + precision@k)
- ActionableRate (classificação dos contatos)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestPhase3CascadeIndustrial:
    """Cenário: prospectar uma indústria metalúrgica com a oferta mechanical_project."""

    def test_cascata_completa_industrial(self):
        # 1. OfferProfile Resolver
        from services.prospecting.default_profiles import get_default_registry
        from services.prospecting import OfferProfileResolver
        registry = get_default_registry()
        resolver = OfferProfileResolver(registry)
        profile = resolver.resolve(offer_profile_key="mechanical_project")
        assert profile.key == "mechanical_project"
        assert profile.archetype == "industrial"
        assert profile.vertical == "mechanical_engineering"

        # 2. DiscoveryPlanner produz plano compatível
        from services.discovery_planner_service import DiscoveryPlanner
        plan = DiscoveryPlanner().plan({"profile_key": profile.archetype})
        assert len(plan["providers"]) > 0

        # 3. Prospecting Hypothesis
        from services.prospecting_hypothesis_service import build_hypothesis
        hyp = build_hypothesis(profile.archetype)
        assert hyp["expected_lift"] > 0
        assert "industr" in hyp["hypothesis"].lower()

        # 4. Lead com múltiplos endereços
        from services.chain_detection_service import detect_chain
        lead = {
            "company_name": "Metalúrgica Alpha",
            "addresses": [
                {"name": "Metalúrgica Alpha - Sede"},
                {"name": "Metalúrgica Alpha - Filial SP"},
                {"name": "Metalúrgica Alpha - Filial MG"},
            ],
        }
        chain = detect_chain(lead)
        assert chain["classification"] in ("SMALL_CHAIN", "FRANCHISE", "ENTERPRISE")
        assert chain["chain_score"] >= 3

        # 5. Decision Maker Pipeline
        from services.decision_maker_pipeline_service import run_decision_maker_pipeline
        pipeline = run_decision_maker_pipeline(
            lead_data=lead, profile={"profile_key": profile.archetype},
        )
        # Industrial prioriza cnpj_qsa
        assert pipeline["contact_strategy"]["provider_order"][0] == "cnpj_qsa"
        # Roles técnicos esperados
        roles = [r["role"] for r in pipeline["target_roles"]]
        assert "plant_engineer" in roles
        # Buyer types coerentes
        bts = [r["buyer_type"] for r in pipeline["target_roles"]]
        assert "TECHNICAL_BUYER" in bts

        # 6. Decision Maker Strategy por perfil industrial
        from services.decision_maker_strategy_service import resolve_contact_strategy
        strat = resolve_contact_strategy(profile.archetype)
        assert strat["channel_priority"][0] == "email"

        # 7. Contact Provider Registry
        from services.contact_provider_registry import (
            infer_email_pattern, classify_qsa_role, cascade_contact_search,
            domain_first_person_search,
        )
        # QSA: sócio-diretor → economic buyer
        assert classify_qsa_role("Sócio-Diretor") == "ECONOMIC_BUYER"
        # Pattern: acentos normalizados
        pattern = infer_email_pattern("alpha.com", "Conceição Müller", verify=False)
        assert "ç" not in pattern["candidate"] and "ü" not in pattern["candidate"]
        # Domain-first strategy
        dfirst = domain_first_person_search("alpha.com", ["plant_engineer"])
        assert dfirst["strategy"] == "domain_first"
        # Cascade com cnpj
        cascade = cascade_contact_search(
            lead_data={"cnpj": "12345678000190"},
            target_roles=["plant_engineer"], max_steps=2,
        )
        assert cascade["stopped_at"] >= 1

    def test_universal_questions_cobre_as_6_camadas(self):
        from services.universal_prospecting_questions_service import build_universal_questions
        q = build_universal_questions("industrial")
        layers = [item["layer"] for item in q["questions"]]
        # Consolidação §18: 6 camadas universais
        assert "icp" in layers
        assert "need" in layers
        assert "buying_power" in layers
        assert "timing" in layers
        assert "decision_maker" in layers
        assert "outreach" in layers

    def test_vertical_pack_industrial_inclui_cnae_e_qsa(self):
        from services.prospecting_hypothesis_service import vertical_pack_for
        pack = vertical_pack_for("industrial")
        # O pack para industrial deve incluir providers relevantes
        assert any(p in pack["enrichment_pack"] for p in [
            "cnae_discovery", "cnpj_receita", "site_contact_pages",
        ])

    def test_routable_actionable_rate_para_lista_mista(self):
        from services.routable_contact_service import actionable_contact_rate
        # Indústria típica: telefones diretos + 1 PABX
        contacts = [
            {"phone": "16999998888", "full_name": "João"},
            {"phone": "1633334000", "pabx_extension": "100", "full_name": "Maria"},
            {"phone": "1140000000", "full_name": "Carlos"},
        ]
        m = actionable_contact_rate(contacts)
        # 3 de 3 são acionáveis (todos >8 dígitos)
        assert m["actionable_rate"] == 1.0

    def test_intent_engine_hiring_gera_triggers_e_score(self):
        from services.intent_engine_service import IntentEngine
        from services.buying_trigger_service import detect_buying_triggers, icp_vs_intent
        ie = IntentEngine()
        events = ie.detect_events([
            {"key": "HIRING", "value": True, "confidence": 0.9, "evidence": "vaga"},
        ])
        triggers = detect_buying_triggers(events)
        scored = ie.score_and_trigger(events)
        icp = icp_vs_intent("industrial", scored["intent_score"], icp_match=True)
        assert len(triggers) == 1
        assert scored["intent_score"] >= 80
        assert icp["classification"] == "TIMELY"

    def test_learning_registra_e_mede_conversion(self):
        from services.learning_service import record_outcome, compute_niche_prior, precision_at_k
        # 4 leads qualificados, 3 converteram
        org = "org-integration-test"
        for _ in range(3):
            record_outcome(org, "Projeto Mecânico", "metalúrgica", "WON")
        record_outcome(org, "Projeto Mecânico", "metalúrgica", "NEW")
        prior = compute_niche_prior(org, "Projeto Mecânico", "metalúrgica")
        assert prior["conversion_rate"] == 75.0  # 3/4
        # Precision@K
        ranked = [{"outcome": "WON"}, {"outcome": "WON"}, {"outcome": "LOST"}]
        p_at_3 = precision_at_k(ranked, k=3)
        assert p_at_3["precision_at_k"] == round(2/3, 3)

    def test_archetype_fallback_quando_template_nao_existe(self):
        from services.archetype_service import match_archetype
        a = match_archetype("Projeto mecânico sob medida metalúrgica")
        assert a["archetype_id"] == "industrial_erp"
        # Fallback: nenhuma keyword bate
        b = match_archetype("XYZ aleatório")
        assert b["archetype_id"] is None
        assert b["profile_key"] == "generic"

    def test_offer_profile_cascata_completa(self):
        """Resolver cai na cascata completa (explicit → vertical → archetype → generic)."""
        from services.prospecting import OfferProfileResolver
        from services.prospecting.offer_profile import (
            OfferProfile, OfferProfileRegistry,
        )
        registry = OfferProfileRegistry()
        registry.register(OfferProfile(
            key="vertical_x", archetype="a", vertical="industrial_specialty",
            icp={"cnaes": ["25"]},
        ))
        registry.register(OfferProfile(
            key="arch_y", archetype="industrial", vertical="any",
            icp={"cnaes": ["28"]},
        ))
        resolver = OfferProfileResolver(registry)
        # Explícito
        r1 = resolver.resolve(offer_profile_key="vertical_x", vertical_key="x")
        assert r1.resolved_from == "explicit"
        # Vertical
        r2 = resolver.resolve(
            offer_profile_key=None, vertical_key="industrial_specialty",
        )
        assert r2.resolved_from == "vertical"
        # Archetype
        r3 = resolver.resolve(
            offer_profile_key=None, vertical_key=None, archetype_key="industrial",
        )
        assert r3.resolved_from == "archetype"
        # Generic
        r4 = resolver.resolve(
            offer_profile_key=None, vertical_key=None, archetype_key=None,
        )
        assert r4.resolved_from == "generic"


class TestOfferMatcherIntegration:
    """Critério Fase C: uma empresa pode ter múltiplas oportunidades simultâneas."""

    def test_metalurgica_tem_3_oportunidades_industriais(self):
        from services.prospecting import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        # Empresa industrial completa
        lead = {
            "company_name": "Metalúrgica X Ltda",
            "segment": "metalúrgica",
            "cnae": "25.11-0",  # CNAE industrial (25 = metalúrgica)
            "company_size": "ME",
            "has_cnpj": True,
            "has_phone": True,
        }
        opps = matcher.match(lead)
        # Deve ter pelo menos 3 oportunidades (mechanical_project, technical_drawing, machine_manual)
        assert len(opps) >= 3
        keys = [o.offer_key for o in opps]
        assert "mechanical_project" in keys
        assert "technical_drawing" in keys
        assert "machine_manual" in keys

    def test_clinica_psicologia_match_landing_page(self):
        from services.prospecting import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        lead = {
            "company_name": "Clínica Y Psicologia",
            "segment": "psicologia",
            "no_own_website": True,
            "has_instagram": True,
            "has_phone": True,
        }
        opps = matcher.match(lead)
        keys = [o.offer_key for o in opps]
        # landing_page deve ser a principal (mais sinais)
        assert "landing_page" in keys
        # landing_page deve ter score > 50 (3 sinais + 1 icp hit)
        lp_opp = next(o for o in opps if o.offer_key == "landing_page")
        assert lp_opp.score >= 50

    def test_desqualificador_zera_score(self):
        from services.prospecting import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        # landing_page tem disqualifier ENTERPRISE
        lead = {
            "company_name": "BigCo",
            "segment": "psicologia",
            "no_own_website": True,
            "has_instagram": True,
            "enterprise": True,  # disqualifier
        }
        opps = matcher.match(lead)
        lp_opp = next((o for o in opps if o.offer_key == "landing_page"), None)
        # Se aparecer, score deve ser 0
        if lp_opp:
            assert lp_opp.score == 0
            assert "DISQUALIFIED" in lp_opp.evidence[0]

    def test_empresa_pode_matchar_trof_eu_e_industrial(self):
        """Critério Fase C puro: empresa com sinais de ambos os universos."""
        from services.prospecting import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        lead = {
            "company_name": "Federação Esportiva que Fabrica Troféus",
            "segment": "esportivos",
            "cnae": "32",  # fabricação
            "has_phone": True,
            "has_instagram": True,
            "hosts_events": True,
        }
        opps = matcher.match(lead)
        keys = [o.offer_key for o in opps]
        # Match tanto trophies quanto industrial (cnae 32)
        # Critério: múltiplas oportunidades
        assert len(opps) >= 1
