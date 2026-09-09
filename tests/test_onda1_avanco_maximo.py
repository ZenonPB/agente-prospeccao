"""Suíte de avanços da Onda 1 + Next Best Action + Waterfall de Pessoas.

Testes para:
1. `NextBestActionService` — calcula próxima ação recomendada para o lead.
2. `PeopleProviderRegistry` — waterfall de descoberta de pessoas com early stopping.
3. `Lead.opportunities` expandido no DTO do endpoint da API.
"""
import sys
import asyncio
from pathlib import Path

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
