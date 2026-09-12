"""Compatibilidade temporária para o antigo caminho de modelos comerciais."""
from database.commercial_intelligence_models import (
    CaseStudy,
    EventSeries,
    ProspectingAgentState,
    ProspectingAlert,
    SavedProspectingSearch,
)

__all__ = [
    "CaseStudy",
    "EventSeries",
    "ProspectingAgentState",
    "ProspectingAlert",
    "SavedProspectingSearch",
]
