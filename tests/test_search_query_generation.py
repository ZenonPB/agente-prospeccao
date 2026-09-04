"""Testes do Search Query Generation (Fase 3 — doc 05).

Seam: `generate_queries(service, segment, city, state, profile_key, ...)`.
Capacidade: gerar queries de descoberta (LLM opcional com fallback determinístico),
com dedup e limite configurável.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.search_query_generation_service import generate_queries  # noqa: E402


class TestGenerateQueries:
    def test_basico_sem_llm_retorna_queries(self):
        result = generate_queries(
            service="Landing Page",
            segment="psicologia",
            city="Araraquara",
            state="SP",
            profile_key="web_presence",
        )
        assert "queries" in result
        assert len(result["queries"]) > 0
        assert result["used_llm"] is False
        assert "Landing Page" in result["queries"][0] or "psicologia" in result["queries"][0]

    def test_max_queries_e_respeitado(self):
        result = generate_queries(
            service="X", segment="Y", city="Z",
            max_queries=2, profile_key="generic",
        )
        assert len(result["queries"]) <= 2

    def test_dedup_case_insensitive(self):
        result = generate_queries(
            service="X", segment="Y", city="Z",
            profile_key="generic", max_queries=10,
        )
        lowered = [q.lower() for q in result["queries"]]
        assert len(lowloaded := set(lowered)) == len(lowered), "Queries duplicadas após dedup"

    def test_industrial_gera_queries_distintas(self):
        result = generate_queries(
            service="ERP", segment="metalúrgica", city="São Carlos",
            profile_key="industrial", max_queries=5,
        )
        assert any("industrial" in q.lower() or "metal" in q.lower() for q in result["queries"])

    def test_llm_expander_e_usado_quando_fornecido(self):
        def mock_llm(**kwargs):
            return ["mock query 1", "mock query 2"]
        result = generate_queries(
            service="X", segment="Y", city="Z",
            profile_key="generic",
            llm_expander=mock_llm,
        )
        assert result["used_llm"] is True
        assert "mock query 1" in result["queries"]

    def test_llm_quebrado_cai_no_deterministico(self):
        def broken_llm(**kwargs):
            raise RuntimeError("LLM offline")
        result = generate_queries(
            service="X", segment="Y", city="Z",
            profile_key="generic",
            llm_expander=broken_llm,
        )
        # Fallback determinístico é aplicado
        assert result["used_llm"] is False
        assert len(result["queries"]) > 0
