"""Event Discovery (Fase F — consolidação §Fase F).

Transforma eventos futuros (competições esportivas, cerimônias, feiras) em
oportunidades comerciais rastreáveis, com:
- EventOpportunity (entidade conceitual completa)
- EventDiscoveryProvider (contract + registry + executor)
- OrganizerResolver (resolve organizador → empresa prospectável)
- EventTimingScorer (urgência baseada em event_date)
- Integração com OfferMatcher (trophies)

Critério da Fase F: "Sistema consegue transformar um evento futuro em
oportunidade comercial rastreável."

Contexto AlphaMec: principal motor de receita é venda de troféus para
eventos esportivos/corporativos sazonais. O pipeline de Event Discovery
é o coração do funil — eventos viram leads (organizadores) e leads
viram ofertas (trophies).
"""
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ============================================================
# EventOpportunity — entidade conceitual (consolidação §13)
# ============================================================

@dataclass
class EventOpportunity:
    """Representa um evento futuro como oportunidade comercial."""
    name: str
    event_type: str  # sport | corporate | fair | ceremony | other
    event_date: str  # ISO date "2026-12-15"
    location: str
    source_url: str
    organizer: str
    # Campos opcionais com defaults (consolidação §Fase F)
    confidence: float = 0.5
    registration_status: str = "unknown"  # open | closed | unknown
    observed_at: Optional[str] = None
    expires_at: Optional[str] = None
    # Resolução do organizador (preenchido pelo executor)
    organizer_resolved: Optional[Dict[str, Any]] = None
    # Timing score (preenchido pelo executor)
    timing: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        # Serialização manual para evitar deepcopy de objetos nested
        # (mappingproxy do organizer_resolved/timing quando setados).
        d = {f.name: getattr(self, f.name) for f in self.__dataclass_fields__.values()}
        # Converte tipos não-primitivos para primitivos
        for k, v in list(d.items()):
            if isinstance(v, dict):
                d[k] = dict(v)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EventOpportunity":
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})

    def is_upcoming(self) -> bool:
        """True se o evento ainda não aconteceu."""
        try:
            ev_date = date.fromisoformat(self.event_date)
            return ev_date >= date.today()
        except (ValueError, TypeError):
            return False  # UNKNOWN ≠ True (consolidação §27)

    def days_until_event(self) -> Optional[int]:
        """Dias até o evento. Negativo se já passou. None se data inválida."""
        try:
            ev_date = date.fromisoformat(self.event_date)
            return (ev_date - date.today()).days
        except (ValueError, TypeError):
            return None


# ============================================================
# EventDiscoveryProvider — contract
# ============================================================

