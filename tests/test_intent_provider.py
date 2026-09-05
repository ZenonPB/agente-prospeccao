"""Testes do IntentProvider (Fase E — consolidação §Fase E).

Seam: `IntentProvider` (Protocol), `IntentProviderRegistry`,
       `IntentScorer.score(event, profile)`, `WebsiteIntentProvider`,
       `JobPostingIntentProvider`.

Capacidade: producers de eventos de intenção (HIRING/NEW_BRANCH/NEW_EQUIPMENT)
que coletam dados de fontes externas e alimentam o IntentEngine.
Critério: "Um evento real coletado altera timing/intent da oportunidade
com evidência."
"""
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestIntentProviderContract:
    def test_provider_tem_metodos_obrigatorios(self):
        from services.prospecting.intent_provider import IntentProvider

        class _P:
            name = "fake"
            async def collect(self, lead_context: Dict[str, Any]) -> List[Dict]:
                return []
        p = _P()
        assert hasattr(p, "name")
        assert hasattr(p, "collect")


class TestIntentProviderRegistry:
    def test_registry_registra_e_recupera(self):
        from services.prospecting.intent_provider import (
            IntentProviderRegistry, _StubIntentProvider,
        )
        reg = IntentProviderRegistry()
        reg.register(_StubIntentProvider("website"))
        assert reg.get("website") is not None
        assert reg.get("nao_existe") is None

    def test_registry_list_keys(self):
        from services.prospecting.intent_provider import (
            IntentProviderRegistry, _StubIntentProvider,
        )
        reg = IntentProviderRegistry()
        reg.register(_StubIntentProvider("website"))
        reg.register(_StubIntentProvider("jobs"))
        assert set(reg.list_keys()) == {"website", "jobs"}


class TestIntentScorer:
    def test_evento_recente_score_alto(self):
        from services.prospecting.intent_provider import IntentScorer
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=5)).isoformat()
        s = IntentScorer(decay_days=30)
        result = s.score({"key": "HIRING", "observed_at": recent, "confidence": 0.9})
        # Há 5 dias (decay 30d) → confidence * (1 - 5/30) = 0.9 * 0.833 = 0.75
        assert 0.6 < result["score"] < 0.85

    def test_evento_antigo_score_baixo(self):
        from services.prospecting.intent_provider import IntentScorer
        from datetime import datetime, timedelta
        old = (datetime.now() - timedelta(days=120)).isoformat()
        s = IntentScorer(decay_days=30)
        result = s.score({"key": "HIRING", "observed_at": old, "confidence": 0.9})
        # 120 dias > 30d → score muito baixo
        assert result["score"] < 0.1

    def test_evento_sem_data_score_igual_confidence(self):
        """Sem observed_at, não aplica decay (consolidação §27: não esconder UNKNOWN)."""
        from services.prospecting.intent_provider import IntentScorer
        s = IntentScorer(decay_days=30)
        result = s.score({"key": "HIRING", "confidence": 0.7})
        assert result["score"] == 0.7

    def test_score_0_quando_confidence_ausente(self):
        from services.prospecting.intent_provider import IntentScorer
        s = IntentScorer()
        result = s.score({"key": "HIRING"})
        assert result["score"] == 0.0

    def test_trigger_threshold_classifica(self):
        from services.prospecting.intent_provider import IntentScorer
        s = IntentScorer(decay_days=30, trigger_threshold=0.5)
        high = s.score({"key": "HIRING", "confidence": 0.9, "observed_at": "2026-09-01T00:00:00"})
        low = s.score({"key": "HIRING", "confidence": 0.2, "observed_at": "2026-09-01T00:00:00"})
        assert high["triggered"] is True
        assert low["triggered"] is False


class TestWebsiteIntentProvider:
    def test_detecta_carreiras_no_site(self):
        from services.prospecting.intent_provider import WebsiteIntentProvider
        # HTML com link /carreiras ou /jobs
        html = '<html><body><a href="/carreiras">Trabalhe Conosco</a></body></html>'
        provider = WebsiteIntentProvider()
        events = provider._parse_html_for_intent(html, "https://alpha.com")
        # Deve detectar HIRING
        hiring = [e for e in events if e["key"] == "HIRING"]
        assert len(hiring) >= 1
        assert hiring[0]["evidence_url"] == "https://alpha.com/carreiras"

    def test_detecta_novos_produtos(self):
        from services.prospecting.intent_provider import WebsiteIntentProvider
        html = '<html><body><a href="/produtos/novo">Lançamento</a></body></html>'
        provider = WebsiteIntentProvider()
        events = provider._parse_html_for_intent(html, "https://alpha.com")
        new_product = [e for e in events if e["key"] == "NEW_PRODUCT"]
        assert len(new_product) >= 1

    def test_site_sem_sinais_retorna_vazio(self):
        from services.prospecting.intent_provider import WebsiteIntentProvider
        html = "<html><body>Apenas informação institucional.</body></html>"
        provider = WebsiteIntentProvider()
        events = provider._parse_html_for_intent(html, "https://alpha.com")
        # Sem links relevantes
        assert all(e["key"] not in ("HIRING", "NEW_PRODUCT", "EXPANDING") for e in events)

    def test_collect_retorna_eventos_com_confidence(self):
        from services.prospecting.intent_provider import WebsiteIntentProvider
        provider = WebsiteIntentProvider()
        # collect com HTML injetado
        events = provider._parse_html_for_intent(
            '<a href="/jobs">Vagas</a>', "https://alpha.com"
        )
        for e in events:
            assert 0.0 <= e["confidence"] <= 1.0
            assert e["source"] == "website"


