"""QuotaService — medidor de cotas diárias por provedor/org.

Contabiliza o uso de provedores externos por organização e por dia, contra
um limite configurável:
- `organizations.api_quota` (JSONB — sobrescreve por provedor, inclusive zero), senão
- `settings.PROVIDER_DAILY_QUOTA` (default do pool global).

O gate é fail-closed: quando `remaining(key) <= 0`, o provider NÃO chama e o
caller trata como falha/fallback. Um override explícito igual a zero desabilita
o provider para a organização e nunca cai silenciosamente no limite global.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import settings
from database.models import Organization, ProviderUsage

logger = logging.getLogger(__name__)


class QuotaService:
    """Acesso síncrono ao medidor de uso (chamado de orquestradores async)."""

    @staticmethod
    def _configured_limit(org: Optional[Organization], key: str) -> int:
        """Resolve override da org preservando zero como configuração explícita."""
        overrides = org.api_quota if org and isinstance(org.api_quota, dict) else {}
        if key in overrides:
            try:
                return max(0, int(overrides[key]))
            except (TypeError, ValueError):
                logger.warning("Quota inválida para %s; bloqueando provider por segurança.", key)
                return 0
        default = settings.PROVIDER_DAILY_QUOTA.get(key)
        try:
            return max(0, int(default)) if default is not None else 0
        except (TypeError, ValueError):
            logger.warning("Quota default inválida para %s; bloqueando provider por segurança.", key)
            return 0

    @staticmethod
    def limit_for(db: Session, organization_id: Optional[str], key_name: str) -> int:
        """Limite diário da org para o provedor (override explícito vence o pool)."""
        key = key_name.upper().strip()
        org = None
        if organization_id:
            org = db.query(Organization).filter(Organization.id == organization_id).first()
        return QuotaService._configured_limit(org, key)

    @staticmethod
    def used_today(
        db: Session, organization_id: Optional[str], key_name: str, when: Optional[datetime] = None,
    ) -> int:
        """Chamadas que a org já fez hoje para o provedor."""
        if not organization_id:
            return 0
        day = (when or datetime.now(timezone.utc)).date()
        row = (
            db.query(ProviderUsage)
            .filter(
                ProviderUsage.organization_id == organization_id,
                ProviderUsage.key_name == key_name.upper().strip(),
                ProviderUsage.usage_date == day,
            )
            .first()
        )
        return row.count if row else 0

    @staticmethod
    def remaining(
        db: Session, organization_id: Optional[str], key_name: str, when: Optional[datetime] = None,
    ) -> int:
        """Quantas chamadas ainda cabem hoje para a org/provedor."""
        limit = QuotaService.limit_for(db, organization_id, key_name)
        if limit <= 0:
            return 0
        return max(0, limit - QuotaService.used_today(db, organization_id, key_name, when))

    @staticmethod
    def can_consume(
        db: Session, organization_id: Optional[str], key_name: str, n: int = 1,
        when: Optional[datetime] = None,
    ) -> bool:
        """True se há cota para mais `n` chamadas hoje. Sem org → sem medição."""
        if not organization_id:
            return True
        return QuotaService.remaining(db, organization_id, key_name, when) >= n

    @staticmethod
    def consume(
        db: Session, organization_id: Optional[str], key_name: str, n: int = 1,
        when: Optional[datetime] = None,
    ) -> None:
        """Incrementa o contador diário da org/key (upsert) e commita."""
        if not organization_id:
            return
        key = key_name.upper().strip()
        day = (when or datetime.now(timezone.utc)).date()
        row = (
            db.query(ProviderUsage)
            .filter(
                ProviderUsage.organization_id == organization_id,
                ProviderUsage.key_name == key,
                ProviderUsage.usage_date == day,
            )
            .first()
        )
        if row:
            row.count = (row.count or 0) + n
        else:
            db.add(ProviderUsage(
                organization_id=organization_id,
                key_name=key,
                usage_date=day,
                count=n,
            ))
        db.commit()

    @staticmethod
    def usage_for_org(
        db: Session, organization_id: Optional[str], when: Optional[datetime] = None,
    ) -> list:
        """Painel de uso da org, incluindo overrides explícitos do pool global."""
        if not organization_id:
            return []
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        overrides = org.api_quota if org and isinstance(org.api_quota, dict) else {}
        keys = sorted(set(settings.PROVIDER_DAILY_QUOTA.keys()) | set(overrides.keys()))
        result = []
        for key in keys:
            limit = QuotaService._configured_limit(org, key)
            used = QuotaService.used_today(db, organization_id, key, when)
            remaining = max(0, limit - used)
            result.append({
                "key_name": key,
                "used": used,
                "limit": limit,
                "remaining": remaining,
                "pct": round(used / limit * 100, 1) if limit else 0,
            })
        return result
