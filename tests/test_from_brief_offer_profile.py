"""Regressão do F-03: POST /api/campaigns/from-brief deve sugerir OfferProfile.

O preview do modo agente resolvia só o template de scoring e nunca o perfil
da oferta — a campanha nascia sem `offer_profile_key` e o pipeline caía no
fallback legado. O brief precisa devolver a oferta resolvida para a UI
confirmar e enviar no create.
"""
import asyncio
from types import SimpleNamespace

from starlette.requests import Request

from src.routes.campaigns import BriefCampaignRequest, create_campaign_from_brief
from tests.test_brief_template_generation import _FakeDB, _patch_chain, _request


def _run(monkeypatch, suggestion):
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
