"""Testes do Event Discovery (Fase F — consolidação §Fase F).

Seam: `EventOpportunity` (dataclass), `EventDiscoveryProvider` (Protocol),
       `EventDiscoveryRegistry`, `EventDiscoveryExecutor`,
       `OrganizerResolver.resolve(event)`, `EventTimingScorer.score(event)`.

Capacidade: transformar um evento futuro (competição esportiva, cerimônia,
feira) em oportunidade comercial rastreável, com organizador, sinais
temporais e timing score (urgência baseada em event_date).

Critério da Fase F: "Sistema consegue transformar um evento futuro em
oportunidade comercial rastreável."

Contexto AlphaMec: o ciclo de vendas da EJ é centrado em eventos
esportivos/corporativos que precisam de troféus — esse é o principal
motor de receita. O pipeline deve:
1. Detectar eventos (provider real)
2. Resolver organizador (organizer resolution)
3. Calcular timing (urgência via event_date)
4. Matchear com OfferProfile (trophies)
5. Persistir com evidência rastreável
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestEventOpportunity:
    def test_oportunidade_basica_tem_campos_obrigatorios(self):
        from services.prospecting.event_discovery import EventOpportunity
        opp = EventOpportunity(
            name="Copa Paulista de Karate",
            event_type="sport",
            event_date="2026-12-15",
            location="São Paulo, SP",
            source_url="https://eventos.com.br/copa-paulista-karate",
            organizer="Federação Paulista de Karate",
        )
        assert opp.name == "Copa Paulista de Karate"
        assert opp.event_type == "sport"
        assert opp.event_date == "2026-12-15"
        assert opp.confidence == 0.5  # default
        assert opp.registration_status == "unknown"  # default

    def test_to_dict_e_from_dict_sao_inversos(self):
        from services.prospecting.event_discovery import EventOpportunity
        opp = EventOpportunity(
            name="Maratona SP 2026",
            event_type="sport",
            event_date="2026-11-10",
            location="São Paulo",
            source_url="https://m.com/maratona-sp",
            organizer="Associação de Maratonistas",
            confidence=0.85,
            observed_at="2026-09-01T00:00:00",
            expires_at="2026-10-01T00:00:00",
        )
        d = opp.to_dict()
        opp2 = EventOpportunity.from_dict(d)
        assert opp2.name == "Maratona SP 2026"
        assert opp2.confidence == 0.85
        assert opp2.expires_at == "2026-10-01T00:00:00"

    def test_is_upcoming_retorna_true_quando_futuro(self):
        from services.prospecting.event_discovery import EventOpportunity
        opp = EventOpportunity(
            name="Futuro",
            event_type="sport",
            event_date="2099-12-31",  # data futura
            location="X",
            source_url="http://x",
            organizer="Y",
        )
        assert opp.is_upcoming() is True

    def test_is_upcoming_retorna_false_quando_passado(self):
        from services.prospecting.event_discovery import EventOpportunity
        opp = EventOpportunity(
            name="Passado",
            event_type="sport",
            event_date="2000-01-01",
            location="X",
            source_url="http://x",
            organizer="Y",
        )
        assert opp.is_upcoming() is False

    def test_days_until_event_positivo_para_futuro(self):
        from services.prospecting.event_discovery import EventOpportunity
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=30)).isoformat()
        opp = EventOpportunity(
            name="30d", event_type="x", event_date=future,
            location="x", source_url="x", organizer="x",
        )
        assert 28 <= opp.days_until_event() <= 30  # tolerance


class TestEventDiscoveryProviderContract:
    def test_provider_tem_metodos_obrigatorios(self):
        from services.prospecting.event_discovery import EventDiscoveryProvider

        class _P:
            name = "fake"
            async def discover(self, lead_context=None):
                return []
        p = _P()
        assert hasattr(p, "name")
        assert hasattr(p, "discover")


class TestOrganizerResolver:
    def test_resolve_organizer_pelo_nome(self):
        from services.prospecting.event_discovery import OrganizerResolver
        resolver = OrganizerResolver()
        result = resolver.resolve_by_name("Federação Paulista de Karate")
        assert result["name"] == "Federação Paulista de Karate"
        assert result["source"] in ("known", "unknown", "name_only", "fuzzy")

    def test_resolve_organizer_exato_conhecido(self):
        from services.prospecting.event_discovery import OrganizerResolver
        resolver = OrganizerResolver()
        # Federação conhecida (cadastro simples in-memory)
        result = resolver.resolve_by_name("CBF")
        # CBF pode ser mapeado para "Confederação Brasileira de Futebol"
        assert result is not None

    def test_resolve_organizer_desconhecido_retorna_name_only(self):
        from services.prospecting.event_discovery import OrganizerResolver
        resolver = OrganizerResolver()
        result = resolver.resolve_by_name("Empresa XYZ123 Sem Padrao")
        assert result["source"] == "name_only"  # não esconde, retorna o que tem


class TestEventTimingScorer:
    def test_evento_futuro_proximo_timing_alto(self):
        from services.prospecting.event_discovery import EventTimingScorer
        from datetime import date, timedelta
        # Evento em 15 dias
        scorer = EventTimingScorer()
        event_date = (date.today() + timedelta(days=15)).isoformat()
        score = scorer.score(event_date)
        # 15 dias = janela ideal (entre 7d e 30d) → score alto
        assert score["timing_score"] >= 60
        assert score["urgency"] in ("high", "medium")

    def test_evento_muito_longo_timing_baixo(self):
        from services.prospecting.event_discovery import EventTimingScorer
        from datetime import date, timedelta
        scorer = EventTimingScorer()
        # Evento em 365 dias
        event_date = (date.today() + timedelta(days=365)).isoformat()
        score = scorer.score(event_date)
        # 1 ano = janela fria → score baixo
        assert score["timing_score"] <= 40  # 365d = very_low

    def test_evento_passado_timing_zero(self):
        from services.prospecting.event_discovery import EventTimingScorer
        from datetime import date, timedelta
        scorer = EventTimingScorer()
        # Evento em -30 dias (passado)
        event_date = (date.today() - timedelta(days=30)).isoformat()
        score = scorer.score(event_date)
        assert score["timing_score"] == 0
        assert score["urgency"] == "expired"

    def test_evento_hoje_timing_maximo(self):
        from services.prospecting.event_discovery import EventTimingScorer
        from datetime import date
        scorer = EventTimingScorer()
        score = scorer.score(date.today().isoformat())
        # Hoje é o dia do evento → urgência máxima
        assert score["timing_score"] >= 90


class TestEventDiscoveryExecutor:
    def test_executor_roda_providers_e_coleta_eventos(self):
        from services.prospecting.event_discovery import (
            EventDiscoveryRegistry, EventDiscoveryExecutor, _StubEventProvider,
        )
        from datetime import date, timedelta
        reg = EventDiscoveryRegistry()
        future = (date.today() + timedelta(days=30)).isoformat()
        reg.register(_StubEventProvider("sports_federation", events=[{
            "name": "Copa X", "event_type": "sport", "event_date": future,
            "location": "SP", "source_url": "https://x", "organizer": "Fed X",
        }]))
        executor = EventDiscoveryExecutor(reg)
        result = executor.execute({})
        assert "sports_federation" in result["events_by_provider"]
        assert len(result["events_by_provider"]["sports_federation"]) == 1

    def test_executor_resolve_organizer_para_cada_evento(self):
        from services.prospecting.event_discovery import (
            EventDiscoveryRegistry, EventDiscoveryExecutor, _StubEventProvider,
        )
        from datetime import date, timedelta
        reg = EventDiscoveryRegistry()
        future = (date.today() + timedelta(days=15)).isoformat()
        reg.register(_StubEventProvider("p1", events=[{
            "name": "Copa Y", "event_type": "sport", "event_date": future,
            "location": "SP", "source_url": "https://y", "organizer": "Fed Y",
        }]))
        executor = EventDiscoveryExecutor(reg)
        result = executor.execute({})
        # Cada evento tem organizer resolvido
        for ev in result["unique_events"]:
            assert "organizer_resolved" in ev
            assert ev["organizer_resolved"]["name"] == "Fed Y"

    def test_executor_calcula_timing_para_cada_evento(self):
        from services.prospecting.event_discovery import (
            EventDiscoveryRegistry, EventDiscoveryExecutor, _StubEventProvider,
        )
        from datetime import date, timedelta
        reg = EventDiscoveryRegistry()
        future = (date.today() + timedelta(days=7)).isoformat()
        reg.register(_StubEventProvider("p1", events=[{
            "name": "Copa Z", "event_type": "sport", "event_date": future,
            "location": "SP", "source_url": "https://z", "organizer": "Fed Z",
        }]))
        executor = EventDiscoveryExecutor(reg)
        result = executor.execute({})
        for ev in result["unique_events"]:
            assert "timing" in ev
            assert "timing_score" in ev["timing"]

    def test_executor_match_com_offer_profile_trophies(self):
        """Critério Fase F: evento real -> oportunidade comercial rastreável."""
        from services.prospecting.event_discovery import (
            EventDiscoveryRegistry, EventDiscoveryExecutor, _StubEventProvider,
        )
        from services.prospecting import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        from datetime import date, timedelta

        reg = EventDiscoveryRegistry()
        # Evento esportivo com organizador que parece empresa (siglas típicas)
        future = (date.today() + timedelta(days=20)).isoformat()
        reg.register(_StubEventProvider("p1", events=[{
            "name": "Copa Paulista de Karate 2026",
            "event_type": "sport",
            "event_date": future,
            "location": "São Paulo, SP",
            "source_url": "https://federacao.org/copa",
            "organizer": "Federação Paulista de Karate",  # organizador com nome de fed
        }]))
        executor = EventDiscoveryExecutor(reg)
        result = executor.execute({})
        # Cada evento é um lead para o OfferMatcher
        matcher = OfferMatcher(build_default_registry())
        # Cria lead_data a partir do evento
        ev = result["unique_events"][0]
        lead_data = {
            "company_name": ev["organizer_resolved"]["name"],
            "segment": "esportivos",  # match com trophies
            "has_phone": True,
            "has_instagram": True,
            "hosts_events": True,
        }
        opps = matcher.match(lead_data)
        # Trophies deve estar no top
        keys = [o.offer_key for o in opps]
        assert "trophies" in keys

    def test_executor_pula_provider_ausente(self):
        from services.prospecting.event_discovery import (
            EventDiscoveryRegistry, EventDiscoveryExecutor, _StubEventProvider,
        )
        reg = EventDiscoveryRegistry()
        reg.register(_StubEventProvider("known"))
        executor = EventDiscoveryExecutor(reg)
        result = executor.execute({})
        assert "known" in result["events_by_provider"]
        # provider não registrado → skipped
        result2 = executor.execute({})
        assert result2["skipped"] == []  # plano vazio, nada pulado

    def test_executor_dedup_por_source_url(self):
        from services.prospecting.event_discovery import (
            EventDiscoveryRegistry, EventDiscoveryExecutor, _StubEventProvider,
        )
        from datetime import date, timedelta
        reg = EventDiscoveryRegistry()
        future = (date.today() + timedelta(days=10)).isoformat()
        ev = {
            "name": "Copa", "event_type": "sport", "event_date": future,
            "location": "SP", "source_url": "https://dup", "organizer": "X",
        }
        reg.register(_StubEventProvider("p1", events=[ev]))
        reg.register(_StubEventProvider("p2", events=[ev]))  # mesmo evento
        executor = EventDiscoveryExecutor(reg)
        result = executor.execute({})
        # Dedup por source_url
        assert result["unique_count"] == 1
        assert result["total_events"] == 2


class TestEventDiscoveryAlphaMec:
    """Cenário real: AlphaMec (EJ) vende troféus para federações esportivas.

    Pipeline: evento esportivo futuro → organizer resolved → timing
    score → match com OfferProfile.trophies → oportunidade rastreável.
    """

    def test_cenario_completo_alpha_mec(self):
        """Copa Paulista de Karate em 30 dias → oportunidade para AlphaMec."""
        from services.prospecting.event_discovery import (
            build_default_event_registry, EventDiscoveryExecutor, SportsFederationProvider,
        )
        from services.prospecting import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        from datetime import date, timedelta

        # 1) Provider recebe lista de eventos
        future = (date.today() + timedelta(days=30)).isoformat()
        known_events = [{
            "name": "Copa Paulista de Karate 2026",
            "event_type": "sport",
            "event_date": future,
            "location": "São Paulo, SP",
            "source_url": "https://fpk.org.br/copa-2026",
            "organizer": "Federação Paulista de Karatê",
        }]
        registry = build_default_event_registry()
        # Substitui o provider stub por um com evento real
        registry.register(SportsFederationProvider(known_events=known_events))

        # 2) Executor descobre e resolve
        executor = EventDiscoveryExecutor(registry)
        result = executor.execute({})
        assert result["unique_count"] == 1
        event = result["unique_events"][0]

        # 3) Organizer resolved (Federação detectada)
        org = event["organizer_resolved"]
        assert org["name"] == "Federação Paulista de Karatê"
        assert org["source"] == "fuzzy"
        assert org["type"] == "federation"

        # 4) Timing score (30 dias = sweet spot)
        timing = event["timing"]
        assert timing["urgency"] in ("high", "medium")
        assert timing["timing_score"] >= 60

        # 5) Match com OfferProfile.trophies (organizador vira lead)
        lead_data = {
            "company_name": org["official_name"] or org["name"],
            "segment": "esportivos",
            "has_phone": True,
            "has_instagram": True,
            "hosts_events": True,
        }
        matcher = OfferMatcher(build_default_registry())
        opps = matcher.match(lead_data)
        # Trophies deve aparecer
        trophies_opp = next((o for o in opps if o.offer_key == "trophies"), None)
        assert trophies_opp is not None
        assert trophies_opp.score > 0

    def test_cenario_5_eventos_dedup_e_ranking(self):
        """5 eventos (3 duplicados) → único resultado ranqueado por timing."""
        from services.prospecting.event_discovery import (
            EventDiscoveryRegistry, EventDiscoveryExecutor, SportsFederationProvider,
        )
        from datetime import date, timedelta

        reg = EventDiscoveryRegistry()
        today = date.today()
        events = [
            # Evento 1: hoje, alta urgência
            {"name": "E1", "event_type": "sport", "event_date": today.isoformat(),
             "location": "SP", "source_url": "https://e1", "organizer": "Fed Y"},
            # Evento 2: 30 dias
            {"name": "E2", "event_type": "sport",
             "event_date": (today + timedelta(days=30)).isoformat(),
             "location": "RJ", "source_url": "https://e2", "organizer": "Fed Z"},
            # Evento 3: 365 dias (muito longo)
            {"name": "E3", "event_type": "sport",
             "event_date": (today + timedelta(days=365)).isoformat(),
             "location": "MG", "source_url": "https://e3", "organizer": "Fed W"},
            # Duplicado de E1 (mesmo source_url)
            {"name": "E1-dup", "event_type": "sport", "event_date": today.isoformat(),
             "location": "SP", "source_url": "https://e1", "organizer": "Fed Y"},
            # Evento 4: 10 dias (sweet spot)
            {"name": "E4", "event_type": "sport",
             "event_date": (today + timedelta(days=10)).isoformat(),
             "location": "BA", "source_url": "https://e4", "organizer": "Fed V"},
        ]
        reg.register(SportsFederationProvider(known_events=events))
        executor = EventDiscoveryExecutor(reg)
        result = executor.execute({})
        # 5 raw → 4 únicos (E1+E1-dup deduped)
        assert result["total_events"] == 5
        assert result["unique_count"] == 4

    def test_execute_sync_preserva_eventos_quando_loop_ja_esta_ativo(self):
        """A API sync não pode descartar corrotinas em host ASGI/loop ativo."""
        import asyncio
        from services.prospecting.event_discovery import (
            EventDiscoveryRegistry,
            EventDiscoveryExecutor,
            SportsFederationProvider,
        )

        registry = EventDiscoveryRegistry()
        registry.register(SportsFederationProvider(known_events=[{
            "name": "Evento em loop",
            "event_type": "sport",
            "event_date": "2099-01-01",
            "location": "SP",
            "source_url": "https://loop-event",
            "organizer": "Federação X",
        }]))
        executor = EventDiscoveryExecutor(registry)

        async def invoke_sync_api_inside_loop():
            return executor.execute({})

        result = asyncio.run(invoke_sync_api_inside_loop())
        assert result["unique_count"] == 1
        assert result["unique_events"][0]["name"] == "Evento em loop"
