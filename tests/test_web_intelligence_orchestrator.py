"""Hook public_web_facts no orquestrador: FACTs → evidence/technical_data.

RED (TDD): o step `public_web_facts` declarado pela oferta, com
`PUBLIC_WEB_ENABLED=True`, persiste FACTs em
`Enrichment.raw_technical_data['web_facts']` + entradas `Lead.evidence`
APÓS `_persist_scoring` (que sobrescreve evidence). Ofertas sem o step e
flag desligada mantêm comportamento idêntico ao anterior.
"""
from __future__ import annotations

from types import SimpleNamespace


def _lead(evidence=None):
    return SimpleNamespace(
        website="https://emp.example/",
        company_name="Emp",
        evidence=list(evidence or []),
        enrichment_timestamps={},
    )


def _enrichment():
    return SimpleNamespace(raw_technical_data={"overall_status": "OK"})


def _facts_result():
    return {
        "facts": {
            "site_reachable": True,
            "page_title": "Emp",
            "meta_description": "Usinagem.",
            "contact_page": "https://emp.example/contato",
            "source_url": "https://emp.example/",
            "kind": "FACT",
        },
        "provenance": {
            "source": "public_web",
            "source_url": "https://emp.example/",
            "observed_at": "2026-09-15T00:00:00+00:00",
            "provider": "public_web",
            "capability": "website_facts",
            "kind": "FACT",
        },
    }


def test_step_registrado_no_capability_registry():
    from services.enrichment_capability_registry import (
        CAPABILITIES, ENRICHMENT_STEP_KEYS, STEP_PUBLIC_WEB_FACTS,
    )

    assert STEP_PUBLIC_WEB_FACTS in ENRICHMENT_STEP_KEYS
    assert CAPABILITIES[STEP_PUBLIC_WEB_FACTS]["requires"] == ["has_website"]


def test_ofertas_existentes_nao_incluem_o_step():
    from services.enrichment_capability_registry import resolve_enrichment_steps

    steps = resolve_enrichment_steps({"enrichment_steps": ["technical_site", "cnpj_receita"]})
    assert "public_web_facts" not in steps


def test_hook_persiste_facts_e_evidence(monkeypatch):
    import services.enrichment_orchestrator as orch

    monkeypatch.setattr(orch.settings, "PUBLIC_WEB_ENABLED", True)

    class _Svc:
        def __init__(self, **kwargs):
            pass

        async def enrich_one(self, candidate):
            assert candidate["website"] == "https://emp.example/"
            return _facts_result()

    monkeypatch.setattr(orch, "PublicWebIntelligenceService", _Svc)

    import asyncio

    lead, enrichment = _lead(), _enrichment()
    asyncio.run(orch._enrich_public_web_facts(lead, enrichment))
    asyncio.run(orch._enrich_public_web_facts(lead, enrichment))
    assert enrichment.raw_technical_data["web_facts"]["facts"]["page_title"] == "Emp"
    assert enrichment.raw_technical_data["overall_status"] == "OK"
    sources = {e["source"] for e in lead.evidence}
    assert sources == {"https://emp.example/"}
    assert len(lead.evidence) == 3
    assert len({(e["title"], e["source"]) for e in lead.evidence}) == 3
    assert all(e["type"] == "web_fact" and e["kind"] == "FACT" for e in lead.evidence)
    assert all(e["provider"] == "public_web" for e in lead.evidence)
    assert all(e["capability"] == "website_facts" for e in lead.evidence)
    assert all(e["observed_at"] == "2026-09-15T00:00:00+00:00" for e in lead.evidence)
    assert lead.enrichment_timestamps.get("public_web")


def test_hook_desligado_nao_faz_nada(monkeypatch):
    import services.enrichment_orchestrator as orch

    monkeypatch.setattr(orch.settings, "PUBLIC_WEB_ENABLED", False)

    async def _fail(candidate):
        raise AssertionError("não deve buscar com flag desligada")

    class _Svc:
        def __init__(self, **kwargs):
            pass

        enrich_one = staticmethod(_fail)

    monkeypatch.setattr(orch, "PublicWebIntelligenceService", _Svc)

    import asyncio

    lead, enrichment = _lead(), _enrichment()
    asyncio.run(orch._enrich_public_web_facts(lead, enrichment))
    assert enrichment.raw_technical_data == {"overall_status": "OK"}
    assert lead.evidence == []


