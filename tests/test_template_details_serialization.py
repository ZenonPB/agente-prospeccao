"""Serialização de vertentes para a tela de detalhes (seam: _serialize).

A visão simples/avançada da vertente deriva tudo do payload lido — por isso
o endpoint precisa expor `prescoring_config` (limiares) e
`enrichment_strategy` (exceções de execução) além dos critérios.
"""
from types import SimpleNamespace

from src.routes.scoring_templates import _serialize


def _tmpl(**overrides):
    base = {
        "id": "template-1",
        "service_label": "Landing pages",
        "positive_signals": [],
        "negative_signals": [],
        "context_signals": [],
        "requires_technical_report": True,
        "requires_business_data": True,
        "enrichment_steps": ["technical_site"],
        "cadence_schedule": [0, 3, 7, 14],
        "extra_instructions": None,
        "playbook": {},
        "is_generated": False,
        "is_active": True,
        "organization_id": None,
        "created_at": None,
        "updated_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestTemplateDetailsSerialization:
    def test_expoe_prescoring_e_strategy(self):
        payload = _serialize(_tmpl(
            prescoring_config={"profile": "web_presence", "enabled": True, "threshold": 45, "top_k": None},
            enrichment_strategy={"skip": ["technical_site"], "stop_after": None},
        ))
        assert payload["prescoring_config"] == {"profile": "web_presence", "enabled": True, "threshold": 45, "top_k": None}
        assert payload["enrichment_strategy"] == {"skip": ["technical_site"], "stop_after": None}

    def test_ausencia_vira_none(self):
        payload = _serialize(_tmpl(prescoring_config=None, enrichment_strategy=None))
        assert payload["prescoring_config"] is None
        assert payload["enrichment_strategy"] is None

    def test_campos_de_criterios_preservados(self):
        payload = _serialize(_tmpl(
            positive_signals=[{"label": "Sem site", "description": "d", "weight_hint": "high"}],
        ))
        assert payload["positive_signals"] == [{"label": "Sem site", "description": "d", "weight_hint": "high"}]
        assert payload["service_label"] == "Landing pages"
