"""Testes do Archetype Service (Fase 3 — doc 32).

Seam: `match_archetype(target_service, target_segment)`.
Capacidade: detectar archetype (landing_pages/industrial_erp/b2b_software) por
keywords do serviço, com fallback para 'generic' quando nada bate.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.archetype_service import match_archetype  # noqa: E402


class TestMatchArchetype:
    def test_landing_page_keywords_detecta_landing_pages(self):
        result = match_archetype("Landing Page de Captura para Psicologia")
        assert result["archetype_id"] == "landing_pages"
        assert result["profile_key"] == "web_presence"
        assert result["confidence"] > 0.5

    def test_industrial_keywords_detecta_industrial_erp(self):
        result = match_archetype("ERP industrial metalúrgica")
        assert result["archetype_id"] == "industrial_erp"
        assert result["profile_key"] == "industrial"

    def test_b2b_keywords_detecta_b2b_software(self):
        result = match_archetype("Sistema web sob medida para B2B")
        assert result["archetype_id"] == "b2b_software"
        assert result["profile_key"] == "business_opportunity"

    def test_sem_match_retorna_generic(self):
        result = match_archetype("Consultoria aleatória qualquer")
        assert result["archetype_id"] is None
        assert result["profile_key"] == "generic"
        assert result["confidence"] == 0.0

    def test_service_vazio_e_generic(self):
        result = match_archetype("")
        assert result["profile_key"] == "generic"

    def test_config_prescrito_para_o_perfil(self):
        """Archetype inclui prescoring_config pronto para o pipeline."""
        result = match_archetype("Landing Page de Captura")
        assert "config" in result
        assert "enabled" in result["config"]
        assert "threshold" in result["config"]
        assert "weights" in result["config"]
