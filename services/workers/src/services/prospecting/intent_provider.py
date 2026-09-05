"""IntentProvider (Fase E — consolidação §Fase E).

Producers de eventos de intenção. Substituem o "fabricador de HIRING" que o
IntentEngine fazia a partir de keywords do LLM — agora providers reais
coletam eventos de fontes externas (site, job boards, news).

Critério: "Um evento real coletado altera timing/intent da oportunidade
com evidência."
"""
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from datetime import datetime, timezone


@runtime_checkable
class IntentProvider(Protocol):
    """Contrato mínimo de producer de intenção."""
    name: str

    async def collect(self, lead_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        ...


class _StubIntentProvider:
    """Stub para tests."""

    def __init__(self, name: str, results: Optional[List[Dict]] = None):
        self.name = name
        self._results = results or []

    async def collect(self, lead_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return list(self._results)


class IntentProviderRegistry:
    """Registry de providers de intent, indexado por name."""

    def __init__(self):
        self._by_name: Dict[str, IntentProvider] = {}

    def register(self, provider: IntentProvider) -> None:
        self._by_name[provider.name] = provider

    def get(self, name: str) -> Optional[IntentProvider]:
        return self._by_name.get(name)

    def list_keys(self) -> List[str]:
        return list(self._by_name.keys())


class IntentScorer:
    """Aplica decay temporal aos eventos de intenção (consolidação §Fase E).

    Decay linear: score = confidence * max(0, 1 - days_since/decay_days).
    Sem observed_at: não aplica decay (consolidação §27: não esconder UNKNOWN).
    """

    def __init__(self, decay_days: int = 90, trigger_threshold: float = 0.5):
        self.decay_days = decay_days
        self.trigger_threshold = trigger_threshold

    def _parse_date(self, observed_at: Optional[str]) -> Optional[datetime]:
        if not observed_at:
            return None
        try:
            # Aceita ISO com ou sem timezone
            if "T" not in observed_at and " " in observed_at:
                return datetime.fromisoformat(observed_at.replace(" ", "T"))
            dt = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    def score(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula score com decay e classifica trigger."""
        confidence = event.get("confidence")
        if confidence is None:
            return {
                "key": event.get("key"),
                "score": 0.0,
                "triggered": False,
                "reason": "no_confidence",
            }
        observed = self._parse_date(event.get("observed_at"))
        if observed is None:
            # Sem data: não aplica decay (não esconder UNKNOWN)
            return {
                "key": event.get("key"),
                "score": float(confidence),
                "triggered": float(confidence) >= self.trigger_threshold,
                "reason": "no_observed_at",
            }
        now = datetime.now(timezone.utc)
        days = (now - observed).days
        if days >= self.decay_days:
            return {
                "key": event.get("key"),
                "score": 0.0,
                "triggered": False,
                "reason": "expired",
                "days_old": days,
            }
        factor = max(0.0, 1.0 - days / self.decay_days)
        final = float(confidence) * factor
        return {
            "key": event.get("key"),
            "score": round(final, 3),
            "triggered": final >= self.trigger_threshold,
            "reason": "scored",
            "days_old": days,
            "decay_factor": round(factor, 3),
        }


class WebsiteIntentProvider:
    """Detecta sinais de intenção a partir do HTML do site do lead.

    Sem dependência de rede — `collect` requer que o HTML seja passado
    (injetado pelo orchestrator). Esta é a versão "pura" testável; a
    versão com fetch HTTP é adapter separado.
    """

    name = "website"

    # Padrões (path keyword → event key)
    _PATTERNS: Dict[str, str] = {
        "carreira": "HIRING",
        "career": "HIRING",
        "job": "HIRING",
        "trabalhe": "HIRING",
        "vaga": "HIRING",
        "produto": "NEW_PRODUCT",
        "novo": "NEW_PRODUCT",
        "lancamento": "NEW_PRODUCT",
        "expans": "EXPANDING",
        "nova-filial": "NEW_BRANCH",
        "filial": "NEW_BRANCH",
    }

    async def collect(self, lead_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Coleta eventos do site. lead_context deve trazer 'html' e 'base_url'."""
        html = lead_context.get("html", "")
        base_url = lead_context.get("base_url", "")
        return self._parse_html_for_intent(html, base_url)

    def _parse_html_for_intent(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not html or not base_url:
            return events
        html_l = html.lower()
        seen_keys: set = set()
        for pattern, event_key in self._PATTERNS.items():
            if pattern in html_l and event_key not in seen_keys:
                seen_keys.add(event_key)
                # Tenta extrair o href (heurística simples)
                evidence_url = self._extract_href(html, pattern, base_url)
                events.append({
                    "key": event_key,
                    "confidence": 0.6,  # signal fraco — site pode ter link morto
                    "source": "website",
                    "evidence": f"Pattern '{pattern}' found in HTML",
                    "evidence_url": evidence_url,
                    "observed_at": None,  # site não tem data confiável
                })
        return events

    def _extract_href(self, html: str, pattern: str, base_url: str) -> Optional[str]:
        """Heurística: extrai o primeiro href que contém o pattern."""
        import re
        # Procura <a href="...pattern...">
        m = re.search(
            rf'href=["\']([^"\']*{pattern}[^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            href = m.group(1)
            if href.startswith("http"):
                return href
            if href.startswith("/"):
                return base_url.rstrip("/") + href
        return None


class JobPostingIntentProvider:
    """Detecta intenção HIRING a partir de vagas em job boards.

    `collect` recebe `lead_context` com 'jobs' (lista de vagas) e gera
    eventos HIRING com decay temporal via IntentScorer.
    """

    name = "jobs"

    def __init__(self, decay_days: int = 90):
        # Default 90d: vaga de 2 dias (factor 0.978) → confidence 0.685
        # Vaga de 30 dias (factor 0.667) → confidence 0.467 (abaixo do trigger)
        self.scorer = IntentScorer(decay_days=decay_days, trigger_threshold=0.5)

    async def collect(self, lead_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        jobs = lead_context.get("jobs", [])
        domain = lead_context.get("domain", "")
        events: List[Dict[str, Any]] = []
        for job in jobs:
            events.extend(self._job_to_events(job, domain))
        return events

    def _job_to_events(self, job: Dict[str, Any], domain: str) -> List[Dict[str, Any]]:
        title = job.get("title", "")
        if not title:
            return []
        # Vaga recente + score base 0.7
        observed = job.get("posted_at", "")
        scored = self.scorer.score({
            "key": "HIRING",
            "confidence": 0.7,
            "observed_at": observed,
        })
        if scored["score"] == 0 and scored["reason"] == "expired":
            # Vaga muito antiga — descarta mas loga
            return []
        return [{
            "key": "HIRING",
            "confidence": scored["score"] if scored["reason"] == "scored" else 0.7,
            "source": "jobs",
            "evidence": f"Vaga encontrada: {title}",
            "evidence_url": job.get("url"),
            "observed_at": observed,
            "domain": domain,
        }]


def build_default_intent_registry() -> IntentProviderRegistry:
    """Registry padrão com WebsiteIntentProvider + JobPostingIntentProvider."""
    reg = IntentProviderRegistry()
    reg.register(WebsiteIntentProvider())
    reg.register(JobPostingIntentProvider())
    return reg
