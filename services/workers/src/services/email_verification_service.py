"""Verificação conservadora de e-mail com histórico e catch-all opt-in.

Sintaxe e MX validam o domínio, não a existência da caixa individual. O probe
SMTP opcional detecta comportamento catch-all, mas nunca promove sozinho um
endereço específico a verificado.
"""
from __future__ import annotations

import asyncio
import logging
import re
import smtplib
import uuid
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
DISPOSABLE_DOMAINS: frozenset = frozenset({
    "mailinator.com", "maildrop.cc", "10minutemail.com", "guerrillamail.com",
    "sharklasers.com", "temp-mail.org", "throwawaymail.com", "getnada.com",
    "yopmail.com", "mailnesia.com", "mailcatch.com", "trashmail.com",
    "fakeinbox.com", "mytemp.email", "dispostable.com", "tempmail.com.br",
    "temporarymail.com", "mailnator.com", "emailondeck.com", "spam4.me",
})
DOH_URL = "https://cloudflare-dns.com/dns-query"
DOH_HEADERS = {"Accept": "application/dns-json"}
MX_RRTYPE = 15


def is_valid_email_syntax(email: Optional[str]) -> bool:
    return bool(email and _EMAIL_RE.match(email.strip()))


def _extract_domain(email: str) -> str:
    return email.strip().lower().rsplit("@", 1)[-1]


class EmailVerificationService:
    """Classifica evidência de domínio sem inventar verificação de mailbox."""

    def __init__(self) -> None:
        self._mx_cache: Dict[str, Optional[List[str]]] = {}

    async def _lookup_mx(self, client: httpx.AsyncClient, domain: str) -> Optional[List[str]]:
        if domain in self._mx_cache:
            return self._mx_cache[domain]
        try:
            resp = await client.get(
                DOH_URL,
                params={"name": domain, "type": "MX"},
                headers=DOH_HEADERS,
            )
            if resp.status_code != 200:
                self._mx_cache[domain] = None
                return None
            payload = resp.json()
            answers = [
                a.get("data", "")
                for a in payload.get("Answer", [])
                if a.get("type") == MX_RRTYPE and a.get("data")
            ]
            result = answers or None
            self._mx_cache[domain] = result
            return result
        except Exception as exc:  # noqa: BLE001
            logger.debug("Erro ao consultar MX de %s: %s", domain, exc)
            self._mx_cache[domain] = None
            return None

    async def verify_email(
        self,
        email: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Valida sintaxe e capacidade de e-mail do domínio, não a caixa."""
        if not is_valid_email_syntax(email):
            return {"verified": False, "domain_valid": False, "mx": None, "reason": "syntax_invalid"}
        domain = _extract_domain(email)
        if domain in DISPOSABLE_DOMAINS:
            return {"verified": False, "domain_valid": False, "mx": None, "reason": "disposable_domain"}

        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=10.0, follow_redirects=False)
        try:
            mx = await self._lookup_mx(client, domain)
        finally:
            if own_client and client is not None:
                await client.aclose()
        if mx is None:
            return {"verified": False, "domain_valid": False, "mx": None, "reason": "no_mx_or_dns_unavailable"}
        return {"verified": False, "domain_valid": True, "mx": mx[0], "reason": "mx_present"}

    @staticmethod
    def probe_smtp_catchall_sync(domain: str, mx_host: str) -> Dict[str, Any]:
        """Testa somente comportamento catch-all; não confirma a caixa alvo."""
        clean_mx = mx_host.split()[-1].rstrip(".")
        random_email = f"probe_check_{uuid.uuid4().hex[:10]}@{domain}"
        try:
            with smtplib.SMTP(clean_mx, port=25, timeout=5) as server:
                server.helo("verify.prospeccao.b2b")
                server.mail("noreply@verify.prospeccao.b2b")
                code, _ = server.rcpt(random_email)
                return {"is_catchall": code == 250, "code": code, "probed": True}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Probe SMTP catch-all falhou para %s: %s", domain, exc)
            return {"is_catchall": None, "probed": False, "error": type(exc).__name__}

    async def probe_smtp_catchall(
        self,
        domain: str,
        mx_host: str,
        enable_catchall_probe: bool = False,
    ) -> Dict[str, Any]:
        if not enable_catchall_probe:
            return {"is_catchall": None, "probed": False, "reason": "disabled_by_policy"}
        return await asyncio.to_thread(self.probe_smtp_catchall_sync, domain, mx_host)

    async def verify_email_v2(
        self,
        email: str,
        client: Optional[httpx.AsyncClient] = None,
        *,
        enable_catchall_probe: bool = False,
    ) -> Dict[str, Any]:
        """Retorna evidência explicável sem tratar inferência como verificação."""
        base = await self.verify_email(email, client=client)
        reason = base.get("reason")
        if reason == "syntax_invalid":
            return {
                **base,
                "status": "invalid",
                "confidence": 0,
                "catch_all": None,
                "auto_send_eligible": False,
            }
        if reason == "disposable_domain":
            return {
                **base,
                "status": "invalid",
                "confidence": 5,
                "catch_all": None,
                "auto_send_eligible": False,
            }
        if not base.get("domain_valid") or not base.get("mx"):
            return {
                **base,
                "status": "unknown",
                "confidence": 15,
                "catch_all": None,
                "auto_send_eligible": False,
            }

        if not enable_catchall_probe:
            return {
                **base,
                "verified": False,
                "status": "domain_validated",
                "confidence": 65,
                "catch_all": None,
                "auto_send_eligible": False,
                "reason": "mx_valid_catchall_not_checked",
            }

        probe = await self.probe_smtp_catchall(
            _extract_domain(email), str(base["mx"]), enable_catchall_probe=True,
        )
        if not probe.get("probed"):
            return {
                **base,
                "verified": False,
                "status": "catchall_unknown",
                "confidence": 50,
                "catch_all": None,
                "auto_send_eligible": False,
                "reason": "catchall_probe_unavailable",
            }
        if probe.get("is_catchall") is True:
            return {
                **base,
                "verified": False,
                "status": "catch_all",
                "confidence": 60,
                "catch_all": True,
                "auto_send_eligible": False,
                "reason": "catch_all_domain",
            }
        return {
            **base,
            "verified": False,
            "status": "non_catch_all",
            "confidence": 75,
            "catch_all": False,
            "auto_send_eligible": False,
            "reason": "mx_valid_non_catch_all_mailbox_unconfirmed",
        }
