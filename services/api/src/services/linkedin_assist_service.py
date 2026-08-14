"""Serviço de LinkedIn assistido (pesquisa + associação manual).

Quando a busca passiva não encontra o decisor, o consultor precisa de um
fluxo guiado: consultas prontas, atalho de busca externa e associação manual
de um perfil que ele encontrou fora do sistema. Tudo passivo (sem scraping
do LinkedIn — o perfil só é validado se o buscador o indexou).
"""
import logging
import os
import re
import sys
from typing import Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from src.db.models import Contact, Lead, LeadActivityAction
from src.services.lead_activity_service import log_activity

# Reusa helpers dos workers (fonte única) para validar o username.
_WORKERS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "workers", "src"
)
if _WORKERS_PATH not in sys.path:
    sys.path.insert(0, _WORKERS_PATH)
from services.contact_enrichment_service import LINKEDIN_ALIAS_RE  # noqa: E402

logger = logging.getLogger(__name__)

# Papéis padrão usados nas consultas sugeridas quando o template não define
# `playbook.linkedin_queries`.
DEFAULT_ROLE_QUERIES = [
    "fundador", "sócio", "diretor", "CEO", "head", "gerente",
]

LINKEDIN_PROFILE_RE = re.compile(
    r"(?:https?://)?(?:[a-z0-9-]+\.)*linkedin\.com/in/([a-zA-Z0-9-]+)(?=[/?#]|$)",
    re.IGNORECASE,
)

# Confiança gravada ao associar manualmente: perfil confirmado no índice (90)
# ou candidato para revisão humana (60).
CONF_VALIDATED = 90
CONF_REVIEW = 60


def build_linkedin_queries(company_name: str, playbook: Optional[dict]) -> List[Dict[str, str]]:
    """Consultas sugeridas `"<empresa>" <papel> linkedin` para achar o decisor.

    Usa `playbook["linkedin_queries"]` (lista de cargos/rótulos definida no
    template da campanha) quando presente; senão a lista padrão de papéis.
    """
    roles = playbook.get("linkedin_queries") if isinstance(playbook, dict) else None
    if not roles or not isinstance(roles, list) or not roles:
        roles = DEFAULT_ROLE_QUERIES
    return [
        {"label": str(role), "query": f'"{company_name}" {role} linkedin'}
        for role in roles
    ]


def extract_linkedin_username(url: str) -> Optional[str]:
    """Extrai o username de uma URL de perfil LinkedIn, se o formato for válido.

    Aceita `https://www.linkedin.com/in/<username>` (com ou sem www/prefixo)
    e valida o username com o mesmo padrão usado no enriquecimento.
    """
    if not url:
        return None
    m = LINKEDIN_PROFILE_RE.search(url.strip())
    if not m:
        return None
    username = m.group(1)
    if not LINKEDIN_ALIAS_RE.match(username):
        return None
    return username


def linkedin_match_status(
    url: Optional[str],
    source: Optional[str],
    confidence: Optional[int],
) -> str:
    """Deriva o estado de match do LinkedIn a partir de fonte e confiança.

    - NOT_FOUND: sem perfil associado.
    - CANDIDATE: URL inferida por heurística (pode não ser a pessoa certa).
    - NEEDS_REVIEW: candidato para revisão humana (associação manual com
      confiança baixa ou fonte desconhecida).
    - VERIFIED: perfil corroborado (encontrado por busca nome+empresa ou
      associação manual validada).
    """
    if not url:
        return "NOT_FOUND"
    src = (source or "").lower()
    conf = int(confidence or 0)
    if src.startswith("manual"):
        return "VERIFIED" if conf >= 90 else "NEEDS_REVIEW"
    if src.startswith("search"):
        return "VERIFIED"
    if src == "heuristic":
        return "CANDIDATE"
    return "VERIFIED" if conf >= 90 else "NEEDS_REVIEW"


class LinkedInAssistService:
    """Validação passiva e persistência do perfil associado manualmente."""

    async def profile_exists(self, username: str) -> bool:
        """Valida a existência do perfil via índice de busca (passivo).

        O LinkedIn bloqueia bots diretos (HTTP 999), então checamos se o
        buscador indexou `linkedin.com/in/<username>`. Retorna `False` quando
        os buscadores falham (o humano decide salvar como candidato).
        """
        async with httpx.AsyncClient(timeout=15) as client:
            for engine, url, params in (
                ("duckduckgo", "https://html.duckduckgo.com/html/",
                 {"q": f'site:linkedin.com/in/ "{username}"', "kl": "br-pt"}),
                ("bing", "https://www.bing.com/search",
                 {"q": f'site:linkedin.com/in/ "{username}"', "count": 10}),
            ):
                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200 and f"/in/{username}" in resp.text:
                        return True
                except Exception as exc:  # noqa: BLE001 — buscador fora do ar não aborta
                    logger.debug("Validação LinkedIn (%s) falhou: %s", engine, exc)
        return False

    def associate(
        self,
        db: Session,
        lead: Lead,
        contact: Contact,
        username: str,
        user_id: str,
        validated: bool,
    ) -> Contact:
        """Persiste a URL associada manualmente e registra na trilha.

        `validated=True` → confidence 90 (perfil confirmado no índice); senão
        60 (candidato para revisão do consultor). Origem gravada como
        `manual:<user_id>` em `raw_data.linkedin_source`.
        """
        contact.linkedin_url = f"https://www.linkedin.com/in/{username}"
        contact.linkedin_confidence = CONF_VALIDATED if validated else CONF_REVIEW
        contact.raw_data = {
            **(contact.raw_data or {}),
            "linkedin_source": f"manual:{user_id}",
        }
        log_activity(
            db,
            lead,
            action=LeadActivityAction.LINKEDIN_ASSOCIATED,
            user_id=user_id,
            detail=f"Perfil LinkedIn associado manualmente: /in/{username}",
        )
        return contact
