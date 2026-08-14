"""SecretService — chaves de API por organização (BYOK).

Responsabilidades:
- Criptografar/descriptografar valores de `organization_secrets` em repouso
  usando Fernet (cryptography), com `SECRETS_ENCRYPTION_KEY` do settings.
  Se a chave mestre não estiver configurada, deriva uma chave determinística
  do DATABASE_URL (adequado apenas para desenvolvimento).
- Resolver a chave de um provedor para uma organização:
  1. Se a org tem `organization_secrets` com a chave → usa (BYOK).
  2. Senão → fallback para o pool global (`settings.GROQ_API_KEY` /
     `settings.GOOGLE_API_KEY`).

Sempre async (padrão do projeto). Nunca loga valores de chave.
"""
import base64
import hashlib
import logging
import os
import sys
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings  # noqa: E402
from database.models import OrganizationSecret  # noqa: E402

logger = logging.getLogger(__name__)

KEY_NAMES = ("GOOGLE_API_KEY", "GROQ_API_KEY")


def _derive_fernet_key() -> bytes:
    """Gera uma chave Fernet determinística (dev fallback) a partir do DATABASE_URL."""
    digest = hashlib.sha256(settings.DATABASE_URL.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    key: bytes
    if settings.SECRETS_ENCRYPTION_KEY:
        key = settings.SECRETS_ENCRYPTION_KEY.encode("utf-8")
    else:
        key = _derive_fernet_key()
    return Fernet(key)


def encrypt_value(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Falha ao descriptografar secret — chave mestre inválida.")
        return ""


class SecretService:
    """Resolve chaves por organização com fallback para o pool global."""

    @staticmethod
    async def set_org_secret(
        db, organization_id: str, key_name: str, value: str,
    ) -> OrganizationSecret:
        """Grava (upsert) uma chave criptografada para a organização."""
        normalized = key_name.upper().strip()
        if normalized not in KEY_NAMES:
            raise ValueError(f"key_name inválido: {normalized}")

        secret = (
            db.query(OrganizationSecret)
            .filter(
                OrganizationSecret.organization_id == organization_id,
                OrganizationSecret.key_name == normalized,
            )
            .first()
        )
        encrypted = encrypt_value(value)
        if secret:
            secret.encrypted_value = encrypted
        else:
            secret = OrganizationSecret(
                organization_id=organization_id,
                key_name=normalized,
                encrypted_value=encrypted,
            )
            db.add(secret)
        db.commit()
        db.refresh(secret)
        return secret

    @staticmethod
    async def delete_org_secret(
        db, organization_id: str, key_name: str,
    ) -> bool:
        """Remove uma chave da organização (volta a usar o pool global)."""
        normalized = key_name.upper().strip()
        secret = (
            db.query(OrganizationSecret)
            .filter(
                OrganizationSecret.organization_id == organization_id,
                OrganizationSecret.key_name == normalized,
            )
            .first()
        )
        if not secret:
            return False
        db.delete(secret)
        db.commit()
        return True

    @staticmethod
    async def resolve_key(
        db, organization_id: Optional[str], key_name: str,
    ) -> Optional[str]:
        """Resolve a chave de um provedor para a org (BYOK) ou o pool global.

        Ordem: organization_secrets → settings (pool).
        """
        normalized = key_name.upper().strip()
        if organization_id:
            try:
                secret = (
                    db.query(OrganizationSecret)
                    .filter(
                        OrganizationSecret.organization_id == organization_id,
                        OrganizationSecret.key_name == normalized,
                    )
                    .first()
                )
                if secret:
                    value = decrypt_value(secret.encrypted_value)
                    if value:
                        return value
            except Exception as e:
                logger.warning("Falha ao resolver secret %s da org %s: %s",
                               normalized, organization_id, e)

        # Fallback para o pool global
        pool_value = getattr(settings, normalized, "")
        return pool_value or None

    @staticmethod
    async def resolve_all(db, organization_id: Optional[str]) -> Dict[str, Any]:
        """Resolve todas as chaves suportadas de uma vez (pool ou BYOK)."""
        result: Dict[str, Any] = {}
        for key_name in KEY_NAMES:
            result[key_name] = await SecretService.resolve_key(
                db, organization_id, key_name,
            )
        return result
