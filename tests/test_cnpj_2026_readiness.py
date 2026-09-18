"""Readiness CNPJ 2026/alfanumérico nas bordas fora do núcleo do Registry.

Seams públicas: normalizadores/validadores legados, identity resolution,
importação (CSV/webhook), PNCP e checksum de garimpo. Valores esperados são
literais fixos: CNPJs reais (Petrobras/BB) e vetores alfanuméricos oficiais
já travados em test_registry_cnpj (exemplo trabalhado + primeiro real da
Receita, jul/2026). Nenhum teste depende de rede, banco ou data atual.
"""
from __future__ import annotations

# Petrobras (numérico real) e primeiro alfanumérico real (Receita, jul/2026).
NUMERICO_MASCARADO = "33.000.167/0001-01"
NUMERICO_LIMPO = "33000167000101"
ALNUM_MASCARADO = "00.000.000/E08G-12"
ALNUM_LIMPO = "00000000E08G12"
# Segundo alfanumérico válido, distinto, com o mesmo esqueleto de dígitos:
# a normalização antiga (só dígitos) colapsa os dois no mesmo identificador.
ALNUM_COLIDENTE = "00000000E08R12"
ALNUM_INVALIDO = "00000000E08G13"


def test_servicos_legados_concordam_com_canonico_no_numerico():
    from services import cnae_discovery_service, cnpj_service
    from services.registry.cnpj import is_valid_cnpj, normalize_cnpj

    assert cnpj_service.normalize_cnpj(NUMERICO_MASCARADO) == normalize_cnpj(NUMERICO_MASCARADO)
    assert cnpj_service.is_valid_cnpj(NUMERICO_MASCARADO) == is_valid_cnpj(NUMERICO_MASCARADO) is True
    assert cnae_discovery_service.normalize_cnpj(NUMERICO_MASCARADO) == NUMERICO_LIMPO


def test_servicos_legados_preservam_alfanumerico_valido():
    from services import cnae_discovery_service, cnpj_service
    from services.registry.cnpj import is_valid_cnpj

    assert is_valid_cnpj(ALNUM_LIMPO) is True
    assert cnpj_service.normalize_cnpj(ALNUM_MASCARADO) == ALNUM_LIMPO
    assert cnpj_service.is_valid_cnpj(ALNUM_LIMPO) is True
    assert cnae_discovery_service.normalize_cnpj(ALNUM_MASCARADO) == ALNUM_LIMPO


def test_servicos_legados_rejeitam_invalido():
    from services import cnpj_service

    assert cnpj_service.is_valid_cnpj(ALNUM_INVALIDO) is False
    assert cnpj_service.is_valid_cnpj("12345678") is False
    assert cnpj_service.is_valid_cnpj(None) is False


def test_identity_nao_colide_alfanumericos_distintos():
    from services.company_identity_service import CompanyIdentityResolver
    from services.registry.cnpj import is_valid_cnpj

    assert is_valid_cnpj(ALNUM_LIMPO) and is_valid_cnpj(ALNUM_COLIDENTE)
    resolver = CompanyIdentityResolver()
    colisao = resolver.resolve({"cnpj": ALNUM_LIMPO}, [{"cnpj": ALNUM_COLIDENTE}])
    assert colisao.status == "new"
    assert colisao.matched_by is None
    assert colisao.auto_merge is False


def test_identity_confirma_mesmo_alfanumerico_mascarado():
    from services.company_identity_service import CompanyIdentityResolver

    resolver = CompanyIdentityResolver()
    achado = resolver.resolve({"cnpj": ALNUM_LIMPO}, [{"cnpj": ALNUM_MASCARADO}])
    assert achado.status == "confirmed"
    assert achado.matched_by == "cnpj"


def test_identity_preserva_numerico_existente():
    from services.company_identity_service import CompanyIdentityResolver

    resolver = CompanyIdentityResolver()
    achado = resolver.resolve({"cnpj": NUMERICO_LIMPO}, [{"cnpj": NUMERICO_MASCARADO}])
    assert achado.status == "confirmed"
    assert achado.matched_by == "cnpj"


def test_csv_import_preserva_alfanumerico_valido():
    from src.services.csv_import_service import clean_cnpj

    assert clean_cnpj(ALNUM_MASCARADO) == ALNUM_LIMPO
    assert clean_cnpj("00.000.000/e08g-12") == ALNUM_LIMPO
    assert clean_cnpj(NUMERICO_MASCARADO) == NUMERICO_LIMPO
    assert clean_cnpj(ALNUM_INVALIDO) is None
    assert clean_cnpj("12345678") is None
    assert clean_cnpj(None) is None


def test_webhook_import_preserva_alfanumerico_valido():
    from src.services.webhook_import_service import clean_cnpj

    assert clean_cnpj(ALNUM_MASCARADO) == ALNUM_LIMPO
    assert clean_cnpj(NUMERICO_MASCARADO) == NUMERICO_LIMPO
    assert clean_cnpj(ALNUM_INVALIDO) is None
    assert clean_cnpj(None) is None


def test_pncp_preserva_fornecedor_alfanumerico_valido():
    from services.pncp_service import PncpService

    item = {"tipoPessoa": "PJ", "niFornecedor": ALNUM_MASCARADO, "nomeRazaoSocialFornecedor": "Exemplo LTDA"}
    parsed = PncpService.parse_contract(item)
    assert parsed is not None
    assert parsed["cnpj"] == ALNUM_LIMPO
    assert parsed["place_id_candidate"] == f"pncp_{ALNUM_LIMPO}"


def test_pncp_rejeita_fornecedor_invalido():
    from services.pncp_service import PncpService

    assert PncpService.parse_contract({"tipoPessoa": "PJ", "niFornecedor": ALNUM_INVALIDO}) is None
    assert PncpService.parse_contract({"tipoPessoa": "PF", "niFornecedor": "12345678901"}) is None


def test_checksum_garimpo_aceita_alfanumerico_sem_quebrar():
    from services.contact_enrichment_service import ContactEnrichmentService

    assert ContactEnrichmentService._is_valid_cnpj_checksum(ALNUM_LIMPO) is True
    assert ContactEnrichmentService._is_valid_cnpj_checksum(NUMERICO_LIMPO) is True
    assert ContactEnrichmentService._is_valid_cnpj_checksum(ALNUM_INVALIDO) is False
