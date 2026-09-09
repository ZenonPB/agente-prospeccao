"""Verificação assíncrona de contato (I/O) separada da resolução de identidade.

O `ContactVerification` legado em `decision_maker_resolution.py` foi migrado
(onda 2): o resolver síncrono não abre mais thread nem toca em rede. Este
módulo é o seam de I/O: recebe o serviço de e-mail por injeção e nunca
abre thread nem toca em rede por conta própria.
"""
import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class ContactVerifier:
    """Verifica entregabilidade de e-mail de forma assíncrona e injetável."""

    def __init__(self, email_service: Optional[Any] = None) -> None:
        """Guarda o serviço de verificação sem criá-lo de forma implícita.

        Args:
            email_service: objeto com `verify_email(email)` assíncrono.
                Quando ausente, a verificação marca pendência real em vez
                de falhar ou inventar resultado.
        """
        self._email_service = email_service

    @staticmethod
    def _is_heuristic_source(source: Optional[str]) -> bool:
        """Indica fonte heurística, que nunca conta como verificada."""
        return (source or "") == "heuristic" or "heuristic" in (source or "")

    async def verify_email(self, person: Any) -> Dict[str, Any]:
        """Confirma o e-mail via serviço injetado, sem thread.

        Args:
            person: contato com `email` e `source`.

        Returns:
            Dicionário com `email_verified` e `verification_status`
            (`verified`, `pending_real_check` ou `skipped_heuristic`).
        """
        email = getattr(person, "email", None)
        source = getattr(person, "source", None)
        if not email or self._is_heuristic_source(source):
            return {"email_verified": False, "verification_status": "skipped_heuristic"}
        raw_data = getattr(person, "raw_data", None)
        if isinstance(raw_data, dict) and self._is_heuristic_source(raw_data.get("email_source")):
            return {"email_verified": False, "verification_status": "skipped_heuristic"}
        if self._email_service is None:
            return {"email_verified": False, "verification_status": "pending_real_check"}
        try:
            result = await self._email_service.verify_email(email)
        except Exception as exc:
            logger.warning("Falha na verificação assíncrona do e-mail: %s", exc)
            return {
                "email_verified": False,
                "verification_status": "pending_real_check",
                "reason": "verification_error",
            }
        verified = bool(result.get("verified")) if isinstance(result, dict) else False
        return {
            "email_verified": verified,
            "verification_status": "verified" if verified else "pending_real_check",
            "reason": result.get("reason") if isinstance(result, dict) else "invalid_verifier_response",
            "mx": result.get("mx") if isinstance(result, dict) else None,
        }
