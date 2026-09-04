"""Testes do capability registry e do planner de enrichment (docs 21 e 08)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.enrichment_capability_registry import (  # noqa: E402
    CAPABILITIES,
    DEFAULT_ENRICHMENT_STEPS,
    plan_enrichment_run,
    resolve_enrichment_steps,
)
from services.template_router import _serialize  # noqa: E402


class TestCapabilityRegistry:
    def test_produces_e_cost_description_presentes(self):
        for step, cap in CAPABILITIES.items():
            assert cap["produces"], f"{step} sem signals declarados"
            assert cap["cost"] in ("low", "medium", "high")
            assert isinstance(cap["description"], str)

    def test_produces_keys_sao_signal_keys_validos(self):
        import services.signal_registry as sr
        valid = {
            getattr(sr.SignalKey, n) for n in dir(sr.SignalKey)
            if n.isupper() and not n.startswith("_")
        }
        for step, cap in CAPABILITIES.items():
            for k in cap["produces"]:
                assert k in valid, f"{step} product {k!r} não registrado em SignalKey"

    def test_technical_site_nao_produce_hasp_instagram(self):
        """Instagram vem do discovery/social, NÃO da auditoria técnica"""
        from services.signal_registry import SignalKey
        assert SignalKey.HAS_INSTAGRAM not in CAPABILITIES["technical_site"]["produces"]

    def test_ordem_da_oferta_e_respeitada(self):
        tmpl = {"enrichment_steps": ["cnpj_receita", "technical_site", "business_social"]}
        plan = plan_enrichment_run(tmpl, {"has_website": True, "has_cnpj": True})
        assert plan["runnable"] == ["cnpj_receita", "technical_site", "business_social"]

    def test_engenharia_sem_site_nao_audita_seo_por_padrao(self):
        plan = plan_enrichment_run(None, {"has_website": False, "has_cnpj": True})
        assert "technical_site" not in plan["runnable"]
        skipped = {s["step"]: s["reason"] for s in plan["skipped"]}
        assert "pré-condição" in skipped["technical_site"]

    def test_landing_executa_sem_consulta_cadastral(self):
        tmpl = {"enrichment_steps": ["technical_site", "business_social"]}
        plan = plan_enrichment_run(tmpl, {"has_website": True, "has_cnpj": False})
        assert "cnpj_receita" not in plan["runnable"]
        assert plan["runnable"] == ["technical_site", "business_social"]

    def test_skip_declarado_pela_oferta(self):
        tmpl = {"enrichment_steps": ["technical_site", "cnpj_receita"],
                "enrichment_strategy": {"skip": ["cnpj_receita"]}}
        plan = plan_enrichment_run(tmpl, {"has_website": True, "has_cnpj": True})
        assert plan["runnable"] == ["technical_site"]
        assert plan["skipped"][0]["step"] == "cnpj_receita"

    def test_stop_after_corta_execucao_declaradamente(self):
        tmpl = {"enrichment_strategy": {"stop_after": "cnpj_receita"}}
        plan = plan_enrichment_run(tmpl, {"has_website": True, "has_cnpj": True})
        assert plan["runnable"] == ["technical_site", "cnpj_receita"]
        reasons = " ".join(s["reason"] for s in plan["skipped"])
        assert "stop_after" in reasons

    def test_stop_after_inexistente_alerta(self, caplog):
        """stop_after num step que nem a oferta declara não corta nada e não
                pode passar despercebido (intenção ambígua)"""
        _ = plan_enrichment_run(
            {"enrichment_strategy": {"stop_after": "newsletter_signup"}},
            {"has_website": True, "has_cnpj": True},
        )
        assert any("newsletter_signup" in r.getMessage() for r in caplog.records)

    def test_plano_sem_template_usa_defaults(self):
        plan = plan_enrichment_run(None, {"has_website": True, "has_cnpj": True})
        assert plan["runnable"] == DEFAULT_ENRICHMENT_STEPS
        assert plan["skipped"] == []

    def test_estrategia_invalida_nao_quebra_o_plano(self):
        tmpl = {"enrichment_strategy": "valor-invalido"}
        plan = plan_enrichment_run(tmpl, {"has_website": True, "has_cnpj": True})
        assert plan["runnable"] == DEFAULT_ENRICHMENT_STEPS

    def test_resolve_enrichment_steps_compat_flags(self):
        assert resolve_enrichment_steps(None) == DEFAULT_ENRICHMENT_STEPS
        assert resolve_enrichment_steps({}) == DEFAULT_ENRICHMENT_STEPS

    def test_resolve_enrichment_steps_alerta_key_desconhecida(self, caplog):
        """Capability declarada mas ainda não registrada NÃO pode sumir em silêncio"""
        resolve_enrichment_steps({
            "enrichment_steps": ["technical_site", "news", "procurement"],
        })
        assert any(
            "news" in r.getMessage() and "registrada" in r.getMessage()
            for r in caplog.records
        )


class TestTemplateSerialization:
    def _tmpl(self, **kw):
        from datetime import datetime
        from database.models import CampaignScoringTemplate
        return CampaignScoringTemplate(service_label="T", created_at=datetime.now(), **kw)

    def test_serialize_passa_prescoring_config_e_strategy(self):
        """Bug da fase 1: prescoring_config era perdido na serialização."""
        tmpl = self._tmpl(
            prescoring_config={"enabled": True, "profile": "web_presence",
                               "threshold": 45},
            enrichment_strategy={"skip": ["cnpj_receita"]},
        )
        data = _serialize(tmpl)
        assert data["prescoring_config"]["threshold"] == 45
        assert data["enrichment_strategy"] == {"skip": ["cnpj_receita"]}

    def test_serialize_sem_configs_fica_none(self):
        data = _serialize(self._tmpl())
        assert data["prescoring_config"] is None
        assert data["enrichment_strategy"] is None


def test_modulo_reexporta_step_constants():
    """#6: STEP_* tem fonte única (capability registry)."""
    from services.prospecting_profile_service import (
        STEP_BUSINESS_SOCIAL, STEP_CNPJ_RECEITA, STEP_TECHNICAL_SITE)
    from services.enrichment_capability_registry import (
        STEP_BUSINESS_SOCIAL as R_BUS, STEP_CNPJ_RECEITA as R_CNPJ,
        STEP_TECHNICAL_SITE as R_SITE)
    assert STEP_TECHNICAL_SITE is R_SITE
    assert STEP_CNPJ_RECEITA is R_CNPJ
    assert STEP_BUSINESS_SOCIAL is R_BUS
