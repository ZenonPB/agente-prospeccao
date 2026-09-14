"""Regressão do F-03: POST /api/campaigns/from-brief deve sugerir OfferProfile.

O preview do modo agente resolve a Vertente no registry efetivo da organização.
Nestes testes unitários não há banco real de overlays, então o builder é fixado
no catálogo base para isolar apenas a resolução da intenção comercial.
"""
import asyncio
from types import SimpleNamespace

from src.routes.campaigns import BriefCampaignRequest, create_campaign_from_brief
from tests.test_brief_template_generation import _FakeDB, _patch_chain, _request


def _run(monkeypatch, suggestion):
    from services.prospecting.default_profiles import get_base_registry

    monkeypatch.setattr(
        "services.prospecting.effective_offer_registry.build_effective_registry",
        lambda _db, _org_id: get_base_registry(),
    )
    route_result = {
        "template": {"service_label": "Genérico"},
        "route": "MATCHED",
        "matched_label": "Genérico",
    }
    _patch_chain(
        monkeypatch, suggestion, route_result,
        lambda db, s, seg, org: {"service_label": "Genérico"},
    )
    db = _FakeDB(row=SimpleNamespace(
        id="tmpl-generico", service_label="Genérico", is_active=True,
    ))
    return asyncio.run(create_campaign_from_brief(
        request=_request(),
        body=BriefCampaignRequest(brief="quero vender troféus"),
        db=db,
        _user=SimpleNamespace(id="u1"),
        _org=SimpleNamespace(id="org1"),
    ))


def test_from_brief_sugere_offer_profile_de_trofeus(monkeypatch):
    result = _run(monkeypatch, {
        "target_service": "Troféus",
        "target_segment": "eventos esportivos",
    })
    assert result["offer_profile_key"] == "trophies"
    assert result["offer_profile_label"] == "Troféus Personalizados"
    assert result["offer_resolved_from"] in ("explicit", "vertical")


def test_from_brief_sem_match_devolve_perfil_nulo(monkeypatch):
    result = _run(monkeypatch, {
        "target_service": "Manutenção de elevadores",
        "target_segment": "Condomínios",
    })
    assert result["offer_profile_key"] is None
