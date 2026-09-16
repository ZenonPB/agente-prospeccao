"""Tenant isolation da 1C/1D (sem DB): Registry global, comercial org-scoped.

- RegistryCompany/RegistryCandidate não têm organization_id (universo global).
- Targeting/adapter não recebem org (leitura global, sem estado comercial).
- Métricas/shadow e promoção continuam org-scoped (ProviderExecutionMetric
  exige organization_id; pipeline passa organization_id do job).
"""
from __future__ import annotations


def test_registry_company_e_global_sem_organization_id():
    from database.models import RegistryCompany

    assert not hasattr(RegistryCompany, "organization_id")


def test_registry_candidate_e_global_sem_organization_id():
    from services.registry.candidate import RegistryCandidate

    assert "organization_id" not in RegistryCandidate.__dataclass_fields__


def test_targeting_nao_recebe_organizacao():
    import inspect

    from services.registry.targeting import build_search_filters

    params = set(inspect.signature(build_search_filters).parameters)
    assert "organization_id" not in params
    assert "org_id" not in params


def test_adapter_items_nao_carregam_organization_id():
    import asyncio

    from services.registry.discovery_adapter import (
        RegistryCnaeDiscoveryAdapter, _to_item,
    )

    class _Cand:
        cnpj = "12345678000195"
        razao_social = "X"
        nome_fantasia = "X"
        cnae_principal = "2869100"
        cnae_principal_label = None
        uf = "SP"
        source_snapshot = None

    item = _to_item(_Cand())
    assert "organization_id" not in item

    async def _run():
        adapter = RegistryCnaeDiscoveryAdapter(search_service_factory=None)
        result = await adapter.run_with_status("28", {"organization_id": "org-a"})
        assert result["status"] == "disabled"

    asyncio.run(_run())


def test_metrica_de_execucao_continua_org_scoped():
    from database.models import ProviderExecutionMetric

    assert hasattr(ProviderExecutionMetric, "organization_id")
    assert ProviderExecutionMetric.organization_id.nullable is False


def test_shadow_usa_organization_do_job():
    import inspect

    import src.pipeline_worker as pw

    params = set(inspect.signature(pw._persist_registry_shadow_comparison).parameters)
    assert "organization_id" in params
