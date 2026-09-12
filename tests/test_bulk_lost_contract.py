"""Contrato estático da ação em lote de perda no painel de oportunidades.

`apps/web` não tem runner de teste de componente, então o contrato observável do
componente é verificado aqui: o arquivo-fonte é lido como texto e as asserções
recaem sobre o caminho de API usado no lote, o diálogo de motivo que precede o
disparo e o resumo com contagem de sucessos e de falhas.

As asserções usam expressões tolerantes a espaço e quebra de linha — formatação
não muda o resultado — mas específicas o suficiente para reprovar o caminho que
manda `PERDIDO` pelo PATCH genérico de status, que aceita lead sem motivo.

**Validates: Requirements 6.1, 6.2, 21.1**
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, Tuple

_COMPONENTE = (
    Path(__file__).resolve().parents[1]
    / "apps"
    / "web"
    / "src"
    / "components"
    / "oportunidades"
    / "lead-list.tsx"
)

# Chamada do PATCH genérico de status (o caminho que aceita PERDIDO sem motivo).
_PATCH_GENERICO = re.compile(r"updateStatus\s*\.\s*mutate")

# Chamada da marcação de perda, que exige motivo no corpo da requisição.
_MARCACAO_COM_MOTIVO = re.compile(r"markLost\s*\.\s*mutate")

# O texto da UI é PT-BR e a redação pode variar; a asserção olha o radical.
_RADICAL_SUCESSO = r"sucess|marcad|movid|atualizad|perdid"
_RADICAL_FALHA = r"falh|erro"

# Nome de estado que controla o diálogo de motivo.
_NOME_DE_MOTIVO = re.compile(r"lost|perd|motivo|reason", re.IGNORECASE)


def _fonte() -> str:
    assert _COMPONENTE.exists(), f"componente não encontrado: {_COMPONENTE}"
    return _COMPONENTE.read_text(encoding="utf-8")


def _fim_do_bloco(fonte: str, abre: int) -> int:
    """Índice logo após a chave que fecha o bloco aberto em `abre`."""
    profundidade = 0
    for i in range(abre, len(fonte)):
        if fonte[i] == "{":
            profundidade += 1
        elif fonte[i] == "}":
            profundidade -= 1
            if profundidade == 0:
                return i + 1
    return len(fonte)


def _blocos(fonte: str) -> Iterator[Tuple[str, str]]:
    """Corpos de função nomeada do arquivo, como (nome, texto do corpo)."""
    for declaracao in re.finditer(r"\b(?:const|function)\s+([A-Za-z_$][\w$]*)", fonte):
        abre = fonte.find("{", declaracao.end())
        if abre == -1:
            continue
        entre = fonte[declaracao.end() : abre]
        # Só interessa corpo de função: assinatura de `function` ou seta.
        if ";" in entre or ("=>" not in entre and not entre.lstrip().startswith("(")):
            continue
        yield declaracao.group(1), fonte[abre : _fim_do_bloco(fonte, abre)]


def _funcao_que_contem(fonte: str, padrao: re.Pattern[str], descricao: str) -> Tuple[str, str]:
    """Menor função nomeada cujo corpo casa com `padrao`."""
    candidatos = [
        (len(corpo), nome, corpo)
        for nome, corpo in _blocos(fonte)
        if padrao.search(corpo)
    ]
    assert candidatos, f"nenhuma função do componente {descricao}"
    _, nome, corpo = min(candidatos)
    return nome, corpo


def _estados(fonte: str) -> Iterator[str]:
    """Nomes de estado declarados por `useState` desestruturado."""
    for estado in re.finditer(
        r"const\s*\[\s*([A-Za-z_$][\w$]*)\s*,\s*(set[A-Za-z_$][\w$]*)\s*\]\s*=\s*useState",
        fonte,
    ):
        yield estado.group(1)


def test_componente_importa_o_hook_de_marcacao_com_motivo():
    """O lote de perda precisa do hook que exige motivo, não do PATCH genérico."""
    fonte = _fonte()
    assert re.search(
        r"import\s*\{[^}]*\buseMarkLost\b[^}]*\}\s*from\s*['\"]@/hooks/use-api['\"]",
        fonte,
        re.S,
    ), "o componente precisa importar `useMarkLost` de `@/hooks/use-api`"
    assert re.search(
        r"const\s+markLost\s*=\s*useMarkLost\s*\(\s*\)", fonte
    ), "o componente precisa instanciar `useMarkLost` para o lote de perda"


def test_lote_de_perdido_dispara_a_marcacao_com_motivo_por_lead():
    """A confirmação do motivo dispara a marcação de perda lead por lead."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(
        fonte, _MARCACAO_COM_MOTIVO, "dispara `markLost` na ação em lote"
    )
    assert re.search(r"selectedLeads|selected\b", corpo), (
        f"`{nome}` precisa percorrer os leads selecionados ao marcar a perda em lote"
    )
    assert re.search(r"lost_reason|lostReason", corpo), (
        f"`{nome}` precisa enviar o motivo escolhido em cada marcação"
    )