@runtime_checkable
class EventDiscoveryProvider(Protocol):
    """Contrato mínimo de provider de descoberta de eventos."""
    name: str

    async def discover(
        self, lead_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...


class _StubEventProvider:
    """Stub para tests."""

    def __init__(self, name: str, events: Optional[List[Dict]] = None):
        self.name = name
        self._events = events or []

    async def discover(self, lead_context=None):
        return list(self._events)


class EventDiscoveryRegistry:
    """Registry de providers de eventos."""

    def __init__(self):
        self._by_name: Dict[str, EventDiscoveryProvider] = {}

    def register(self, provider: EventDiscoveryProvider) -> None:
        self._by_name[provider.name] = provider

    def get(self, name: str) -> Optional[EventDiscoveryProvider]:
        return self._by_name.get(name)

    def list_keys(self) -> List[str]:
        return list(self._by_name.keys())


# ============================================================
# OrganizerResolver — resolve organizador → empresa prospectável
# ============================================================

class OrganizerResolver:
    """Resolve nome de organizador para uma entidade conhecida.

    Estratégia:
    1. Match exato no cadastro (Federação CBF, FPF, etc.)
    2. Match por similaridade (fuzzy)
    3. Fallback: retorna name_only (consolidação §27: não esconder UNKNOWN)
    """

    # Cadastro simples de federações conhecidas (fonte rastreável)
    _KNOWN_ORGANIZERS: Dict[str, Dict[str, str]] = {
        "cbf": {"name": "Confederação Brasileira de Futebol", "type": "federation"},
        "fpf": {"name": "Federação Paulista de Futebol", "type": "federation"},
        "cbk": {"name": "Confederação Brasileira de Karatê", "type": "federation"},
        "cbv": {"name": "Confederação Brasileira de Vôlei", "type": "federation"},
        "cbj": {"name": "Confederação Brasileira de Judô", "type": "federation"},
        "cbat": {"name": "Confederação Brasileira de Atletismo", "type": "federation"},
        "cbb": {"name": "Confederação Brasileira de Basquete", "type": "federation"},
        "fpf-karate": {"name": "Federação Paulista de Karatê", "type": "federation"},
    }

    def resolve_by_name(self, name: str) -> Dict[str, Any]:
        """Resolve nome para organizador.

        Returns:
            {
                "name": str,
                "official_name": str | None,
                "type": str | None,  # federation | company | unknown
                "source": str,  # "exact" | "fuzzy" | "name_only"
                "confidence": float,
            }
        """
        if not name or not name.strip():
            return {
                "name": name or "",
                "official_name": None,
                "type": None,
                "source": "name_only",
                "confidence": 0.0,
            }
        norm = name.strip().lower()
        # 1) Match exato (siglas)
        if norm in self._KNOWN_ORGANIZERS:
            return {
                "name": name,
                "official_name": self._KNOWN_ORGANIZERS[norm]["name"],
                "type": self._KNOWN_ORGANIZERS[norm]["type"],
                "source": "exact",
                "confidence": 0.95,
            }
        # 2) Match fuzzy: nome contém "Federação" / "Confederação" / "Liga"
        lower = name.lower()
        for keyword in ("federação", "confederação", "liga", "associação"):
            if keyword in lower:
                return {
                    "name": name,
                    "official_name": name,
                    "type": "federation" if keyword != "associação" else "association",
                    "source": "fuzzy",
                    "confidence": 0.6,
                }
        # 3) Fallback: name_only (não esconde UNKNOWN)
        return {
            "name": name,
            "official_name": name,
            "type": "unknown",
            "source": "name_only",
            "confidence": 0.3,
        }


# ============================================================
# EventTimingScorer — urgência baseada em event_date
# ============================================================

class EventTimingScorer:
    """Calcula timing score (0-100) baseado em proximidade do evento.

    Janela ideal: 7-60 dias (espaço para prospecção + produção de troféus).
    - Hoje: 100 (urgência máxima)
    - 7-60 dias: 80-100 (sweet spot)
    - 60-180 dias: 50-80 (planejamento)
    - 180+ dias: <50 (frio)
    - Passado: 0 (expirado)
    """

    def __init__(self, ideal_min_days: int = 7, ideal_max_days: int = 60):
        self.ideal_min_days = ideal_min_days
        self.ideal_max_days = ideal_max_days

    def score(self, event_date_str: str) -> Dict[str, Any]:
        """Calcula timing e classifica urgência."""
        try:
            ev_date = date.fromisoformat(event_date_str)
        except (ValueError, TypeError):
            return {
                "timing_score": 0,
                "urgency": "unknown",
                "days_until": None,
                "reason": "invalid_date",
            }
        days = (ev_date - date.today()).days
        if days < 0:
            return {
                "timing_score": 0,
                "urgency": "expired",
                "days_until": days,
                "reason": "past_event",
            }
        if days == 0:
            return {
                "timing_score": 100,
                "urgency": "today",
                "days_until": 0,
                "reason": "happens_today",
            }
        # Janela ideal
        if self.ideal_min_days <= days <= self.ideal_max_days:
            score = 100
            urgency = "high" if days <= 30 else "medium"
        elif days < self.ideal_min_days:
            # 1-6 dias: muito próximo, urgência alta
            score = 90
            urgency = "high"
        elif days <= 180:
            # 60-180 dias: planejamento
            score = max(40, 80 - (days - 60) // 5)
            urgency = "low"
        else:
            # 180+ dias: frio (decay mais agressivo)
            score = max(10, 40 - (days - 180) // 20)
            urgency = "very_low"
        return {
            "timing_score": score,
            "urgency": urgency,
            "days_until": days,
            "reason": "scored",
        }


# ============================================================
# EventDiscoveryExecutor — pipeline completo
# ============================================================

class EventDiscoveryExecutor:
    """Executa pipeline de Event Discovery: provider → organizer → timing → matcher.

    Critério da Fase F: 'Sistema consegue transformar um evento futuro
    em oportunidade comercial rastreável.'
    """

    def __init__(
        self,
        registry: EventDiscoveryRegistry,
        organizer_resolver: Optional[OrganizerResolver] = None,
        timing_scorer: Optional[EventTimingScorer] = None,
    ):
        self.registry = registry
        self.organizer_resolver = organizer_resolver or OrganizerResolver()
        self.timing_scorer = timing_scorer or EventTimingScorer()

    def execute(
        self,
        plan: Optional[Dict[str, Any]] = None,
        lead_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Executa pipeline completo de event discovery.

        Se `plan` é None ou vazio, executa TODOS os providers do registry
        (modo "all").
        """
        plan = plan or {}
        events_by_provider: Dict[str, List[EventOpportunity]] = {}
        execution_order: List[str] = []
        skipped: List[str] = []

        # 1) Provider collection — usa plan se fornecido, senão todos
        plan_providers = plan.get("providers") or [{"type": k} for k in self.registry.list_keys()]
        for step in plan_providers:
            provider_name = step.get("type")
            provider = self.registry.get(provider_name)
            if provider is None:
                skipped.append(provider_name)
                continue
            execution_order.append(provider_name)
            # Roda provider (sync ou async)
            try:
                raw_events = self._invoke_provider(provider, lead_context)
            except Exception:
                raw_events = []
            # 2) Converte para EventOpportunity
            opps = [self._to_event_opportunity(e) for e in raw_events]
            events_by_provider[provider_name] = opps

        # 3) Dedup por source_url
        all_events: List[EventOpportunity] = []
        for name in execution_order:
            all_events.extend(events_by_provider.get(name, []))

        # 4) Resolve organizer + timing para cada evento
        unique_events: List[Dict[str, Any]] = []
        seen_urls: set = set()
        for ev in all_events:
            if ev.source_url in seen_urls:
                continue
            seen_urls.add(ev.source_url)
            # Organizer resolution
            org_resolved = self.organizer_resolver.resolve_by_name(ev.organizer)
            # Timing score
            timing = self.timing_scorer.score(ev.event_date)
            # Concatena como dict puro (sem objetos aninhados problemáticos)
            ev_with_meta = {
                **ev.to_dict(),
                "organizer_resolved": dict(org_resolved),
                "timing": dict(timing),
            }
            unique_events.append(ev_with_meta)

        return {
            "events_by_provider": {k: [e.to_dict() for e in v] for k, v in events_by_provider.items()},
            "execution_order": execution_order,
            "skipped": skipped,
            "total_events": len(all_events),
            "unique_events": unique_events,
            "unique_count": len(unique_events),
        }

    def _invoke_provider(
        self, provider: EventDiscoveryProvider, lead_context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Roda provider detectando sync/async."""
        import asyncio
        import inspect
        import threading

        res = provider.discover(lead_context)
        if inspect.isawaitable(res):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # Nenhum loop nesta thread: asyncio.run cria e fecha um loop
                # próprio, sem emitir o warning de get_event_loop().
                try:
                    res = asyncio.run(res)
                except RuntimeError:
                    if inspect.iscoroutine(res):
                        res.close()
                    return []
            else:
                # `execute()` pode ser chamado por código sync que está
                # hospedado dentro de um loop (ex.: servidor ASGI). Rode
                # o awaitable numa thread com loop próprio; não descarte
                # o evento nem deixe coroutine não aguardada.
                result_box: List[Any] = []
                error_box: List[BaseException] = []

                def _run() -> None:
                    try:
                        result_box.append(asyncio.run(res))
                    except BaseException as exc:  # noqa: BLE001
                        error_box.append(exc)

                worker = threading.Thread(target=_run, daemon=True)
                worker.start()
                worker.join()
                if error_box:
                    return []
                return list(result_box[0] or []) if result_box else []
        return res or []

    def _to_event_opportunity(self, raw: Dict[str, Any]) -> EventOpportunity:
        """Converte dict raw em EventOpportunity, com defaults seguros."""
        return EventOpportunity.from_dict({
            "name": raw.get("name", ""),
            "event_type": raw.get("event_type", "other"),
            "event_date": raw.get("event_date", ""),
            "location": raw.get("location", ""),
            "source_url": raw.get("source_url", ""),
            "organizer": raw.get("organizer", ""),
            "confidence": float(raw.get("confidence", 0.5)),
            "registration_status": raw.get("registration_status", "unknown"),
            "observed_at": raw.get("observed_at"),
            "expires_at": raw.get("expires_at"),
        })


# ============================================================
# EventDiscoveryAdapter — adapters reais (sports_federation stub)
# ============================================================

class SportsFederationProvider:
    """Provider que simula scraping de federações esportivas.

    Em produção, isso seria conectado a APIs reais de federações (CBF/FPF/etc).
    Aqui fica como stub testável — sem dependência de rede.
    """

    name = "sports_federation"

    def __init__(self, known_events: Optional[List[Dict]] = None):
        # Eventos conhecidos do cadastro (em produção viriam de API/HTML)
        self._known_events = known_events or []

    async def discover(self, lead_context=None):
        return list(self._known_events)


def build_default_event_registry() -> EventDiscoveryRegistry:
    """Registry padrão com SportsFederationProvider."""
    reg = EventDiscoveryRegistry()
    reg.register(SportsFederationProvider())
    return reg
