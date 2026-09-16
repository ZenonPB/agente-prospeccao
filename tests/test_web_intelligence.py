"""Inteligência web pública (1D): shortlist barato, concorrência, provenance.

RED (TDD): filtro sem-site evita HTTP; shortlist respeita max_candidates;
provenance FACT com observed_at real; timeout vira UNKNOWN; concorrência
limitada; sem DB/transação no serviço.
"""
from __future__ import annotations

import asyncio


def _cand(**kwargs):
    base = {"cnpj": "12345678000195", "place_id": "registry_12345678000195",
            "website": "https://empresa.example"}
    base.update(kwargs)
    return base


def _service(fetch=None, **kwargs):
    from services.prospecting.web_intelligence import PublicWebIntelligenceService

    if fetch is None:
        async def fetch(url):
            return {"status": "ok", "url": url,
                    "text": "<html><head><title>X</title></head></html>"}

    class _FakeClient:
        def __init__(self):
            pass

        async def fetch(self, url):
            return await fetch(url)

    return PublicWebIntelligenceService(
        client_factory=_FakeClient, **kwargs,
    )


def test_candidatos_sem_site_proprio_evitam_http():
    from services.prospecting.web_intelligence import PublicWebIntelligenceService

    svc = _service()
    short = svc.shortlist([
        _cand(website="https://instagram.com/empresa"),
        _cand(website=None),
        _cand(website="https://empresa.example"),
    ])
    assert len(short) == 1
    assert short[0]["website"] == "https://empresa.example"


def test_shortlist_respeita_max_candidates_preservando_ordem():
    svc = _service(max_candidates=2)
    cands = [_cand(cnpj=f"{i:014d}", website="https://empresa.example")
             for i in range(5)]
    short = svc.shortlist(cands)
    assert [c["cnpj"] for c in short] == ["00000000000000", "00000000000001"]


def test_enrich_retorna_stats_economicas():
    async def _run():
        svc = _service(max_candidates=2)
        cands = [_cand(website="https://empresa.example") for _ in range(2)]
        cands.append(_cand(website=None))
        out = await svc.enrich_candidates(cands)
        assert out["stats"]["candidates_before"] == 3
        assert out["stats"]["candidates_after_filter"] == 2
        assert out["stats"]["http_calls"] == 2
        assert out["stats"]["http_avoided"] == 1
        assert out["stats"]["promoted_count"] == 0

    asyncio.run(_run())


def test_provenance_fact_com_observed_at_real():
    from datetime import datetime

    async def _run():
        svc = _service()
        before = datetime.now().astimezone().isoformat()
        out = await svc.enrich_candidates([_cand()])
        (entry,) = out["results"][0]["evidence"]
        assert entry["kind"] == "FACT"
        assert entry["source"] == "public_web"
        assert entry["provider"] == "public_web_intelligence"
        assert entry["capability"] == "website_facts"
        assert entry["source_url"].startswith("https://empresa.example")
        observed = datetime.fromisoformat(entry["observed_at"])
        assert entry["observed_at"] >= before
        assert (datetime.now().astimezone() - observed).total_seconds() < 60

    asyncio.run(_run())


def test_falha_de_fetch_vira_unknown_sem_website_absent():
    async def _fail(url):
        return {"status": "failed", "reason": "timeout"}

    async def _run():
        svc = _service(fetch=_fail)
        out = await svc.enrich_candidates([_cand()])
        facts = out["results"][0]["facts"]
        assert facts["site_reachable"] == "unknown"
        assert "website_absent" not in facts

    asyncio.run(_run())


def test_enrich_one_expoe_facts_e_provenance_para_o_orquestrador():
    async def _run():
        svc = _service()
        out = await svc.enrich_one(_cand())
        assert out["facts"]["page_title"] == "X"
        assert out["provenance"]["kind"] == "FACT"
        assert out["provenance"]["source_url"].startswith("https://empresa.example")

    asyncio.run(_run())


def test_retry_nao_duplica_evidencia_web():
    async def _run():
        svc = _service()
        candidate = _cand()
        first = await svc.enrich_candidates([candidate])
        second = await svc.enrich_candidates([candidate])
        evidences = first["results"][0]["evidence"] + second["results"][0]["evidence"]
        keys = {
            (item["provider"], item["source_url"], item["candidate_ref"]["cnpj"], item["facts"].get("page_title"))
            for item in evidences
        }
        assert len(keys) == len(first["results"][0]["evidence"])

    asyncio.run(_run())


def test_concorrencia_limitada():
    async def _run():
        active = 0
        peak = 0

        async def _slow(url):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {"status": "ok", "url": url, "text": "<html></html>"}

        svc = _service(fetch=_slow, max_concurrency=2, max_candidates=10)
        cands = [_cand(website="https://empresa.example") for _ in range(6)]
        out = await svc.enrich_candidates(cands)
        assert out["stats"]["http_calls"] == 6
        assert peak <= 2

    asyncio.run(_run())


def test_servico_nao_usa_db_nem_transacao():
    import inspect

    from services.prospecting import web_intelligence as mod

    source = inspect.getsource(mod)
    assert "Session" not in source
    assert "commit" not in source
    assert "groq" not in source.lower()
    assert "hunter" not in source.lower()
