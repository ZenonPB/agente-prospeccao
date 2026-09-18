"""Rótulos de área/cargo não podem se passar por pessoa decisora.

Contrato: um telefone/e-mail genérico da empresa nunca vira "contato
direto do decisor". Nomes como "Equipe de Vendas" ou "Atendimento"
são canal da empresa (GENERIC_CHANNEL), não pessoa (DIRECT_*).
"""
from services.prospecting.contactability import assess_contactability


def test_nome_de_area_nao_vira_pessoa_diretamente_contatavel():
    result = assess_contactability([{
        "name": "Equipe de Vendas",
        "email": "vendas@empresa.com.br",
        "confidence": 80,
    }])
    assert result["person_found"] is False
    assert result["status"] == "GENERIC_CHANNEL"


def test_nome_de_atendimento_com_telefone_e_canal_generico():
    result = assess_contactability([{
        "name": "Atendimento",
        "phone": "16999999999",
        "confidence": 80,
    }])
    assert result["person_found"] is False
    assert result["status"] == "GENERIC_CHANNEL"
