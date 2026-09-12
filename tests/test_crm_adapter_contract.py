"""Testes do limite arquitetural de integração CRM."""
import pytest

from services.crm_adapters import (
    CRM_ADAPTER_VERSION,
    CRMAdapterRegistry,
    CRMEntitySnapshot,
    CRMSyncResult,
)


class _Adapter:
    provider = "pipedrive"
    version = CRM_ADAPTER_VERSION

    async def upsert(self, snapshot, *, idempotency_key):
        return CRMSyncResult(
            provider=self.provider,
            operation="upsert",
            local_entity_id=snapshot.entity_id,
            remote_entity_id="remote-1",
            status="ok",
        )

    async def fetch_changes(self, *, organization_id, cursor=None):
        return [], cursor

    async def healthcheck(self):
        return {"ok": True}


def test_snapshot_restringe_entidades_canonicas():
    snapshot = CRMEntitySnapshot(
        entity_type="company",
        entity_id="company-1",
        organization_id="org-1",
        fields={"name": "Alpha"},
    )
    assert snapshot.version == "v1"

    with pytest.raises(ValueError, match="entity_type"):
        CRMEntitySnapshot(entity_type="password", entity_id="x", organization_id="org-1")


def test_registry_falha_fechado_sem_adapter_configurado():
    registry = CRMAdapterRegistry()
    with pytest.raises(LookupError, match="não configurado"):
        registry.get("pipedrive")


def test_registry_aceita_adapter_versionado():
    registry = CRMAdapterRegistry()
    registry.register(_Adapter())

    assert registry.get("PIPEDRIVE").provider == "pipedrive"
    assert registry.configured_providers() == ("pipedrive",)


def test_registry_rejeita_provider_fora_do_contrato():
    adapter = _Adapter()
    adapter.provider = "unknown"
    with pytest.raises(ValueError, match="não suportado"):
        CRMAdapterRegistry().register(adapter)
