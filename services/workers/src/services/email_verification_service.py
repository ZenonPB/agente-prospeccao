"""EmailVerificationService — verificação passiva de entregabilidade de e-mail.

Reduz bounce e protege a reputação do domínio antes de qualquer envio de
cadência.

O que é verificado (100% passivo — Lei 12.737/2012):
1. **Sintaxe** — o endereço tem formato válido.
2. **Domínio descartável** — blocklist de provedores temporários
   (mailinator etc.) que sempre "aceitam" qualquer endereço.
3. **Registro MX** — o domínio tem servidor de e-mail configurado
   (consulta DNS pública via Cloudflare DoH, sem dependência nova).

O que NÃO é verificado aqui (fora de escopo por exigir ação não-passiva):
- **Catch-all**: detectar exigiria conversa SMTP (`RCPT TO` com um localpart
  aleatório) — isso é um probe no servidor alvo, fora da política do projeto.
  Fica como item futuro com decisão explícita de produto.
- **Caixa individual**: só um SMTP handshake comprovaria a caixa; não passivo.

Retorno sempre "fail-closed": qualquer incerteza (DNS indisponível, timeout)
resulta em `verified=False`, pois o custo de um falso-positivo é um bounce.
"""
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Sintaxe de e-mail (mesma regra usada no enriquecimento de contatos).
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)

# Domínios descartáveis/temporários comuns (não exaustivo — suficiente para
# o primeiro entregável; ampliável por config sem mudar código).
DISPOSABLE_DOMAINS: frozenset = frozenset({
    "mailinator.com", "maildrop.cc", "10minutemail.com", "guerrillamail.com",
    "sharklasers.com", "temp-mail.org", "throwawaymail.com", "getnada.com",
    "yopmail.com", "mailnesia.com", "mailcatch.com", "trashmail.com",
    "fakeinbox.com", "mytemp.email", "dispostable.com", "tempmail.com.br",
    "temporarymail.com", "mailnator.com", "emailondeck.com", "spam4.me",
})

# Cloudflare DNS-over-HTTPS (API pública, JSON) — consulta MX sem instalar
# lib de DNS. Respostas sem `Answer` = domínio sem registro MX.
DOH_URL = "https://cloudflare-dns.com/dns-query"
DOH_HEADERS = {"Accept": "application/dns-json"}
MX_RRTYPE = 15


def is_valid_email_syntax(email: Optional[str]) -> bool:
    """True se o e-mail tem sintaxe válida (sem resolver DNS — sem rede)."""
    return bool(email and _EMAIL_RE.match(email.strip()))


def _extract_domain(email: str) -> str:
    """Devolve o domínio de um e-mail (lowercase)."""
    return email.strip().lower().rsplit("@", 1)[-1]


class EmailVerificationService:
    """Verifica a entregabilidade provável de um e-mail (passivo, sem custo)."""

    def __init__(self) -> None:
        # Cache em memória por domínio → resultado do MX (evita re-consultar
        # o DNS para dezenas de contatos do mesmo domínio).
        self._mx_cache: Dict[str, Optional[List[str]]] = {}

    async def _lookup_mx(
        self, client: httpx.AsyncClient, domain: str,
    ) -> Optional[List[str]]:
        """Consulta os MX de um domínio via DNS-over-HTTPS (Cloudflare).

        Retorna lista de MX ou None em caso de falha de rede/indisponibilidade
        (o chamador trata como "não verificado" — fail-closed).
        """
        if domain in self._mx_cache:
            return self._mx_cache[domain]

        try:
            resp = await client.get(
                DOH_URL,
                params={"name": domain, "type": "MX"},
                headers=DOH_HEADERS,
            )
            if resp.status_code != 200:
                logger.debug("DoH MX falhou (%s) para %s", resp.status_code, domain)
                self._mx_cache[domain] = None
                return None
            payload = resp.json()
            answers = [
                a.get("data", "")
                for a in payload.get("Answer", [])
                if a.get("type") == MX_RRTYPE
            ]
            result = answers or None
            self._mx_cache[domain] = result
            return result
        except Exception as exc:  # noqa: BLE001 — qualquer erro = fail-closed
            logger.debug("Erro ao consultar MX de %s: %s", domain, exc)
            self._mx_cache[domain] = None
            return None

    async def verify_email(
        self,
        email: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Verifica um e-mail e devolve `{verified, mx, reason}`.

        `verified` só é True quando todos os checks passarem (sintaxe +
        não-descartável + MX presente). Qualquer incerteza → False.
        `reason` explica o motivo do resultado (para UI e logs).
        `mx` é o primeiro servidor MX encontrado (ou None).
        """
        if not is_valid_email_syntax(email):
            return {"verified": False, "mx": None, "reason": "syntax_invalid"}

        domain = _extract_domain(email)
        if domain in DISPOSABLE_DOMAINS:
            return {"verified": False, "mx": None, "reason": "disposable_domain"}

        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=10.0)
        try:
            mx = await self._lookup_mx(client, domain)
        finally:
            if own_client:
                await client.aclose()

        if mx is None:
            return {"verified": False, "mx": None, "reason": "no_mx_or_dns_unavailable"}
        return {"verified": True, "mx": mx[0], "reason": "ok"}
