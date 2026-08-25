"""Testes do coletor de licitações públicas (PNCP).

Cobre janela de datas, parse do contrato (fornecedores PJ com CNPJ válido),
dedup por fornecedor, nota de evidência e a busca com cliente HTTP fake —
sem tocar na rede nem no banco.
"""
from datetime import date
from types import SimpleNamespace

from services.pncp_service import (
    PncpService,
    default_date_window,
    format_contract_note,
    unique_suppliers,
)


def _contrato(**overrides):
    base = {
        "numeroControlePNCP": "83026765000128-2-000266/2026",
        "tipoPessoa": "PJ",
        "niFornecedor": "14126371000129",
        "nomeRazaoSocialFornecedor": "14.126.371 NORLEI JOSE DOS SANTOS",
        "orgaoEntidade": {
            "cnpj": "83026765000128",
            "razaoSocial": "MUNICIPIO DE CAMPO ERE",
        },
        "unidadeOrgao": {"ufSigla": "SC", "municipioNome": "Campo Ere"},
        "objetoContrato": "Coleta e destinação de resíduos recicláveis",
        "valorGlobal": 120000.0,
        "dataAssinatura": "2026-07-31",
    }
    base.update(overrides)
    return base


# --- Janela de datas ---------------------------------------------------------


def test_janela_padrao_em_dias():
    # Últimos 30 dias contando hoje (início inclusivo).
    assert default_date_window(days_back=30, today=date(2026, 8, 24)) == (
        "20260726",
        "20260824",
    )


def test_janela_de_um_dia():
    assert default_date_window(days_back=1, today=date(2026, 8, 24)) == (
        "20260824",
        "20260824",
    )


# --- Parse do contrato -------------------------------------------------------


def test_parse_contrato_pj_mapeia_fornecedor():
    out = PncpService.parse_contract(_contrato())
    assert out is not None
    assert out["cnpj"] == "14126371000129"
    assert out["supplier_name"] == "14.126.371 NORLEI JOSE DOS SANTOS"
    assert out["place_id_candidate"] == "pncp_14126371000129"
    assert out["contract"]["numero_controle"] == "83026765000128-2-000266/2026"
    assert out["contract"]["orgao"] == "MUNICIPIO DE CAMPO ERE"
    assert out["contract"]["uf"] == "SC"
    assert out["contract"]["valor_global"] == 120000.0


def test_parse_contrato_pessoa_fisica_e_descartado():
    assert PncpService.parse_contract(_contrato(tipoPessoa="PF")) is None


def test_parse_contrato_sem_cnpj_valido_e_descartado():
    assert PncpService.parse_contract(_contrato(niFornecedor="123")) is None
    assert PncpService.parse_contract(_contrato(niFornecedor=None)) is None


def test_parse_contrato_mascara_valores_ausentes():
    out = PncpService.parse_contract(
        _contrato(valorGlobal=None, objetoContrato=None, unidadeOrgao=None)
    )
    assert out is not None
    assert out["contract"]["valor_global"] is None
    assert out["contract"]["objeto"] is None
    assert out["contract"]["uf"] is None


# --- Dedup por fornecedor ----------------------------------------------------


def test_unique_suppliers_agrupa_por_cnpj():
    parsed = [
        PncpService.parse_contract(_contrato()),
        PncpService.parse_contract(
            _contrato(
                numeroControlePNCP="83026765000128-2-000300/2026",
                valorGlobal=80000.0,
                dataAssinatura="2026-08-05",
            )
        ),
        PncpService.parse_contract(
            _contrato(niFornecedor="98765432000110", nomeRazaoSocialFornecedor="Outra Ltda")
        ),
    ]
    suppliers = unique_suppliers([p for p in parsed if p])
    assert len(suppliers) == 2
    norlei = next(s for s in suppliers if s["cnpj"] == "14126371000129")
    assert len(norlei["contracts"]) == 2
    assert norlei["total_value"] == 200000.0
    # Fornecedor mais recente primeiro (contrato de 2026-08-05).
    assert suppliers[0]["cnpj"] == "14126371000129"


# --- Nota de evidência -------------------------------------------------------


def test_nota_de_contrato_e_legivel_e_curta():
    supplier = unique_suppliers([PncpService.parse_contract(_contrato())])[0]
    note = format_contract_note(supplier)
    assert "1 contrato" in note
    assert "MUNICIPIO DE CAMPO ERE" in note
    assert len(note) <= 400


def test_nota_trunca_objeto_longo():
    supplier = unique_suppliers(
        [PncpService.parse_contract(_contrato(objetoContrato="x" * 900))]
    )[0]
    note = format_contract_note(supplier)
    assert len(note) < 420


# --- Busca com HTTP fake -----------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        page = (params or {}).get("pagina", 1)
        return _FakeResponse(self.pages.get(page, {"data": [], "totalPaginas": 1}))


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_search_pagina_ate_esgotar_e_filtra_por_uf():
    client = _FakeClient(
        {
            1: {"data": [_contrato()], "totalPaginas": 2},
            2: {
                "data": [
                    _contrato(
                        niFornecedor="98765432000110",
                        nomeRazaoSocialFornecedor="Vale Plásticos S.A.",
                        unidadeOrgao={"ufSigla": "SP", "municipioNome": "Campinas"},
                    )
                ],
                "totalPaginas": 2,
            },
        }
    )
    suppliers = _run(
        PncpService.search_supplier_contracts(
            "20260701", "20260731", uf="SP", max_suppliers=10, client=client
        )
    )
    assert [s["supplier_name"] for s in suppliers] == ["Vale Plásticos S.A."]
    assert len(client.calls) == 2


def test_search_consulta_endpoint_real_com_datas_compactas():
    client = _FakeClient({1: {"data": [], "totalPaginas": 0}})
    _run(
        PncpService.search_supplier_contracts(
            "20260701", "20260731", max_suppliers=5, client=client
        )
    )
    url, params = client.calls[0]
    assert "/contratos" in url
    assert params["dataInicial"] == "20260701"
    assert params["dataFinal"] == "20260731"
    assert params["pagina"] == 1


def test_search_para_no_maximo_de_fornecedores():
    client = _FakeClient(
        {
            1: {
                "data": [
                    _contrato(
                        niFornecedor="11111111000111",
                        nomeRazaoSocialFornecedor="A Ltda",
                    ),
                    _contrato(
                        niFornecedor="22222222000122",
                        nomeRazaoSocialFornecedor="B Ltda",
                    ),
                ],
                "totalPaginas": 3,
            },
            2: {"data": [], "totalPaginas": 3},
            3: {"data": [], "totalPaginas": 3},
        }
    )
    suppliers = _run(
        PncpService.search_supplier_contracts(
            "20260701", "20260731", max_suppliers=1, client=client
        )
    )
    assert len(suppliers) == 1
    assert len(client.calls) == 1  # não paginou além do necessário


def test_search_filtra_por_palavra_chave_no_objeto():
    client = _FakeClient(
        {
            1: {
                "data": [
                    _contrato(objetoContrato="Usinagem de peças CNC"),
                    _contrato(
                        niFornecedor="98765432000110",
                        objetoContrato="Manutenção de elevadores",
                    ),
                ],
                "totalPaginas": 1,
            }
        }
    )
    suppliers = _run(
        PncpService.search_supplier_contracts(
            "20260701", "20260731", keyword="usinagem", max_suppliers=10, client=client
        )
    )
    assert [s["cnpj"] for s in suppliers] == ["14126371000129"]