def test_lote_de_perdido_nao_usa_o_patch_generico_de_status():
    """`PERDIDO` é desviado antes de qualquer chamada ao PATCH genérico."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(
        fonte, _PATCH_GENERICO, "chama o PATCH genérico de status em lote"
    )
    guarda = re.search(r"PERDIDO", corpo)
    assert guarda, (
        f"`{nome}` manda qualquer status pelo PATCH genérico, incluindo PERDIDO sem motivo"
    )
    chamada = _PATCH_GENERICO.search(corpo)
    assert chamada is not None
    assert guarda.start() < chamada.start(), (
        f"em `{nome}` a guarda de PERDIDO precisa vir antes da chamada do PATCH genérico"
    )
    assert re.search(r"\breturn\b", corpo[guarda.end() : chamada.start()]), (
        f"em `{nome}` a guarda de PERDIDO precisa retornar antes do PATCH genérico"
    )


def test_componente_declara_o_dialogo_de_motivo_do_lote():
    """Existe diálogo de motivo controlado por estado no próprio componente."""
    fonte = _fonte()
    estados = [nome for nome in _estados(fonte) if _NOME_DE_MOTIVO.search(nome)]
    assert estados, (
        "o componente precisa de estado que controle o diálogo de motivo do lote"
    )
    assert re.search(r"<(?=[A-Z])[\w.]*(?:Dialog|Modal|Motivo|Lost)", fonte), (
        "o componente precisa renderizar o diálogo de motivo do lote"
    )


def test_dialogo_de_motivo_reaproveita_o_enum_de_lost_reason():
    """As opções de motivo vêm do enum compartilhado, sem lista paralela."""
    fonte = _fonte()
    assert re.search(
        r"import\s*\{[^}]*\bLOST_REASON_OPTIONS\b[^}]*\}\s*from\s*['\"]@/hooks/use-api['\"]",
        fonte,
        re.S,
    ), "as opções de motivo precisam vir de `LOST_REASON_OPTIONS` em `@/hooks/use-api`"


def test_lote_de_perdido_abre_o_dialogo_antes_de_qualquer_requisicao():
    """O desvio de `PERDIDO` abre o diálogo e sai sem emitir requisição."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(
        fonte, _PATCH_GENERICO, "chama o PATCH genérico de status em lote"
    )
    guarda = re.search(r"PERDIDO", corpo)
    assert guarda, f"`{nome}` não desvia PERDIDO para o diálogo de motivo"
    saida = re.search(r"\breturn\b", corpo[guarda.end() :])
    assert saida, f"o desvio de PERDIDO em `{nome}` precisa retornar antes do disparo"
    ramo = corpo[guarda.end() : guarda.end() + saida.end()]
    assert re.search(r"set[A-Za-z_$][\w$]*\s*\(", ramo), (
        f"o desvio de PERDIDO em `{nome}` precisa abrir o diálogo de motivo"
    )
    assert not re.search(r"\.\s*mutate", ramo), (
        f"o desvio de PERDIDO em `{nome}` não pode emitir requisição antes do motivo"
    )


def test_resumo_do_lote_informa_sucessos_e_falhas():
    """O resumo do lote traz a contagem de sucessos e a de falhas."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(
        fonte, _MARCACAO_COM_MOTIVO, "dispara `markLost` na ação em lote"
    )
    mensagens = [texto for texto in re.findall(r"`[^`]*`", corpo) if "${" in texto]
    assert any(re.search(_RADICAL_SUCESSO, texto, re.I) for texto in mensagens), (
        f"`{nome}` precisa informar a quantidade de leads marcados com sucesso"
    )
    assert any(re.search(_RADICAL_FALHA, texto, re.I) for texto in mensagens), (
        f"`{nome}` precisa informar a quantidade de falhas do lote"
    )


def test_opcao_de_marcar_como_perdido_continua_disponivel_no_lote():
    """Regressão: a ação em lote de perda continua ofertada ao consultor."""
    fonte = _fonte()
    opcoes = re.search(r"bulkStatusOptions\s*=\s*\[(.*?)\]\s*;", fonte, re.S)
    assert opcoes, "o componente precisa declarar as opções de ação em lote"
    assert re.search(r"['\"]PERDIDO['\"]", opcoes.group(1)), (
        "a opção de marcar como perdido precisa continuar no menu de lote"
    )
    assert re.search(r"perdido", opcoes.group(1), re.I), (
        "a opção de perda precisa ter rótulo em português"
    )
