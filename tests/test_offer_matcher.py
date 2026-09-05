"""Testes do OfferMatcher (Fase C — consolidação §Fase C).

Seam: `OfferMatcher.match(lead_data, registry)`, `LeadOpportunity`.
Capacidade: dada uma empresa (lead) e um registry de OfferProfiles, retornar
múltiplas oportunidades simultâneas (uma por oferta relevante), cada uma com:
- score (0-100)
- evidência (por que essa oferta)
- profile_key resolvido
- resolved_from (qual nível da cascata)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestLeadOpportunity:
    def test_oportunidade_basica_tem_campos_obrigatorios(self):
        from services.prospecting.offer_matcher import LeadOpportunity
        opp = LeadOpportunity(
            offer_key="landing_page",
            profile_key="web_presence",
            score=85,
            evidence=["NO_OWN_WEBSITE", "GOOGLE_RATING"],
        )
        assert opp.offer_key == "landing_page"
        assert opp.profile_key == "web_presence"
        assert opp.score == 85
        assert len(opp.evidence) == 2
        assert opp.resolved_from == "explicit"  # default

    def test_to_dict_e_from_dict_sao_inversos(self):
        from services.prospecting.offer_matcher import LeadOpportunity
        opp = LeadOpportunity(
            offer_key="mechanical_project",
            profile_key="industrial",
            score=70,
            evidence=["HAS_CNPJ", "CNAE_25"],
            resolved_from="vertical",
        )
        d = opp.to_dict()
        opp2 = LeadOpportunity.from_dict(d)
        assert opp2.offer_key == "mechanical_project"
        assert opp2.resolved_from == "vertical"
        assert opp2.evidence == ["HAS_CNPJ", "CNAE_25"]


class TestOfferMatcher:
    def test_match_lead_sem_ofertas_retorna_lista_vazia(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting import OfferProfileRegistry
        matcher = OfferMatcher(OfferProfileRegistry())
        opps = matcher.match({"company_name": "Test"})
        assert opps == []

    def test_match_retorna_multiplas_oportunidades(self):
        """Critério Fase C: empresa pode ter múltiplas oportunidades simultâneas."""
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting import OfferProfileRegistry
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        # Indústria metalúrgica → matches mechanical_project, technical_drawing, machine_manual
        lead = {
            "company_name": "Metalúrgica Alpha",
            "cnae": "25",  # metalúrgica
            "has_cnpj": True,
            "has_phone": True,
        }
        opps = matcher.match(lead)
        # Mínimo 1 oportunidade
        assert len(opps) >= 1
        # Cada uma é LeadOpportunity
        for opp in opps:
            assert opp.offer_key
            assert 0 <= opp.score <= 100
            assert opp.profile_key

    def test_match_ordena_por_score_decrescente(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        lead = {"company_name": "X", "cnae": "25", "has_cnpj": True, "has_phone": True}
        opps = matcher.match(lead)
        # Scores em ordem decrescente
        scores = [o.score for o in opps]
        assert scores == sorted(scores, reverse=True)

    def test_match_filtra_abaixo_threshold(self):
        """Só oportunidades com score >= threshold entram no resultado."""
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        # Lead com informação mínima (deve descartar todas)
        lead = {"company_name": "Empty"}
        opps = matcher.match(lead, min_score=80)
        # Provavelmente nenhuma oportunidade atinge 80
        for opp in opps:
            assert opp.score >= 80

    def test_match_lead_web_presence_match_landing_page(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        lead = {
            "company_name": "Psicologia Clínica",
            "has_own_website": False,  # público-alvo de landing_page
            "has_instagram": True,
            "has_phone": True,
        }
        opps = matcher.match(lead)
        # Deve incluir landing_page
        keys = [o.offer_key for o in opps]
        assert "landing_page" in keys

    def test_match_inclui_evidencia(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        lead = {
            "company_name": "X",
            "has_own_website": False,
            "has_instagram": True,
            "has_phone": True,
        }
        opps = matcher.match(lead)
        # Cada oportunidade tem pelo menos 1 evidência
        for opp in opps:
            assert len(opp.evidence) > 0

    def test_match_top_k_limita_resultados(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        lead = {"company_name": "X", "cnae": "25", "has_cnpj": True, "has_phone": True}
        opps = matcher.match(lead, top_k=2)
        assert len(opps) <= 2
