"""Suíte de avanços da Onda 1 + Next Best Action + Waterfall de Pessoas.

Testes para:
1. `NextBestActionService` — calcula próxima ação recomendada para o lead.
2. `PeopleProviderRegistry` — waterfall de descoberta de pessoas com early stopping.
3. `Lead.opportunities` expandido no DTO do endpoint da API.
"""
import sys
import asyncio
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKERS_SRC = REPO_ROOT / "services" / "workers" / "src"
API_PARENT = REPO_ROOT / "services" / "api"

for p in (WORKERS_SRC, API_PARENT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


class TestNextBestActionService:
    def test_recomenda_acao_com_base_em_status_e_oportunidades(self):
        from services.prospecting.next_best_action_service import NextBestActionService

        lead_data = {
            "status": "QUALIFICADO",
            "score": 85,
            "routable": True,
            "has_primary_contact": True,
            "has_verified_email": True,
            "opportunities": [
                {"offer_key": "mechanical_project", "score": 88},
            ],
        }
        action = NextBestActionService().recommend(lead_data)
        assert action["action"] == "START_EMAIL_CADENCE"
        assert action["priority"] in ("HIGH", "MEDIUM")
        assert "offer_key" in action
        assert action["offer_key"] == "mechanical_project"

    def test_recomenda_revisao_quando_contato_ambiguo(self):
        from services.prospecting.next_best_action_service import NextBestActionService

        lead_data = {
            "status": "ANALISADO",
            "score": 75,
            "verification_status": "needs_review",
            "has_primary_contact": False,
            "opportunities": [],
        }
        action = NextBestActionService().recommend(lead_data)
        assert action["action"] == "REVIEW_DECISION_MAKER"
        assert action["priority"] == "HIGH"


class TestNextBestActionRoutability:
    """A ação distingue a roteabilidade persistida (P1.39)."""

    def test_direct_contact_liga_com_confianca_maior(self):
        from services.prospecting.next_best_action_service import NextBestActionService

        action = NextBestActionService().recommend({
            "status": "QUALIFICADO",
            "routability_type": "DIRECT_CONTACT",
            "phone": "+5511987654321",
        })
        assert action["action"] == "CALL"
        assert action["why"] == "direct_phone_contact"

    def test_routable_contact_pabx_liga_com_target_person(self):
        from services.prospecting.next_best_action_service import NextBestActionService

        action = NextBestActionService().recommend({
            "status": "ANALISADO",
            "routability_type": "ROUTABLE_CONTACT",
            "phone": "+551130001000",
        })
        assert action["action"] == "CALL"
        assert action["why"] == "pabx_with_target_person"

    def test_institutional_sugere_acao_humana_pela_recepcao(self):
        """Telefone genérico não bloqueia ação humana: vira RESEARCH."""
        from services.prospecting.next_best_action_service import NextBestActionService

        action = NextBestActionService().recommend({
            "status": "ANALISADO",
            "routability_type": "INSTITUTIONAL",
            "phone": "3456",
        })
        assert action["action"] == "RESEARCH"
        assert action["why"] == "institutional_phone_requires_reception"

    def test_unknown_unreachable_enriquece_novamente(self):
        from services.prospecting.next_best_action_service import NextBestActionService

        for routability in ("UNKNOWN", "UNREACHABLE"):
            action = NextBestActionService().recommend({
                "status": "ANALISADO",
                "routability_type": routability,
            })
            assert action["action"] == "RE_ENRICH"
            assert action["why"] == "contact_unreachable"

    def test_legado_sem_classificacao_mantem_comportamento(self):
        from services.prospecting.next_best_action_service import NextBestActionService

        action = NextBestActionService().recommend({
            "status": "ANALISADO",
            "routable": True,
            "phone": "+5511999998888",
        })
        assert action["action"] == "CALL"
        assert action["why"] == "routable_phone_contact"


class TestPeopleProviderRegistryWaterfall:
    def test_waterfall_para_no_early_stopping(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        calls = []

        class FastProvider:
            name = "fast_cheap"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{
                    "name": "João Engenheiro",
                    "email": "joao@empresa.com.br",
                    "confidence": 90,
                    "verified": True,
                }]

        class ExpensiveProvider:
            name = "expensive"
            cost = 10

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{"name": "Ignorado"}]

        registry = PeopleProviderRegistry()
        registry.register(FastProvider())
        registry.register(ExpensiveProvider())

        result = asyncio.run(registry.waterfall_search(
            domain="empresa.com.br",
            titles=["plant_engineer"],
            min_contact_confidence=80,
            require_verified_email=True,
        ))

        assert len(result["people"]) == 1
        assert result["people"][0]["name"] == "João Engenheiro"
        assert calls == ["fast_cheap"]  # Parou no primeiro que atendeu o critério!
        assert result["early_stopped"] is True

    def test_deduplica_pessoa_e_preserva_provenance(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "provider"
            cost = 1

            async def search(self, domain, titles):
                return [
                    {"name": "Ana Silva", "email": "ana@empresa.com", "confidence": 60},
                    {"name": "Ana Silva", "email": "ana@empresa.com", "phone": "+5511", "confidence": 80},
                ]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search("empresa.com", ["CEO"]))

        assert len(result["people"]) == 1
        assert result["people"][0]["phone"] == "+5511"
        assert result["people"][0]["confidence"] == 80
        assert result["people"][0]["sources"] == ["provider"]

    def test_falha_de_provider_nao_vira_lista_vazia_silenciosa(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class BrokenProvider:
            name = "broken"
            cost = 1

            async def search(self, domain, titles):
                raise TimeoutError("provider timeout")

        result = asyncio.run(PeopleProviderRegistry([BrokenProvider()]).waterfall_search("empresa.com", ["CEO"]))

        assert result["people"] == []
        assert result["status"] == "failed"
        assert result["attempts"] == [{
            "provider": "broken",
            "status": "failed",
            "result_count": 0,
            "error": "provider timeout",
        }]

    def test_continua_apos_provider_vazio_e_retorna_status_observavel(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class EmptyProvider:
            name = "empty"
            cost = 1

            async def search(self, domain, titles):
                return []

        class FallbackProvider:
            name = "fallback"
            cost = 2

            async def search(self, domain, titles):
                return [{"name": "Maria Souza", "confidence": 40}]

        result = asyncio.run(PeopleProviderRegistry([EmptyProvider(), FallbackProvider()]).waterfall_search(
            "empresa.com", ["CEO"], min_contact_confidence=80,
        ))

        assert result["status"] == "success"
        assert result["providers_attempted"] == ["empty", "fallback"]
        assert result["attempts"][0]["status"] == "empty"

    def test_sem_provider_fica_desabilitado(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        result = asyncio.run(PeopleProviderRegistry().waterfall_search("empresa.com", ["CEO"]))

        assert result["status"] == "disabled"
        assert result["providers_attempted"] == []

    def test_preserva_quota_excedida_no_status_agregado(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class QuotaProvider:
            name = "quota"
            cost = 1

            async def search(self, domain, titles):
                from services.prospecting.hunter_people_provider import HunterProviderError
                raise HunterProviderError("quota_exceeded", "cota esgotada")

        result = asyncio.run(PeopleProviderRegistry([QuotaProvider()]).waterfall_search("empresa.com", ["CEO"]))

        assert result["status"] == "quota_exceeded"
        assert result["attempts"][0]["status"] == "quota_exceeded"


class TestPeopleProviderRegistryMaxCost:
    """Early stopping por orçamento (P1.36) com custo observável."""

    def test_max_cost_bloqueia_provider_fora_do_orcamento(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        calls = []

        class CheapProvider:
            name = "cheap"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return []

        class ExpensiveProvider:
            name = "expensive"
            cost = 10

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{"name": "Caro", "confidence": 90}]

        result = asyncio.run(PeopleProviderRegistry([CheapProvider(), ExpensiveProvider()]).waterfall_search(
            "empresa.com", ["CEO"], max_cost=2,
        ))

        assert calls == ["cheap"]  # caro nunca foi consultado
        assert result["status"] == "budget_exceeded"
        assert result["cost_spent"] == 1
        assert result["attempts"][1]["status"] == "budget_exceeded"
        assert result["attempts"][1]["error"] == "max_cost_reached"

    def test_max_cost_interrompe_cascata_com_orcamento_gasto(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class MidProvider:
            name = "mid"
            cost = 2

            async def search(self, domain, titles):
                return []

        class NextProvider:
            name = "next"
            cost = 3

            async def search(self, domain, titles):
                return [{"name": "X", "confidence": 90}]

        result = asyncio.run(PeopleProviderRegistry([MidProvider(), NextProvider()]).waterfall_search(
            "empresa.com", ["CEO"], max_cost=4,
        ))

        assert result["status"] == "budget_exceeded"
        assert result["cost_spent"] == 2
        assert result["providers_attempted"] == ["mid", "next"]  # next bloqueado na tentativa

    def test_sem_max_cost_comportamento_inalterado(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "p"
            cost = 5

            async def search(self, domain, titles):
                return [{"name": "Maria", "confidence": 90}]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search("empresa.com", ["CEO"]))

        assert result["status"] == "success"
        assert result["cost_spent"] == 5

    def test_disabled_tem_custo_zero(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        result = asyncio.run(PeopleProviderRegistry().waterfall_search("empresa.com", ["CEO"]))

        assert result["status"] == "disabled"
        assert result["cost_spent"] == 0


class TestPeopleProviderRegistryRoleFit:
    """Role fit configurável sem transformar cargo desejado em pessoa."""

    def test_role_fit_exato_permite_early_stopping(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        calls = []

        class Provider:
            name = "people"
            cost = 1

            async def search(self, domain, titles):
                calls.append(list(titles))
                return [{
                    "name": "Ana",
                    "title": "Engineering Manager",
                    "confidence": 85,
                    "verified": True,
                }]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search(
            "empresa.com", ["engineering_manager"],
            min_contact_confidence=80,
            require_verified_email=True,
            min_role_fit=70,
        ))

        assert calls == [["engineering_manager"]]
        assert result["early_stopped"] is True
        assert result["people"][0]["role_fit_score"] >= 70
        assert result["people"][0]["role_fit_status"] == "matched"
        assert result["people"][0]["matched_titles"] == ["engineering_manager"]

    def test_role_fit_incompativel_continua_cascata(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        calls = []

        class FirstProvider:
            name = "first"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{"name": "Ana", "title": "Finance Manager", "confidence": 95}]

        class FallbackProvider:
            name = "fallback"
            cost = 2

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{"name": "Bruno", "role": "plant engineer", "confidence": 80}]

        result = asyncio.run(PeopleProviderRegistry([FirstProvider(), FallbackProvider()]).waterfall_search(
            "empresa.com", ["plant_engineer"],
            min_contact_confidence=70,
            min_role_fit=70,
        ))

        assert calls == ["first", "fallback"]
        assert result["status"] == "success"
        assert result["early_stopped"] is True
        assert result["people"][0]["role_fit_status"] == "not_matched"

    def test_somente_cargos_incompativeis_retorna_status_explicito(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "people"
            cost = 1

            async def search(self, domain, titles):
                return [{"name": "Ana", "title": "Finance Manager", "confidence": 95}]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search(
            "empresa.com", ["plant_engineer"], min_role_fit=70,
        ))

        assert result["status"] == "role_not_matched"
        assert result["role_fit"] == {"matched": 0, "not_matched": 1, "unknown": 0}

    def test_dedup_preserva_melhor_role_fit_entre_providers(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class FirstProvider:
            name = "first"
            cost = 1

            async def search(self, domain, titles):
                return [{"name": "Ana", "email": "ana@empresa.com", "title": "Manager", "confidence": 80}]

        class SecondProvider:
            name = "second"
            cost = 2

            async def search(self, domain, titles):
                return [{"name": "Ana", "email": "ana@empresa.com", "title": "Engineering Manager", "confidence": 70}]

        result = asyncio.run(PeopleProviderRegistry([FirstProvider(), SecondProvider()]).waterfall_search(
            "empresa.com", ["engineering_manager"], min_role_fit=70,
        ))

        assert len(result["people"]) == 1
        assert result["people"][0]["role_fit_score"] == 100
        assert result["people"][0]["role_fit_status"] == "matched"
        assert result["role_fit"]["matched"] == 1

    def test_sem_cargo_fica_unknown_e_nao_e_promovido(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "people"
            cost = 1

            async def search(self, domain, titles):
                return [{"name": "Sem cargo", "confidence": 95}]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search(
            "empresa.com", ["ceo"], min_role_fit=70,
        ))

        assert result["early_stopped"] is False
        assert result["people"][0]["role_fit_score"] == 0
        assert result["people"][0]["role_fit_status"] == "unknown"

    def test_role_label_do_hunter_e_considerado_no_fit(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "hunter"
            cost = 1

            async def search(self, domain, titles):
                return [{
                    "name": "João",
                    "role_label": "Engineering Manager",
                    "confidence": 90,
                    "verified": True,
                }]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search(
            "empresa.com", ["engineering_manager"],
            min_contact_confidence=80,
            require_verified_email=True,
            min_role_fit=70,
        ))

        assert result["early_stopped"] is True
        assert result["people"][0]["role_fit_status"] == "matched"

    def test_role_fit_clasifica_senioridade_e_departamento(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "people"
            cost = 1

            async def search(self, domain, titles):
                return [
                    {"name": "Ana", "title": "Senior Engineering Manager", "confidence": 90},
                    {"name": "Bruno", "title": "Finance Director", "confidence": 90},
                    {"name": "Carla", "title": "Junior Developer", "confidence": 90},
                ]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search(
            "empresa.com", ["engineering_manager"],
        ))
        people = {item["name"]: item for item in result["people"]}

        assert people["Ana"]["role_seniority"] == "senior"
        assert people["Ana"]["role_department"] == "engineering"
        assert people["Bruno"]["role_seniority"] == "executive"
        assert people["Bruno"]["role_department"] == "finance"
        assert people["Carla"]["role_seniority"] == "junior"
        assert people["Carla"]["role_department"] == "engineering"
        assert result["role_filters"]["requested"] is False
        assert all(item["role_filter_status"] == "not_requested" for item in people.values())

    def test_filtro_de_senioridade_continua_cascata(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        calls = []

        class JuniorProvider:
            name = "junior"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{"name": "Ana", "title": "Junior Engineer", "confidence": 90}]

        class MiddleProvider:
            name = "middle"
            cost = 2

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{"name": "Beatriz", "title": "Lead Engineer", "confidence": 90}]

        class SeniorProvider:
            name = "senior"
            cost = 3

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{"name": "Bruno", "title": "Senior Engineer", "confidence": 80}]

        result = asyncio.run(PeopleProviderRegistry(
            [JuniorProvider(), MiddleProvider(), SeniorProvider()],
        ).waterfall_search(
            "empresa.com", ["engineer"], seniority="senior",
        ))

        assert calls == ["junior", "middle", "senior"]
        assert result["status"] == "success"
        assert result["early_stopped"] is True
        assert result["people"][-1]["role_seniority"] == "senior"

    def test_filtros_de_role_fit_sao_expostos_no_resultado(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "people"
            cost = 1

            async def search(self, domain, titles):
                return [
                    {"name": "Ana", "title": "Senior Engineer", "confidence": 90},
                    {"name": "Bruno", "title": "Finance Director", "confidence": 90},
                ]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search(
            "empresa.com", ["engineer"],
            seniority=["senior"], department=["engineering"],
        ))

        assert result["role_filters"] == {
            "seniority": ["senior"],
            "department": ["engineering"],
            "requested": True,
            "matched": 1,
            "not_matched": 1,
        }
        assert result["people"][0]["role_filter_status"] == "matched"
        assert result["people"][1]["role_filter_status"] == "not_matched"



class TestPeopleDiscoveryProfileConfig:
    """Configuração de descoberta vem do OfferProfile sem habilitar provider."""

    def test_configura_limites_de_discovery_do_profile(self):
        from services.contact_enrichment_service import ContactEnrichmentService

        config = ContactEnrichmentService.discovery_limits({
            "enrichment": {
                "max_cost": 4,
                "max_steps": 2,
                "min_role_fit": 75,
                "seniority": ["Senior", "Executive"],
                "department": "Engineering",
            },
        })

        assert config == {
            "max_cost": 4.0,
            "max_steps": 2,
            "min_role_fit": 75.0,
            "seniority": ["senior", "executive"],
            "department": ["engineering"],
        }

    def test_configuracao_invalida_usa_none_sem_quebrar_legado(self):
        from services.contact_enrichment_service import ContactEnrichmentService

        config = ContactEnrichmentService.discovery_limits({
            "enrichment": {"max_cost": "x", "max_steps": 0, "min_role_fit": 101},
        })

        assert config == {
            "max_cost": None,
            "max_steps": None,
            "min_role_fit": None,
            "seniority": [],
            "department": [],
        }

    def test_profile_vazio_nao_habilita_limites_externos(self):
        from services.contact_enrichment_service import ContactEnrichmentService

        assert ContactEnrichmentService.discovery_limits({}) == {
            "max_cost": None,
            "max_steps": None,
            "min_role_fit": None,
            "seniority": [],
            "department": [],
        }

    def test_perfis_padrao_declaram_role_fit_e_limites(self):
        from services.contact_enrichment_service import ContactEnrichmentService
        from services.prospecting.default_profiles import get_default_registry

        for profile in get_default_registry().list():
            config = ContactEnrichmentService.discovery_limits(profile.to_dict())
            if profile.decision_makers.get("roles"):
                assert config["min_role_fit"] == 70.0
                assert config["max_steps"] == 2

    def test_landing_page_reserva_orcamento_para_fallback_de_site(self):
        from services.contact_enrichment_service import ContactEnrichmentService
        from services.prospecting.default_profiles import get_default_registry

        profile = get_default_registry().get("landing_page")

        assert ContactEnrichmentService.discovery_limits(profile.to_dict()) == {
            "max_cost": 2.0,
            "max_steps": 2,
            "min_role_fit": 70.0,
            "seniority": [],
            "department": [],
        }

    def test_sem_min_role_fit_mantem_contrato_legado(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "people"
            cost = 1

            async def search(self, domain, titles):
                return [{"name": "Pessoa", "confidence": 90}]

        result = asyncio.run(PeopleProviderRegistry([Provider()]).waterfall_search(
            "empresa.com", ["ceo"], min_contact_confidence=80,
        ))

        assert result["early_stopped"] is True
        assert result["people"][0]["role_fit_status"] == "unknown"

    def test_waterfall_prioriza_site_barato_e_para_com_role_fit(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry
        from services.prospecting.website_people_provider import WebsitePeopleProvider

        class HunterEmpty:
            name = "hunter"
            cost = 1

            async def search(self, domain, titles):
                return []

        html = """
        <script type="application/ld+json">
        {"@type":"Person","name":"Carla","jobTitle":"Marketing Manager",
         "email":"carla@empresa.com.br"}
        </script>
        """

        async def request(**kwargs):
            return httpx.Response(
                200,
                text=html,
                request=httpx.Request("GET", kwargs["url"]),
            )

        registry = PeopleProviderRegistry([
            HunterEmpty(),
            WebsitePeopleProvider(request=request, max_pages=1),
        ])
        result = asyncio.run(registry.waterfall_search(
            "empresa.com.br", ["marketing_manager"],
            min_contact_confidence=70,
            min_role_fit=70,
            max_cost=2,
        ))

        assert result["providers_attempted"] == ["website_people"]
        assert result["early_stopped"] is True
        assert result["people"][0]["role_fit_status"] == "matched"

    def test_waterfall_faz_fallback_para_hunter_quando_site_vazio(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry
        from services.prospecting.website_people_provider import WebsitePeopleProvider

        class HunterProvider:
            name = "hunter"
            cost = 1

            async def search(self, domain, titles):
                return [{
                    "name": "Diego",
                    "title": "CEO",
                    "email": "diego@empresa.com.br",
                    "confidence": 85,
                    "verified": True,
                }]

        async def empty_site(**kwargs):
            return httpx.Response(
                200,
                text="<html><body>Sem pessoas</body></html>",
                request=httpx.Request("GET", kwargs["url"]),
            )

        registry = PeopleProviderRegistry([
            HunterProvider(),
            WebsitePeopleProvider(request=empty_site, max_pages=1),
        ])
        result = asyncio.run(registry.waterfall_search(
            "empresa.com.br", ["ceo"],
            min_contact_confidence=80,
            require_verified_email=True,
            min_role_fit=70,
            max_cost=2,
        ))

        assert result["providers_attempted"] == ["website_people", "hunter"]
        assert result["early_stopped"] is True
        assert result["people"][0]["source"] == "hunter"
