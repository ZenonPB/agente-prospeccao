"""Verificação assíncrona de contato (I/O) separada da resolução de identidade.

O `ContactVerification` legado em `decision_maker_resolution.py` é síncrono e
abrigava adaptação com thread para o `EmailVerificationService` assíncrono.
Este módulo é o seam de I/O: recebe o serviço de e-mail por injeção e nunca
abre thread nem toca em rede por conta própria.
"""
from typing import Any, Dict, Optional


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
        if self._email_service is None:
            return {"email_verified": False, "verification_status": "pending_real_check"}
        try:
            result = await self._email_service.verify_email(email)
        except Exception:
            return {"email_verified": False, "verification_status": "pending_real_check"}
        verified = bool(result.get("verified")) if isinstance(result, dict) else False
        return {
            "email_verified": verified,
            "verification_status": "verified" if verified else "pending_real_check",
        }
