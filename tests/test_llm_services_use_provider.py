"""Os serviços de LLM usam a mesma costura do provider (pacing/retry/cota).

Depois da centralização do modelo, segment/brief/router/geração de template
devem delegar a `groq_json_chat` (lazy import). Aqui stubamos essa função e
garantimos o comportamento de sucesso/fallback de cada serviço, sem rede.
"""
import asyncio

import pytest

from services.segment_suggestion_service import SegmentSuggestionService
from services.campaign_brief_service import CampaignBriefService
from services.template_router import _classify_llm, ROUTE_MATCHED, ROUTE_GENERIC
from services.template_generation_service import TemplateGenerationService


def _patch_provider(monkeypatch, result):
    from services import provider_client

    async def fake_groq_json_chat(*args, **kwargs):
        return result

    monkeypatch.setattr(provider_client, "groq_json_chat", fake_groq_json_chat)
    monkeypatch.setattr(provider_client, "_last_groq_sent", 0.0)


# ---------------------------------------------------------------------------
# Segment suggestion
# ---------------------------------------------------------------------------

def test_segment_suggestion_normaliza_resposta_do_provider(monkeypatch):
    _patch_provider(monkeypatch, {
        "segment": "Clínicas odontológicas",
        "rationale": "Dependem de captação local.",
        "subniches": ["Odontopediatria"],
        "hook": "Site sem agendamento",
        "cities_hint": ["Araraquara"],
    })
    out = asyncio.run(SegmentSuggestionService(api_key="test").suggest(profile="web_presence"))
    assert out["segment"] == "Clínicas odontológicas"
    assert out["cities_hint"] == ["Araraquara"]


def test_segment_suggestion_falha_cai_no_fallback_offline(monkeypatch):
    _patch_provider(monkeypatch, None)
    out = asyncio.run(SegmentSuggestionService(api_key="test").suggest(profile="web_presence"))
    assert out["segment"]  # fallback determinístico


# ---------------------------------------------------------------------------
# Campaign brief
# ---------------------------------------------------------------------------

def test_brief_interpret_normaliza_e_nao_inventa_perfil(monkeypatch):
    _patch_provider(monkeypatch, {
        "name": "Landing pages - Clínicas de psicologia - Araraquara",
        "target_service": "Landing pages para captação de pacientes",
        "target_segment": "Clínicas de psicologia",
        "target_city": "Araraquara",
        "target_state": "SP",
        "analysis_profile": "web_presence",
        "places_query": "clinica de psicologia em Araraquara",
        "scoring_template_label": "SEO / Marketing Digital",
        "rationale": "Fito direto.",
    })
    out = asyncio.run(CampaignBriefService(api_key="test").interpret("brief"))
    assert out["target_city"] == "Araraquara"
    assert out["analysis_profile"] == "web_presence"


def test_brief_falha_do_provider_levanta_runtimeerror(monkeypatch):
    _patch_provider(monkeypatch, None)
    with pytest.raises(RuntimeError):
        asyncio.run(CampaignBriefService(api_key="test").interpret("brief"))


# ---------------------------------------------------------------------------
# Template router (classificação LLM)
# ---------------------------------------------------------------------------

def test_classify_llm_match_por_choice(monkeypatch):
    _patch_provider(monkeypatch, {"choice": "Desenvolvimento de Sites"})
    route, label = asyncio.run(_classify_llm("sites", ["Desenvolvimento de Sites"], api_key="k"))
    assert route == ROUTE_MATCHED
    assert label == "Desenvolvimento de Sites"


def test_classify_llm_falha_cai_no_generico(monkeypatch):
    _patch_provider(monkeypatch, None)
    route, label = asyncio.run(_classify_llm("qualquer", ["X"], api_key="k"))
    assert route == ROUTE_GENERIC


# ---------------------------------------------------------------------------
# Geração de template
# ---------------------------------------------------------------------------

def _valid_template_dict():
    return {
        "service_label": "Landing Pages para Clínicas de Saúde",
        "requires_technical_report": True,
        "requires_business_data": True,
        "positive_signals": [{"label": "Sem site próprio", "description": "Usa só Instagram", "weight_hint": "high"}],
        "negative_signals": [],
        "context_signals": [{"label": "Segmento", "description": "Clínicas"}],
        "extra_instructions": "Valide a presença digital.",
    }


def test_template_generation_valida_resposta(monkeypatch):
    _patch_provider(monkeypatch, _valid_template_dict())
    out = asyncio.run(
        TemplateGenerationService(api_key="test")._call_llm("landing pages", "clínicas"),
    )
    assert out["service_label"].startswith("Landing Pages")
    assert out["positive_signals"][0]["weight_hint"] == "high"


def test_template_generation_falha_retorna_none(monkeypatch):
    _patch_provider(monkeypatch, None)
    out = asyncio.run(
        TemplateGenerationService(api_key="test")._call_llm("landing pages", "clínicas"),
    )
    assert out is None