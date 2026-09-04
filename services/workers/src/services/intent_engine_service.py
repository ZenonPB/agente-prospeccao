"""Intent Engine (Fase 3 — #24): detecta eventos recentes de compra/intenção.

Seam: SignalRegistry (fatos observados) → IntentEngine (inferência temporal)
Contratos: cada evento tem timestamp, fonte, confiança, evidência.
Não produz fatos — só marca a possibilidade de necessidade agora.
"""
from typing import Any, Dict, List, Optional
from services.signal_registry import SignalKey

class IntentEngine:
    """Interface profunda: detect_events recebe sinais observados (FACT)
    e retorna intent_signals (INFERENCE/HYPOTHESIS com evidência)."""
    
    INTENT_KEYS = {
        "HIRING": "horario_abertura_vagas",
        "NEW_BRANCH": "abertura_filial",
        "NEW_EQUIPMENT": "novo_equipamento",
        "EXPANDING": "expansao",
        "NEW_PRODUCT": "novo_produto",
    }
    
    def detect_events(self, signals: List[Dict], profile: Optional[Dict] = None) -> List[Dict]:
        results = []
        for s in signals or []:
            key = s.get("key")
            if key in self.INTENT_KEYS and s.get("value"):
                results.append({
                    "key": key,
                    "status": "INFERENCE",  # derivado de facts observados
                    "confidence": float(s.get("confidence") or 0.7),
                    "observed_at": s.get("observed_at"),
                    "evidence_refs": [s.get("evidence")],
                    "source": s.get("source"),
                })
        return results
