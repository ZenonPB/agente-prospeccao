"""Contrato de ativação opt-in de providers pagos por organização."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def test_hunter_global_sem_quota_da_org_fica_desabilitado():
    from services.contact_enrichment_service import ContactEnrichmentService

    organization = MagicMock(api_quota={})
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = organization

    with patch(
        "services.secret_service.SecretService.resolve_key",
        new=AsyncMock(return_value="global-secret"),
    ):
        service = asyncio.run(ContactEnrichmentService.for_organization(db, "org-1"))

    assert service.hunter_enabled is False
    assert service.people_registry.list_providers() == []


def test_hunter_com_quota_da_org_fica_registrado():
    from services.contact_enrichment_service import ContactEnrichmentService

    organization = MagicMock(api_quota={"HUNTER_API_KEY": 50})
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = organization

    with patch(
        "services.secret_service.SecretService.resolve_key",
        new=AsyncMock(return_value="org-secret"),
    ):
        service = asyncio.run(ContactEnrichmentService.for_organization(db, "org-1"))

    assert service.hunter_enabled is True
    assert service.people_registry.list_providers() == ["hunter"]