"""Testes do Universal Prospecting Questions (Fase 3 — doc 18).

Seam: `build_universal_questions(profile_key, lead_context)`,
       `validate_answer_coverage(answers)`,
       `discovery_questions_for(profile_key)`.
Capacidade: declarar 6 perguntas universais do agente (icp/need/buying_power/
timing/decision_maker/outreach) e perguntas de qualificação por vertical.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.universal_prospecting_questions_service import (  # noqa: E402
    build_universal_questions,
    validate_answer_coverage,
    discovery_questions_for,
)


class TestBuildUniversalQuestions:
    def test_retorna_6_perguntas(self):
        q = build_universal_questions("industrial")
        assert len(q["questions"]) == 6

    def test_perguntas_tem_layer(self):
        q = build_universal_questions("generic")
        layers = [item["layer"] for item in q["questions"]]
        assert layers == ["icp", "need", "buying_power", "timing", "decision_maker", "outreach"]

    def test_perguntas_sao_strings(self):
        q = build_universal_questions("web_presence")
        for item in q["questions"]:
            assert isinstance(item["question"], str)
            assert len(item["question"]) > 0

    def test_lead_context_anexado(self):
        ctx = {"company_name": "X"}
        q = build_universal_questions("generic", lead_context=ctx)
        assert q["lead_context"] == ctx


class TestValidateAnswerCoverage:
    def test_todas_preenchidas_e_complete(self):
        result = validate_answer_coverage(["a", "b", "c", "d", "e", "f"])
        assert result["complete"] is True
        assert result["coverage"] == 100

    def test_algumas_vazias_e_incomplete(self):
        result = validate_answer_coverage(["a", None, "c", "", [], {}])
        # "a" e "c" são preenchidos; None/""/[]/{} são vazios
        assert result["answered"] == 2
        assert result["complete"] is False
        assert result["coverage"] == round(2/6*100)


class TestDiscoveryQuestions:
    def test_industrial_tem_3_perguntas(self):
        d = discovery_questions_for("industrial")
        assert len(d["discovery_questions"]) == 3

    def test_perfil_desconhecido_cai_no_generic(self):
        d = discovery_questions_for("perfil_inexistente")
        # Cai no generic mas com profile_key preservado
        assert d["profile_key"] == "perfil_inexistente"
        assert len(d["discovery_questions"]) > 0

    def test_perguntas_diferentes_por_perfil(self):
        web = discovery_questions_for("web_presence")["discovery_questions"]
        ind = discovery_questions_for("industrial")["discovery_questions"]
        assert web != ind
