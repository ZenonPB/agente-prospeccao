"""Contrato do resolver cross-provider de identidade de empresas."""


def test_cnpj_exato_confirma_identidade_e_preserva_provenance():
    from services.company_identity_service import CompanyIdentityResolver

    resolver = CompanyIdentityResolver()
    result = resolver.resolve(
        {"name": "Metalúrgica XPTO LTDA", "cnpj": "00.111.222/0001-33", "city": "São Paulo"},
        [
            {
                "name": "XPTO INDUSTRIA",
                "cnpj": "00111222000133",
                "provider": "pncp",
                "provider_query": "metalurgia sp",
            }
        ],
    )

    assert result.status == "confirmed"
    assert result.matched_by == "cnpj"
    assert result.confidence == 1.0
    assert result.provenance["providers"] == ["pncp"]
    assert result.provenance["provider_queries"] == ["metalurgia sp"]


def test_dominios_equivalentes_confirmam_entre_providers():
    from services.company_identity_service import CompanyIdentityResolver

    result = CompanyIdentityResolver().resolve(
        {"name": "XPTO", "website": "https://www.xpto.com.br/contato", "provider": "google_places"},
        [{"name": "XPTO LTDA", "normalized_domain": "xpto.com.br", "provider": "cnae_discovery"}],
    )

    assert result.status == "confirmed"
    assert result.matched_by == "normalized_domain"
    assert result.confidence == 0.95
    assert result.provenance["providers"] == ["google_places", "cnae_discovery"]


def test_place_id_confirma_mesmo_estabelecimento_mesmo_com_nome_diferente():
    from services.company_identity_service import CompanyIdentityResolver

    result = CompanyIdentityResolver().resolve(
        {"name": "XPTO Filial", "place_id": "ChIJ123", "provider": "google_places"},
        [{"name": "XPTO", "place_id_candidate": "ChIJ123", "provider": "google_places"}],
    )

    assert result.status == "confirmed"
    assert result.matched_by == "place_id"


def test_nome_e_localizacao_ambiguos_sao_candidato_e_nao_merge_automatico():
    from services.company_identity_service import CompanyIdentityResolver

    result = CompanyIdentityResolver().resolve(
        {"name": "Metalúrgica XPTO", "city": "São Paulo", "state": "SP", "provider": "cnae_discovery"},
        [{"name": "Metalurgica XPTO Industria", "city": "São Paulo", "state": "SP", "provider": "google_places"}],
    )

    assert result.status == "candidate"
    assert result.matched_by == "name_location_candidate"
    assert 0.5 <= result.confidence < 0.9
    assert result.auto_merge is False


def test_sem_chave_de_identidade_retorna_nova_entidade():
    from services.company_identity_service import CompanyIdentityResolver

    result = CompanyIdentityResolver().resolve(
        {"name": "Empresa Nova", "provider": "google_places"},
        [],
    )

    assert result.status == "new"
    assert result.matched_by is None
    assert result.auto_merge is False