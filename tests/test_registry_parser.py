"""Parser do layout aberto da Receita (Fase 1B).

Seam: `services.registry.parser.iter_records`.
Layout: PDF oficial "NOVOLAYOUTDOSDADOSABERTOSDOCNPJ" (gov.br).
Fixtures SINTÉTICAS fiéis ao layout (bulk real inacessível neste ambiente);
bytes latin-1 com diacríticos provam o caminho de encoding.
"""
from __future__ import annotations

from decimal import Decimal


def _estab(
    basico="33000167",
    ordem="0001",
    dv="01",
    matriz="1",
    fantasia="PETROBRAS",
    sit="2",
    data_sit="20050912",
    motivo="00",
    cid_ext="",
    pais="105",
    inicio="19661006",
    cnae="6000001",
    sec="1922501,1931400",
    tipo_logr="AVENIDA",
    logr="REPUBLICA DO CHILE",
    numero="65",
    compl="",
    bairro="CENTRO",
    cep="20031170",
    uf="RJ",
    mun="6001",
    email="contato@petrobras.com.br",
) -> str:
    cols = [
        basico, ordem, dv, matriz, fantasia, sit, data_sit, motivo, cid_ext,
        pais, inicio, cnae, sec, tipo_logr, logr, numero, compl, bairro, cep,
        uf, mun, "21", "32249000", "", "", "", "", email, "", "",
    ]
    assert len(cols) == 30
    return ";".join(f'"{c}"' for c in cols)


def test_estabelecimento_basico():
    from services.registry.parser import iter_records

    rows = list(iter_records([_estab()], kind="estabelecimentos"))
    assert len(rows) == 1
    row = rows[0]
    assert row.ok is True
    rec = row.record
    assert rec["cnpj"] == "33000167000101"
    assert rec["cnpj_basico"] == "33000167"
    assert rec["matriz"] is True
    assert rec["nome_fantasia"] == "PETROBRAS"
    assert rec["situacao"] == "2"
    assert rec["cnae_principal"] == "6000001"
    assert rec["cnaes_secundarios"] == ["1922501", "1931400"]
    assert rec["uf"] == "RJ"
    assert rec["municipio_cod"] == "6001"
    assert str(rec["data_inicio"]) == "1966-10-06"


def test_filial_e_matriz():
    from services.registry.parser import iter_records

    mat = list(iter_records([_estab(ordem="0001", dv="01", matriz="1")], kind="estabelecimentos"))[0]
    fil = list(iter_records([_estab(ordem="0002", dv="92", matriz="2", fantasia="FILIAL")], kind="estabelecimentos"))[0]
    assert mat.record["matriz"] is True
    assert fil.record["matriz"] is False
    assert fil.record["cnpj"] == "33000167000292"


def test_latin1_com_diacriticos():
    from services.registry.parser import iter_records

    raw = _estab(logr="AVENIDA SÃO JOÃO", bairro="SÉ", fantasia="PAÇO").encode("latin-1")
    line = raw.decode("latin-1")
    row = list(iter_records([line], kind="estabelecimentos"))[0]
    assert row.ok is True
    assert row.record["logradouro"] == "AVENIDA SÃO JOÃO"
    assert row.record["bairro"] == "SÉ"


def test_email_telefones_nao_sao_extraidos():
    """Minimização (§18): contato da PJ não entra no candidato."""
    from services.registry.parser import iter_records

    rec = list(iter_records([_estab()], kind="estabelecimentos"))[0].record
    assert "email" not in rec
    assert "telefone" not in rec
    assert "telefone1" not in rec


def test_numero_sn_e_campos_vazios_preservados():
    from services.registry.parser import iter_records

    rec = list(iter_records([_estab(numero="S/N", compl="", fantasia="")], kind="estabelecimentos"))[0].record
    assert rec["numero"] == "S/N"
    assert rec["complemento"] is None
    assert rec["nome_fantasia"] is None


def test_colunas_erradas_viram_erro_sem_derrubar_lote():
    from services.registry.parser import iter_records

    lines = [_estab(), '"só";"duas"', _estab(fantasia="SEGUNDA")]
    rows = list(iter_records(lines, kind="estabelecimentos"))
    assert [r.ok for r in rows] == [True, False, True]
    assert rows[1].line_no == 2
    assert "colunas" in rows[1].error


def test_cnpj_invalido_e_rejeitado():
    from services.registry.parser import iter_records

    rows = list(iter_records([_estab(basico="123", dv="9")], kind="estabelecimentos"))
    assert rows[0].ok is False
    assert "cnpj" in rows[0].error


def test_empresa_basica_e_capital():
    from services.registry.parser import iter_records

    line = '"33000167";"PETROLEO BRASILEIRO S A PETROBRAS";"2011";"10";"100000000,00";"05";""'
    row = list(iter_records([line], kind="empresas"))[0]
    assert row.ok is True
    assert row.record["cnpj_basico"] == "33000167"
    assert row.record["razao_social"] == "PETROLEO BRASILEIRO S A PETROBRAS"
    assert row.record["porte"] == "05"
    assert row.record["capital_social"] == Decimal("100000000.00")


def test_referencia_cnae():
    from services.registry.parser import iter_records

    cnae = list(iter_records(['"6000001";"Extração de petróleo"'], kind="cnaes"))[0]
    assert cnae.ok is True
    assert cnae.record == {"codigo": "6000001", "descricao": "Extração de petróleo"}
