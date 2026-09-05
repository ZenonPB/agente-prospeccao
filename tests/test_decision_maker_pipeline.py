"""Testes do Decision Maker Pipeline (Fase 3 — doc 34).

Seam: `run_decision_maker_pipeline(lead_data, profile)`,
       `resolve_target_roles(profile_key)`.
Capacidade: unificar o caminho empresa→cargo-alvo→pessoa→canais→verificação
com auditabilidade (chain + strategy + accessibility).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.decision_maker_pipeline_service import (  # noqa: E402
    run_decision_maker_pipeline,
    resolve_target_roles,
)


class TestResolveTargetRoles:
    def test_industrial_resolve_plant_engineer(self):
        roles = resolve_target_roles("industrial")
        titles = [r["role"] for r in roles]
        assert "plant_engineer" in titles

    def test_cada_role_tem_buyer_type(self):
        roles = resolve_target_roles("web_presence")
        for r in roles:
            assert r["buyer_type"] in ("ECONOMIC_BUYER", "TECHNICAL_BUYER", "CHAMPION")

    def test_perfil_desconhecido_cai_no_generic(self):
        roles = resolve_target_roles("perfil_inexistente")
        assert len(roles) > 0


class TestRunPipeline:
    def test_retorna_target_roles_chain_strategy_accessibility(self):
        result = run_decision_maker_pipeline(
            lead_data={"company_name": "Alpha", "domain": "alpha.com"},
            profile={"profile_key": "industrial"},
        )
        assert "target_roles" in result
        assert "chain_classification" in result
        assert "contact_strategy" in result
        assert "decision_maker_accessibility" in result

    def test_chain_classification_e_dos_dados(self):
        result = run_decision_maker_pipeline(
            lead_data={"company_name": "X", "addresses": [{"name": "X"}]},
            profile={"profile_key": "generic"},
        )
        assert result["chain_classification"] in (
            "INDEPENDENT", "SMALL_CHAIN", "FRANCHISE", "ENTERPRISE", "UNKNOWN",
        )

    def test_accessibility_score_e_0_a_100(self):
        result = run_decision_maker_pipeline(
            lead_data={"company_name": "Y"},
            profile={"profile_key": "generic"},
        )
        score = result["decision_maker_accessibility"]["score"]
        assert 0 <= score <= 100

    def test_strategy_e_por_perfil(self):
        industrial = run_decision_maker_pipeline(
            lead_data={"company_name": "X"},
            profile={"profile_key": "industrial"},
        )
        web = run_decision_maker_pipeline(
            lead_data={"company_name": "X"},
            profile={"profile_key": "web_presence"},
        )
        # Estratégias diferentes por perfil (consolidação §27)
        assert (industrial["contact_strategy"]["provider_order"] !=
                web["contact_strategy"]["provider_order"])
