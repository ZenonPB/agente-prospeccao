"""Testes do discovery multi-query (docs/melhorias/04).

Cobertura por variedade semântica: a campanha executa várias consultas
Places, deduplica por identidade do negócio e mantém `source_queries`
auditável em cada candidato.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.discovery_multi_query import (  # noqa: E402
    MAX_SEARCH_QUERIES,
    aggregate_multi_query_results,
    expand_search_queries,
)


class _Campaign:
    """Duck-typing da campanha (objeto ou dict)."""

    def __init__(self, search_queries=None, places_query=None):
        self.search_queries = search_queries
        self.places_query = places_query


class TestExpandSearchQueries:
    def test_usa_todas_as_queries_declaradas(self):
        camp = _Campaign(
            search_queries=["clínica de psicologia Araraquara",
                            "psicólogo infantil Araraquara",
                            "  terapia de casal Araraquara  "])
        assert expand_search_queries(camp) == [
            "clínica de psicologia Araraquara",
            "psicólogo infantil Araraquara",
            "terapia de casal Araraquara",
        ]

    def test_ignora_vazias_e_deduplica_preservando_ordem(self):
        camp = _Campaign(search_queries=[
            "Clínica de Psicologia Araraquara", "", "  ",
            "clínica de psicologia araraquara"],
        )
        assert expand_search_queries(camp) == ["Clínica de Psicologia Araraquara"]

    def test_sem_lista_cai_para_places_query_compat(self):
        camp = _Campaign(places_query="fisioterapia Campinas")
        assert expand_search_queries(camp) == ["fisioterapia Campinas"]

    def test_fallback_query_quando_nada_declarado(self):
        camp = _Campaign()
        assert expand_search_queries(camp, fallback_query="empresas") == ["empresas"]

    def test_cap_de_10_consultas(self):
        camp = _Campaign(search_queries=[f"query {i}" for i in range(25)])
        assert len(expand_search_queries(camp)) == MAX_SEARCH_QUERIES

    def test_aceita_dict_de_campanha(self):
        assert expand_search_queries(
            {"search_queries": ["a", "b"], "places_query": "c"}) == ["a", "b"]


class TestAggregateMultiQueryResults:
    def _query(self):
        return {
            "place_id": "ChIJ1",
            "name": "Clínica Bem Estar",
            "category": "health",
        }

    def test_mesmo_place_id_em_duas_queries_produz_um_candidato(self):
        q = self._query()
        merged = aggregate_multi_query_results([
            ("clínica de psicologia", [dict(q)]),
            ("psicólogo infantil", [dict(q, name="Clínica Bem Estar (outro nome)")]),
        ])
        assert len(merged) == 1
        assert merged[0]["place_id"] == "ChIJ1"

    def test_queries_de_subnicho_ficam_associadas_ao_candidato(self):
        q = self._query()
        merged = aggregate_multi_query_results([
            ("clínica de psicologia", [dict(q)]),
            ("psicólogo infantil", [dict(q)]),
            ("terapia de casal", [dict(q)]),
        ])
        cand = merged[0]
        assert cand["source_query"] == "clínica de psicologia"  # primeira
        assert cand["source_queries"] == [
            "clínica de psicologia", "psicólogo infantil", "terapia de casal"]

    def test_candidatos_distintos_nao_se_fundem(self):
        merged = aggregate_multi_query_results([
            ("qi", [{"place_id": "p1", "name": "A"}]),
            ("qj", [{"place_id": "p2", "name": "B"}]),
        ])
        assert len(merged) == 2

    def test_fallback_identidade_por_nome_quando_sem_place_id(self):
        merged = aggregate_multi_query_results([
            ("qa", [{"name": "Oficina Mecânica Silva", "category": "car_repaire"}]),
            ("qb", [{"name": "  oficina mecânica silva  ", "category": "car_repaire"}]),
        ])
        assert len(merged) == 1
        assert merged[0]["source_queries"] == ["qa", "qb"]