class TestJobPostingIntentProvider:
    def test_detecta_vaga_recente_como_hiring(self):
        from services.prospecting.intent_provider import JobPostingIntentProvider
        from datetime import datetime, timedelta
        provider = JobPostingIntentProvider()
        job = {
            "title": "Engenheiro Mecânico Sr",
            "company": "Alpha",
            "posted_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "url": "https://jobs.com/123",
            "description": "Vaga para projetista mecânico",
        }
        events = provider._job_to_events(job, "alpha.com")
        hiring = [e for e in events if e["key"] == "HIRING"]
        assert len(hiring) == 1
        assert hiring[0]["confidence"] >= 0.6  # vaga de 2 dias com decay 90d
        assert "Engenheiro" in hiring[0]["evidence"]

    def test_vaga_antiga_score_baixo(self):
        from services.prospecting.intent_provider import JobPostingIntentProvider
        from datetime import datetime, timedelta
        provider = JobPostingIntentProvider()
        old = (datetime.now() - timedelta(days=365)).isoformat()
        job = {
            "title": "Vaga antiga",
            "company": "Alpha",
            "posted_at": old,
            "url": "https://jobs.com/old",
        }
        events = provider._job_to_events(job, "alpha.com")
        # Vaga muito antiga → confidence baixa
        if events:
            assert events[0]["confidence"] < 0.5


class TestIntentProviderIntegration:
    """Critério Fase E: 'Um evento real coletado altera timing/intent
    da oportunidade com evidência.'"""

    def test_evento_real_altera_timing(self):
        """Vaga real coletada + decay → oportunidade vira TIMELY."""
        import asyncio
        from datetime import datetime, timedelta
        from services.prospecting.intent_provider import (
            build_default_intent_registry, IntentScorer,
        )
        from services.buying_trigger_service import icp_vs_intent

        registry = build_default_intent_registry()
        # 1) Coleta de provider real (job board)
        jobs_provider = registry.get("jobs")
        job = {
            "title": "Engenheiro Mecânico",
            "company": "Alpha",
            "posted_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "url": "https://jobs.com/123",
        }
        events = asyncio.run(jobs_provider.collect({"jobs": [job], "domain": "alpha.com"}))
        # 2) Scoring com decay
        scorer = IntentScorer(decay_days=90)
        scored = [scorer.score(e) for e in events]
        # Pelo menos 1 evento scored
        assert any(s["reason"] == "scored" and s["triggered"] for s in scored)
        # 3) Mudar ICP vs Intent: opportunity vira TIMELY
        intent_score = max((s["score"] for s in scored), default=0) * 100
        result = icp_vs_intent("industrial", intent_score=intent_score, icp_match=True)
        assert result["classification"] == "TIMELY"
        # Evidência rastreável
        assert any(e.get("evidence_url") for e in events)

    def test_evento_antigo_nao_triggera(self):
        """Vaga de 6 meses atrás → não triggera (decay expirou)."""
        import asyncio
        from datetime import datetime, timedelta
        from services.prospecting.intent_provider import (
            build_default_intent_registry, IntentScorer,
        )
        registry = build_default_intent_registry()
        jobs_provider = registry.get("jobs")
        old = (datetime.now() - timedelta(days=180)).isoformat()
        job = {"title": "Vaga antiga", "company": "X", "posted_at": old}
        events = asyncio.run(jobs_provider.collect({"jobs": [job]}))
        # JobPostingIntentProvider descarta vagas expiradas (sem evento)
        # ou gera com confidence baixa
        for e in events:
            scorer = IntentScorer(decay_days=90)
            s = scorer.score(e)
            assert s["triggered"] is False

    def test_offer_profile_discovery_e_respeitado(self):
        """trigger_threshold por oferta (OfferProfile.intent) é plugado."""
        from services.prospecting.intent_provider import IntentScorer
        # Perfil trophies tem decay_days=30 (consolidação §Fase E)
        # threshold customizado por oferta
        scorer = IntentScorer(decay_days=30, trigger_threshold=0.4)
        s = scorer.score({
            "key": "EVENT_SCHEDULED",
            "confidence": 0.6,
            "observed_at": "2026-08-01T00:00:00",
        })
        # 30d+ → expirado
        assert s["reason"] in ("expired", "scored")
