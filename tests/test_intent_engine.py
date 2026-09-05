"""Testes do Intent Engine (Fase 3 — doc 24).

Seam: `IntentEngine.detect_events()` / `score_and_trigger()`.
Capacidade: transformar sinais observados em eventos de intenção com confiança e
score agregado, distinguindo presença real (HIRING/NEW_BRANCH com value=True)
de ausência (UNKNOWN). Não produz fatos — apenas classifica.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.intent_engine_service import IntentEngine  # noqa: E402


class TestDetectEvents:
    def test_hiring_signal_vira_evento_com_confidence(self):
        ie = IntentEngine()
        events = ie.detect_events([
            {"key": "HIRING", "value": True, "confidence": 0.9,
             "evidence": "vaga de projetista mecânico"}
        ])
        assert len(events) == 1
        assert events[0]["key"] == "HIRING"
        assert events[0]["status"] == "INFERENCE"
        assert events[0]["confidence"] == 0.9
        assert "vaga" in str(events[0]["evidence_refs"])

    def test_sinal_sem_chave_conhecida_e_descartado(self):
        ie = IntentEngine()
        events = ie.detect_events([
            {"key": "UNKNOWN_KEY", "value": True, "confidence": 0.9, "evidence": "x"}
        ])
        assert events == []

    def test_sinal_sem_value_e_descartado(self):
        ie = IntentEngine()
        events = ie.detect_events([
            {"key": "HIRING", "value": False, "confidence": 0.9, "evidence": "x"}
        ])
        assert events == []

    def test_lista_vazia_retorna_lista_vazia(self):
        ie = IntentEngine()
        assert ie.detect_events([]) == []


class TestScoreAndTrigger:
    def test_um_evento_alta_confianca_da_intent_score_alto(self):
        ie = IntentEngine()
        result = ie.score_and_trigger([
            {"key": "HIRING", "status": "INFERENCE", "confidence": 0.9,
             "evidence_refs": ["vaga"]}
        ])
        assert result["intent_score"] == 90
        assert result["buying_trigger"] == "HIRING"
        assert "HIRING" in result["why_now"]

    def test_multiplos_eventos_agregam_score(self):
        ie = IntentEngine()
        result = ie.score_and_trigger([
            {"key": "HIRING", "status": "INFERENCE", "confidence": 0.8,
             "evidence_refs": ["vaga"]},
            {"key": "NEW_BRANCH", "status": "INFERENCE", "confidence": 0.7,
             "evidence_refs": ["filial"]},
        ])
        # media de 80 e 70 = 75
        assert 70 <= result["intent_score"] <= 80
        assert "HIRING" in result["buying_trigger"]
        assert "NEW_BRANCH" in result["buying_trigger"]

    def test_sem_eventos_intent_score_e_zero(self):
        ie = IntentEngine()
        result = ie.score_and_trigger([])
        assert result["intent_score"] == 0
        assert result["buying_trigger"] is None
        assert result["why_now"] is None
