"""Regressões do contrato free-first da descoberta de pessoas (Fases 1F/1G)."""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.prospecting.people_provider_registry import PeopleProviderRegistry  # noqa: E402
from services.prospecting.website_people_provider import WebsitePeopleProvider  # noqa: E402


class _PaidProvider:
    name = "paid"
    cost = 1.0

    def __init__(self):
        self.called = False

    async def search(self, domain, titles):
        self.called = True
        return [{"name": "Pessoa Paga", "confidence": 90, "email": "paga@example.com"}]


class _FreeProvider:
    name = "free"
    cost = 0.0

    def __init__(self):
        self.called = False

    async def search(self, domain, titles):
        self.called = True
        return [{"name": "Pessoa Gratuita", "confidence": 95, "email": "gratis@example.com"}]


def test_site_publico_declara_custo_financeiro_zero():
    assert WebsitePeopleProvider.cost == 0.0


def test_budget_zero_executa_free_e_bloqueia_paid():
    free = _FreeProvider()
    paid = _PaidProvider()
    registry = PeopleProviderRegistry([paid, free])

    result = asyncio.run(registry.waterfall_search(
        "example.com",
        [],
        max_cost=0.0,
        min_contact_confidence=70,
    ))

    assert free.called is True
    assert paid.called is False
    assert result["status"] == "success"
    assert result["cost_spent"] == 0.0
    assert result["people"][0]["email"] == "gratis@example.com"


def test_budget_zero_sem_resultado_free_nao_consulta_paid():
    class _EmptyFree:
        name = "free"
        cost = 0.0

        async def search(self, domain, titles):
            return []

    paid = _PaidProvider()
    registry = PeopleProviderRegistry([paid, _EmptyFree()])
    result = asyncio.run(registry.waterfall_search("example.com", [], max_cost=0.0))

    assert paid.called is False
    assert result["cost_spent"] == 0.0
    assert any(
        attempt["provider"] == "paid" and attempt["status"] == "budget_exceeded"
        for attempt in result["attempts"]
    )
