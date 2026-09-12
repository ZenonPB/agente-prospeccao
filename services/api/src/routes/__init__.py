"""Composição dos routers públicos da API.

`leads.py` ainda é um módulo legado grande. As mutações comerciais críticas são
instaladas após o carregamento dele para preservar imports/URLs existentes sem
manter duas implementações ativas no runtime.
"""
from . import leads as leads
from .lead_mutations import install_lead_mutations

install_lead_mutations(leads)

__all__ = ["leads"]
