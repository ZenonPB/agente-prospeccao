"""Provenance consolidada no descarte do pre-scoring (P1.2).

Um candidato rejeitado precisa ser rastreável: o registro de auditoria
carrega providers, consultas e ids do candidato, da mesma forma que o Lead
selecionado, para permitir revisão humana e recalibração do gate.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "workers" / "src"))

from services.candidate_pre_scoring_service import CandidatePreScoringService  # noqa: E402


class TestDiscardRecordProvenance:
    def _service(self):
        return CandidatePreScoringService()

    def test_descarte_reutiliza_provenance_do_executor(self):
        """Quando o item passou pelo dedup, a provenance consolidada é preservada."""
        item = {
            "place_id": "ChIJxyz",
            "name": "Metalúrgica Alfa",
            "provenance": {
                "providers": ["google_places"],
                "provider_queries": ["metalurgia em Campinas"],
                "provider_candidate_ids": ["ChIJxyz"],
            },
        }
        record = self._service()._discard_record(
            item, {"signals": [], "discovery_score": 10},
            {"profile_key": "generic"}, {"threshold": 40},
            "below_threshold", {},
        )
        assert record["provenance"] == {
            "providers": ["google_places"],
            "provider_queries": ["metalurgia em Campinas"],
            "provider_candidate_ids": ["ChIJxyz"],
        }

    def test_descarte_deriva_provenance_do_item_bruto(self):
        """Item sem provenance consolidada deriva de provider/provider_query."""
        item = {
            "place_id": "abc",
            "name": "Oficina Beta",
            "provider": "google_places",
            "provider_query": "oficinas em Sorocaba",
        }
        record = self._service()._discard_record(
            item, {"signals": [], "discovery_score": 5},
            {"profile_key": "generic"}, {"threshold": 40},
            "below_threshold", {},
        )
        assert record["provenance"] == {
            "providers": ["google_places"],
            "provider_queries": ["oficinas em Sorocaba"],
            "provider_candidate_ids": [],
        }

    def test_descarte_sem_fonte_tem_provenance_vazia(self):
        """Sem fonte nenhuma, provenance vazia explícita (não None nem erro)."""
        record = self._service()._discard_record(
            {"name": "Sem Fonte"}, {"signals": [], "discovery_score": 0},
            {"profile_key": "generic"}, {"threshold": 40},
            "insufficient_data", {},
        )
        assert record["provenance"] == {
            "providers": [],
            "provider_queries": [],
            "provider_candidate_ids": [],
        }

    def test_reason_preservado_no_registro(self):
        record = self._service()._discard_record(
            {"place_id": "x", "name": "A"}, {"signals": [], "discovery_score": 50},
            {"profile_key": "generic"}, {"threshold": 40},
            "top_k_cut", {"organization_id": "org-1", "campaign_id": "camp-1"},
        )
        assert record["reason"] == "top_k_cut"
        assert record["organization_id"] == "org-1"