def test_hook_sem_website_nao_busca(monkeypatch):
    import services.enrichment_orchestrator as orch

    monkeypatch.setattr(orch.settings, "PUBLIC_WEB_ENABLED", True)

    class _Svc:
        def __init__(self, **kwargs):
            pass

        async def enrich_one(self, candidate):
            raise AssertionError("sem website não deve buscar")

    monkeypatch.setattr(orch, "PublicWebIntelligenceService", _Svc)

    import asyncio

    lead = _lead()
    lead.website = None
    asyncio.run(orch._enrich_public_web_facts(lead, _enrichment()))
    assert lead.evidence == []


def test_hook_com_falha_nao_carimba_freshness(monkeypatch):
    import asyncio
    import services.enrichment_orchestrator as orch

    monkeypatch.setattr(orch.settings, "PUBLIC_WEB_ENABLED", True)

    class _Svc:
        def __init__(self, **kwargs):
            pass

        async def enrich_one(self, candidate):
            return {
                "facts": {
                    "site_reachable": "unknown",
                    "fetch_status": "failed",
                    "fetch_reason": "timeout",
                    "kind": "FACT",
                },
                "provenance": {
                    "source": "public_web",
                    "source_url": candidate["website"],
                    "provider": "public_web_intelligence",
                    "capability": "website_facts",
                    "kind": "FACT",
                },
                "evidence": [],
            }

    monkeypatch.setattr(orch, "PublicWebIntelligenceService", _Svc)
    lead, enrichment = _lead(), _enrichment()
    asyncio.run(orch._enrich_public_web_facts(lead, enrichment))
    assert enrichment.raw_technical_data["web_facts"]["facts"]["site_reachable"] == "unknown"
    assert lead.enrichment_timestamps == {}


def test_hook_com_falha_preserva_evidencia_web_anterior(monkeypatch):
    import asyncio
    import services.enrichment_orchestrator as orch

    monkeypatch.setattr(orch.settings, "PUBLIC_WEB_ENABLED", True)

    class _Svc:
        def __init__(self, **kwargs):
            pass

        async def enrich_one(self, candidate):
            return {
                "facts": {"site_reachable": "unknown", "fetch_status": "failed", "kind": "FACT"},
                "provenance": {
                    "source": "public_web",
                    "source_url": candidate["website"],
                    "provider": "public_web_intelligence",
                    "capability": "website_facts",
                    "kind": "FACT",
                },
                "evidence": [],
            }

    monkeypatch.setattr(orch, "PublicWebIntelligenceService", _Svc)
    previous = [{"type": "web_fact", "source": "https://emp.example/", "title": "Título anterior"}]
    lead, enrichment = _lead(evidence=previous), _enrichment()
    asyncio.run(orch._enrich_public_web_facts(lead, enrichment))
    assert lead.evidence == previous
    assert lead.enrichment_timestamps == {}


def test_hook_com_falha_preserva_snapshot_web_anterior(monkeypatch):
    import asyncio
    import services.enrichment_orchestrator as orch

    monkeypatch.setattr(orch.settings, "PUBLIC_WEB_ENABLED", True)

    class _Svc:
        def __init__(self, **kwargs):
            pass

        async def enrich_one(self, candidate):
            return {
                "facts": {
                    "site_reachable": "unknown",
                    "fetch_status": "failed",
                    "fetch_reason": "network_error",
                    "kind": "FACT",
                },
                "provenance": {
                    "source": "public_web",
                    "source_url": candidate["website"],
                    "provider": "public_web_intelligence",
                    "capability": "website_facts",
                    "kind": "FACT",
                },
                "evidence": [],
            }

    monkeypatch.setattr(orch, "PublicWebIntelligenceService", _Svc)
    previous_web_facts = {
        "facts": {
            "site_reachable": True,
            "fetch_status": "ok",
            "page_title": "Snapshot anterior",
        },
        "provenance": {
            "source": "public_web",
            "source_url": "https://emp.example/",
            "observed_at": "2026-09-15T00:00:00+00:00",
        },
    }
    lead = _lead(evidence=[{"type": "web_fact", "title": "Snapshot anterior"}])
    enrichment = SimpleNamespace(
        raw_technical_data={"web_facts": previous_web_facts},
    )

    asyncio.run(orch._enrich_public_web_facts(lead, enrichment))

    assert enrichment.raw_technical_data["web_facts"] == previous_web_facts
    assert lead.enrichment_timestamps == {}
    assert enrichment.raw_technical_data["web_facts"]["facts"]["site_reachable"] is True
