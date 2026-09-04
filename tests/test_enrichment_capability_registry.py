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
    def test_toda_capability_declara_sinais_que_produz(self):
        for step, cap in CAPABILITIES.items():
            assert cap["produces"], f"{step} sem signals declarados"
            assert cap["cost"] in ("low", "medium", "high")
            assert isinstance(cap["description"], str)

    def test_ordem_da_oferta_e_respeitada(self):
        tmpl = {"enrichment_steps": ["cnpj_receita", "technical_site", "business_social"]}
        plan = plan_enrichment_run(
            tmpl, {"has_website": True, "has_cnpj": True})
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

    def test_plano_sem_template_usa_defaults(self):
        plan = plan_enrichment_run(None, {"has_website": True, "has_cnpj": True})
        assert plan["runnable"] == DEFAULT_ENRICHMENT_STEPS
        assert plan["skipped"] == []

    def test_estrategia_invalida_nao_quebra_o_plano(self):
        tmpl = {"enrichment_strategy": "valor-invalido"}
        plan = plan_enrichment_run(tmpl, {"has_website": True, "has_cnpj": True})
        assert plan["runnable"] == DEFAULT_ENRICHMENT_STEPS

    def test_resolve_enrichment_steps_compat_flags(self):
        # API antiga preservada (re-export com mesmo comportamento).
        assert resolve_enrichment_steps(None) == DEFAULT_ENRICHMENT_STEPS
        assert resolve_enrichment_steps({}) == DEFAULT_ENRICHMENT_STEPS


class TestTemplateSerialization:
    def _tmpl(self, **kw):
        from datetime import datetime
        from database.models import CampaignScoringTemplate
        return CampaignScoringTemplate(service_label="T", created_at=datetime.now(), **kw)

    def test_serialize_passa_prescoring_config_e_strategy(self):
        """Bug da fase 1: prescoring_config era perdido na serialização — o
        gate nunca leria a config declarada em templates reais."""
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
