"""Entity resolution reutilizada para itens do Registry (1C §10).

Não cria RegistryDeduplicator: usa CompanyIdentityResolver existente.
Prioridade: CNPJ canônico > domínio > place_id; fuzzy nunca auto-merge.
"""
from __future__ import annotations


def _resolver():
    from services.company_identity_service import CompanyIdentityResolver

    return CompanyIdentityResolver()


def _reg(cnpj="12345678000195", domain=None, place_id=None, name="INDUSTRIA X"):
    return {"cnpj": cnpj, "normalized_domain": domain, "place_id": place_id,
            "company_name": name, "provider": "cnae_discovery"}


def test_cnpj_existente_confirma_com_auto_merge():
    res = _resolver().resolve(_reg(), [_reg()])
    assert res.status == "confirmed"
    assert res.matched_by == "cnpj"
    assert res.auto_merge is True


def test_dominio_confirma_quando_cnpj_ausente():
    res = _resolver().resolve(
        _reg(cnpj=None, domain="empresa.example"),
        [_reg(cnpj=None, domain="empresa.example")],
    )
    assert res.status == "confirmed"
    assert res.matched_by == "normalized_domain"


def test_candidato_novo_sem_chaves():
    res = _resolver().resolve(
        {"company_name": "NOVA EMPRESA", "provider": "cnae_discovery"}, [],
    )
    assert res.status == "new"
    assert res.auto_merge is False


def test_duas_fontes_mesmo_cnpj_fundem():
    places = {"cnpj": None, "place_id": "ChIJ123", "company_name": "IND X",
              "city": "Araraquara", "state": "SP", "provider": "google_places"}
    registry = _reg(place_id=None)
    registry = {**registry, "company_name": "IND X"}
    res = _resolver().resolve(registry, [places, _reg()])
    assert res.status == "confirmed"
    assert res.matched_by == "cnpj"


def test_retry_e_replay_sao_deterministicos():
    item, known = _reg(), [_reg()]
    first = _resolver().resolve(item, known)
    second = _resolver().resolve(item, known)
    assert first.to_dict() == second.to_dict()


def test_chaves_fortes_divergentes_nao_fundem():
    res = _resolver().resolve(
        _reg(cnpj="11111111000111", name="EMPRESA A"),
        [_reg(cnpj="22222222000122", name="EMPRESA A")],
    )
    assert not (res.status == "confirmed" and res.matched_by == "cnpj")
    assert res.auto_merge is False
