"""CRM boundary do Registry discovery: busca pura não toca Company/Lead.

RED (TDD): garante RegistryCandidate != Company no caminho do adapter —
converter candidatos (dicts) para o formato do pipeline NÃO cria entidades
comerciais; promoção continua exclusiva da fronteira existente.
"""
from __future__ import annotations


def test_converter_candidatos_nao_toca_crm():
    from services.registry.discovery_adapter import _to_item

    class _Cand:
        cnpj = "12345678000195"
        razao_social = "INDUSTRIA EXEMPLO LTDA"
        nome_fantasia = "EXEMPLO"
        cnae_principal = "2869100"
        cnae_principal_label = "Máquinas"
        uf = "SP"
        source_snapshot = "2026-08"

    item = _to_item(_Cand())
    # Dict puro: sem organization_id, sem ids comerciais, sem mutação.
    assert set(item) <= {
        "cnpj", "company_name", "name", "cnae_code", "cnae_description",
        "city", "state", "address", "municipio_cod", "situacao", "matriz", "porte",
        "cnaes_secundarios", "place_id", "provider", "discovery_source",
        "provider_query", "source_snapshot", "provenance",
    }
    assert "organization_id" not in item
    assert "company_id" not in item
    assert "lead_id" not in item


def test_place_id_registry_e_deterministico_e_nao_colide_com_places():
    from services.registry.discovery_adapter import _to_item

    class _Cand:
        cnpj = "12345678000195"
        razao_social = "X"
        nome_fantasia = "X"
        cnae_principal = None
        cnae_principal_label = None
        uf = None
        source_snapshot = None

    assert _to_item(_Cand())["place_id"] == "registry_12345678000195"
