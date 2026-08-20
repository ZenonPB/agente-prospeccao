"""Carimbos de tempo do enriquecimento por fonte (LinkedIn, site, reviews).

Cada fonte tem um TTL: o lead não é re-buscado/re-analisado dentro dele.
Os timestamps ficam em `leads.enrichment_timestamps` (JSONB) e a API usa o
mesmo módulo para expor o quão "velho" cada dado está na página do lead.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Vida útil de cada fonte de enriquecimento, em horas.
TTL_HOURS: Dict[str, int] = {
    "linkedin": 30 * 24,  # candidato de perfil (pessoa/empresa) — 30 dias
    "site": 7 * 24,       # análise técnica do site — 7 dias
    "reviews": 24,        # reputação no Google (rating/avaliações) — 24h
    "cnpj": 30 * 24,      # dados cadastrais da Receita Federal — 30 dias
}


def now_iso() -> str:
    """Timestamp atual UTC em formato ISO (padrão de gravação)."""
    return datetime.now(timezone.utc).isoformat()


def read_stamps(lead: Any) -> Dict[str, str]:
    """Lê os timestamps por fonte de um lead (entre ORM ou objeto bespoke)."""
    if not hasattr(lead, "enrichment_timestamps"):
        return {}
    return dict(lead.enrichment_timestamps or {})


def get_stamp(lead: Any, source: str) -> Optional[str]:
    """Timestamp ISO de uma fonte (ou None se nunca enriquecida)."""
    return read_stamps(lead).get(source)


def stamp(lead: Any, source: str, when: Optional[datetime] = None) -> None:
    """Grava o timestamp de uma fonte no lead (atribuição em molde p/ SQLAlchemy)."""
    ts = (when or datetime.now(timezone.utc)).isoformat()
    stamps = read_stamps(lead)
    stamps[source] = ts
    lead.enrichment_timestamps = stamps


def is_fresh(stamp_iso: Optional[str], source: str, now: Optional[datetime] = None) -> bool:
    """True se a fonte tem o carimbo dentro do TTL (não precisa re-buscar)."""
    if not stamp_iso:
        return False
    try:
        dt = datetime.fromisoformat(stamp_iso)
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - dt) < timedelta(hours=TTL_HOURS.get(source, 0))


def freshness_snapshot(stamps: Dict[str, str], now: Optional[datetime] = None) -> Dict[str, Optional[str]]:
    """Estado de cada fonte para a UI: 'fresh' | 'stale' | None (nunca)."""
    out: Dict[str, Optional[str]] = {}
    for source in TTL_HOURS:
        stamp_value = (stamps or {}).get(source)
        if not stamp_value:
            out[source] = None
        else:
            out[source] = "fresh" if is_fresh(stamp_value, source, now) else "stale"
    return out