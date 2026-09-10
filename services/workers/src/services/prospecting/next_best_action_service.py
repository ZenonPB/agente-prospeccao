"""Recomendação determinística da próxima ação comercial.

O serviço recomenda, mas não envia mensagens nem altera o lead. Isso mantém o
humano no loop e permite que a API persista a decisão posteriormente.
"""

from typing import Any, Dict, List, Optional


class NextBestActionService:
    """Calcula uma ação explicável a partir do estado atual do lead."""

    def recommend(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Retorna ação, motivo, confiança, evidências e oferta prioritária.

        Args:
            lead_data: Snapshot serializável do lead e suas oportunidades.
                Aceita ``routability_type`` (classificação persistida do
                contato: ``DIRECT_CONTACT``, ``ROUTABLE_CONTACT``,
                ``INSTITUTIONAL``, ``UNKNOWN`` ou ``UNREACHABLE``).

        Returns:
            Recomendação sem efeitos colaterais, compatível com persistência JSON.
        """
        offer_key = self._top_offer(lead_data.get("opportunities"))
        status = str(lead_data.get("status") or "").upper()
        verification = str(lead_data.get("verification_status") or "").lower()
        routability = str(lead_data.get("routability_type") or "").upper()
        evidence: List[str] = []

        if lead_data.get("opt_out") or status in {"PERDIDO", "FECHADO", "CLOSED"}:
            return self._build("STOP", "lead_blocked", 1.0, evidence, offer_key)
        if verification in {"needs_review", "ambiguous"}:
            return self._build("REVIEW_DECISION_MAKER", "identity_needs_review", 0.95, ["verification_status"], offer_key)
        if lead_data.get("has_verified_email") or lead_data.get("email_verified"):
            evidence.append("verified_email")
            if status in {"QUALIFICADO", "CONTATADO", "ANALISADO"}:
                evidence.append("qualified_or_active_lead")
                return self._build("START_EMAIL_CADENCE", "verified_email_and_active_opportunity", 0.9, evidence, offer_key)
        if routability:
            return self._by_routability(routability, lead_data, offer_key)
        # Legado (sem classificação persistida): mantém o comportamento
        # anterior enquanto os contatos antigos não tiverem routability_type.
        if lead_data.get("routable") and lead_data.get("phone"):
            return self._build("CALL", "routable_phone_contact", 0.78, ["routable", "phone"], offer_key)
        if lead_data.get("has_primary_contact") or lead_data.get("has_contact"):
            return self._build("RESEARCH", "contact_requires_verification", 0.7, ["contact_found"], offer_key)
        return self._build("RE_ENRICH", "missing_actionable_contact", 0.82, ["no_actionable_contact"], offer_key)

    @staticmethod
    def _by_routability(
        routability: str,
        lead_data: Dict[str, Any],
        offer_key: Optional[str],
    ) -> Dict[str, Any]:
        """Distingue a ação pelo tipo de roteabilidade persistido no contato.

        - ``DIRECT_CONTACT``: telefone direto da pessoa → ligar.
        - ``ROUTABLE_CONTACT``: PABX + pessoa-alvo identificada → ligar
          (roteável pela recepção, com extension/nome na evidência).
        - ``INSTITUTIONAL``: telefone genérico — nome + departamento podem
          bastar para ação humana (consultor liga pela recepção).
        - ``UNKNOWN``/``UNREACHABLE``: sem canal acionável → enriquecer de novo.
        """
        if routability in {"DIRECT_CONTACT", "ROUTABLE_CONTACT"} and lead_data.get("phone"):
            if routability == "DIRECT_CONTACT":
                return NextBestActionService._build(
                    "CALL", "direct_phone_contact", 0.8, ["routability_type", "phone"], offer_key,
                )
            return NextBestActionService._build(
                "CALL", "pabx_with_target_person", 0.78, ["routability_type", "pabx", "phone"], offer_key,
            )
        if routability in {"DIRECT_CONTACT", "ROUTABLE_CONTACT"}:
            return NextBestActionService._build(
                "RESEARCH", "routable_type_without_phone", 0.6, ["routability_type"], offer_key,
            )
        if routability == "INSTITUTIONAL":
            return NextBestActionService._build(
                "RESEARCH", "institutional_phone_requires_reception", 0.65, ["routability_type"], offer_key,
            )
        return NextBestActionService._build(
            "RE_ENRICH", "contact_unreachable", 0.85, ["routability_type"], offer_key,
        )


    @staticmethod
    def _top_offer(opportunities: Any) -> Optional[str]:
        """Escolhe a oportunidade de maior score sem inventar oferta."""
        if not isinstance(opportunities, list):
            return None
        candidates = [item for item in opportunities if isinstance(item, dict) and item.get("offer_key")]
        if not candidates:
            return None
        return max(candidates, key=lambda item: float(item.get("score") or item.get("overall") or 0))["offer_key"]

    @staticmethod
    def _build(
        action: str,
        reason: str,
        confidence: float,
        evidence: List[str],
        offer_key: Optional[str],
    ) -> Dict[str, Any]:
        """Monta o contrato de saída da recomendação."""
        result: Dict[str, Any] = {
            "action": action,
            "why": reason,
            "confidence": confidence,
            "evidence": evidence,
            "deadline": None,
            "priority": "HIGH" if confidence >= 0.85 else "MEDIUM",
        }
        if offer_key:
            result["offer_key"] = offer_key
        return result