"""Token de inbound por organização — resolução determinística de tenant.

Os provedores de inbound (Postmark, SendGrid inbound parse) só permitem
configurar a URL de destino, sem header customizado. Por isso a credencial
viaja no path da rota e é resolvida aqui, antes de qualquer consulta de
domínio.

Só o `sha256` do token é persistido em `Organization.inbound_token_hash`.
O token em claro existe apenas no momento da geração e na configuração do
provedor — nunca é gravado nem registrado em log.
"""
import hashlib
import logging
import secrets
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from src.db.models import Organization

logger = logging.getLogger(__name__)

# Teto de tamanho do token aceito no path. Acima disso a requisição é recusada
# sem tocar o banco — token legítimo tem 43 caracteres.
MAX_TOKEN_LENGTH = 128


def hash_inbound_token(token: str) -> str:
    """Hash determinístico do token — permite lookup indexado por igualdade."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def generate_inbound_token() -> Tuple[str, str]:
    """Retorna (token em claro, hash). O claro só é exibido na geração."""
    token = secrets.token_urlsafe(32)
    return token, hash_inbound_token(token)


def resolve_organization_by_token(db: Session, token: str) -> Optional[Organization]:
    """Resolve no máximo uma org antes de qualquer consulta de domínio.

    A comparação é feita no banco sobre o hash (valor derivado, não o
    segredo) usando o índice único `uq_organizations_inbound_token_hash`:
    determinístico, indexado e sem risco de casar duas organizações. Como
    a comparação não é sobre o segredo em si, não há necessidade de
    comparação em tempo constante na aplicação.

    Devolve `None` para token vazio, acima do teto de tamanho ou sem
    correspondência — o chamador trata os três casos de forma idêntica.
    """
    if not token or len(token) > MAX_TOKEN_LENGTH:
        # Nunca logar o token: só o motivo da recusa.
        logger.warning("Token de inbound recusado: ausente ou fora do tamanho aceito")
        return None

    org = (
        db.query(Organization)
        .filter(Organization.inbound_token_hash == hash_inbound_token(token))
        .first()
    )
    if org is None:
        logger.warning("Token de inbound não resolveu nenhuma organização")
        return None

    logger.info("Inbound resolvido para a organização %s", org.id)
    return org
