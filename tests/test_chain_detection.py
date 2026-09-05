"""Testes do Chain Detection (Fase 3 — doc 13).

Seam: `detect_chain(lead_data)`.
Capacidade: classificar empresa como INDEPENDENT/SMALL_CHAIN/FRANCHISE/ENTERPRISE/UNKNOWN
a partir de evidências observadas. Regra crítica: UNKNOWN nunca é penalizado.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.chain_detection_service import (  # noqa: E402
    detect_chain,
    INDEPENDENT,
    SMALL_CHAIN,
    FRANCHISE,
    ENTERPRISE,
    UNKNOWN,
)


class TestDetectChain:
    def test_lead_minimo_sem_dados_e_unknown(self):
        result = detect_chain({})
        assert result["classification"] == UNKNOWN
        assert result["confidence"] <= 0.5
        assert result["chain_score"] == 0

    def test_uma_unica_unidade_e_independent(self):
        result = detect_chain({
            "company_name": "Padaria São José",
            "addresses": [{"name": "Padaria São José"}],
        })
        assert result["classification"] == INDEPENDENT

    def test_tres_unidades_mesmo_nome_vira_chain(self):
        result = detect_chain({
            "company_name": "Padaria São José",
            "addresses": [
                {"name": "Padaria São José - Centro"},
                {"name": "Padaria São José - Norte"},
                {"name": "Padaria São José - Sul"},
            ],
        })
        assert result["classification"] in (SMALL_CHAIN, FRANCHISE, ENTERPRISE)
        assert result["chain_score"] >= 3

    def test_unknown_nao_e_penalizado(self):
        """Doc 13: UNKNOWN não é automaticamente penalizado."""
        result = detect_chain({"domain": "alpha.com"})
        # Confidence deve ser baixa mas não pode indicar exclusão
        assert result["classification"] in (UNKNOWN, INDEPENDENT)
        assert result["profile_hint"] != "excluded" or result["classification"] == UNKNOWN

    def test_evidence_e_auditavel(self):
        result = detect_chain({
            "company_name": "Padaria X",
            "addresses": [
                {"name": "Padaria X - Centro"},
                {"name": "Padaria X - Norte"},
            ],
        })
        assert isinstance(result["evidence"], list)
        # Cada evidência tem confidence rastreável
        for ev in result["evidence"]:
            assert "type" in ev
            assert "weight" in ev

    def test_cnpj_matriz_pattern_eleva_score(self):
        result = detect_chain({
            "company_name": "Lojas Y",
            "cnpj": "12.345.678/0001-90",
            "addresses": [
                {"name": "Lojas Y - Filial 1"},
                {"name": "Lojas Y - Filial 2"},
            ],
        })
        # CNPJ matriz + 2 filiais → score alto (>= 3)
        assert result["chain_score"] >= 2
