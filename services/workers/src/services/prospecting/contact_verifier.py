"""Verificação assíncrona de contato separada da resolução de identidade."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)
MAX_EMAIL_HISTORY = 30


class ContactVerifier:
    """Verifica e-mail por serviço injetado e mantém histórico auditável."""

    def __init__(
        self,
        email_service: Optional[Any] = None,
        *,
        enable_catchall_probe: bool = False,
    ) -> None:
        self._email_service = email_service
        self._enable_catchall_probe = bool(enable_catchall_probe)

    @staticmethod
    def _is_heuristic_source(source: Optional[str]) -> bool:
        return (source or "") == "heuristic" or "heuristic" in (source or "")

    @staticmethod
    def _append_history(person: Any, email: str, result: Dict[str, Any]) -> None:
        raw = deepcopy(getattr(person, "raw_data", None) or {})
        history = [item for item in raw.get("email_verification_history", []) if isinstance(item, dict)]
        record = {
            "email": email.strip().lower(),
            "status": result.get("verification_status") or result.get("status"),
            "email_verified": bool(result.get("email_verified")),
            "confidence": int(result.get("confidence") or 0),
            "reason": result.get("reason"),
            "catch_all": result.get("catch_all"),
            "mx": result.get("mx"),
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        if history and history[-1].get("email") == record["email"] and history[-1].get("status") == record["status"]:
            history[-1] = record
        else:
            history.append(record)
        raw["email_verification_history"] = history[-MAX_EMAIL_HISTORY:]
        setattr(person, "raw_data", raw)

    @staticmethod
    def latest_verified_at(person: Any) -> str | None:
        raw = getattr(person, "raw_data", None)
        if not isinstance(raw, dict):
            return None
        history = raw.get("email_verification_history")
        if isinstance(history, list) and history and isinstance(history[-1], dict):
            return history[-1].get("observed_at")
        value = getattr(person, "email_verified_at", None) or getattr(person, "last_verified_at", None)
        return value.isoformat() if hasattr(value, "isoformat") else value

    async def verify_email(self, person: Any) -> Dict[str, Any]:
        email = getattr(person, "email", None)
        source = getattr(person, "source", None)
        raw_data = getattr(person, "raw_data", None)
        if not email or self._is_heuristic_source(source) or (
            isinstance(raw_data, dict) and self._is_heuristic_source(raw_data.get("email_source"))
        ):
            return {"email_verified": False, "verification_status": "skipped_heuristic", "confidence": 0}
        if self._email_service is None:
            return {"email_verified": False, "verification_status": "pending_real_check", "confidence": 0}

        try:
            if hasattr(self._email_service, "verify_email_v2"):
                verified = await self._email_service.verify_email_v2(
                    email,
                    enable_catchall_probe=self._enable_catchall_probe,
                )
                result = {
                    "email_verified": bool(verified.get("verified")),
                    "verification_status": verified.get("status") or "unknown",
                    "reason": verified.get("reason"),
                    "mx": verified.get("mx"),
                    "confidence": int(verified.get("confidence") or 0),
                    "catch_all": verified.get("catch_all"),
                    "auto_send_eligible": bool(verified.get("auto_send_eligible")),
                }
            else:
                verified = await self._email_service.verify_email(email)
                ok = bool(verified.get("verified")) if isinstance(verified, dict) else False
                result = {
                    "email_verified": ok,
                    "verification_status": "verified" if ok else "pending_real_check",
                    "reason": verified.get("reason") if isinstance(verified, dict) else "invalid_verifier_response",
                    "mx": verified.get("mx") if isinstance(verified, dict) else None,
                    "confidence": 80 if ok else 20,
                    "catch_all": None,
                    "auto_send_eligible": ok,
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha na verificação assíncrona do e-mail: %s", exc)
            result = {
                "email_verified": False,
                "verification_status": "pending_real_check",
                "reason": "verification_error",
                "confidence": 0,
                "catch_all": None,
                "auto_send_eligible": False,
            }

        self._append_history(person, email, result)
        return result
