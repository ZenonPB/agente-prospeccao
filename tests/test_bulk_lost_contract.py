"""Contrato estático da ação em lote de perda no painel de oportunidades.

`apps/web` não tem runner de teste de componente, então o contrato observável do
componente é verificado aqui: o arquivo-fonte é lido como texto e as asserções
recaem sobre o preview/execute bulk, o diálogo de motivo que precede o preview e
o resumo das decisões de execução.

As asserções usam expressões tolerantes a espaço e quebra de linha — formatação
não muda o resultado — mas específicas o suficiente para reprovar um retorno ao
PATCH individual de status ou a uma execução de `PERDIDO` sem motivo.

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

_PREVIEW_BULK = re.compile(r"previewBulk\s*\.\s*mutateAsync")
_EXECUTE_BULK = re.compile(r"executeBulk\s*\.\s*mutateAsync")

# O texto da UI é PT-BR e a redação pode variar; a asserção olha o radical.
_RADICAL_SUCESSO = r"aceit|aplicad|sucess"
_RADICAL_FALHA = r"rejeit|falh|pendên|erro"

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


def test_componente_importa_e_instancia_os_hooks_bulk():
    """Preview e execução usam os endpoints bulk, sem hook individual de lead."""
    fonte = _fonte()
    assert re.search(
        r"import\s*\{[^}]*\busePreviewBulkLeads\b[^}]*\}\s*from\s*['\"]@/hooks/use-api['\"]",
        fonte,
        re.S,
    ), "o componente precisa importar `usePreviewBulkLeads`"
    assert re.search(
        r"import\s*\{[^}]*\buseExecuteBulkLeads\b[^}]*\}\s*from\s*['\"]@/hooks/use-api['\"]",
        fonte,
        re.S,
    ), "o componente precisa importar `useExecuteBulkLeads`"
    assert re.search(r"const\s+previewBulk\s*=\s*usePreviewBulkLeads\s*\(\s*\)", fonte)
    assert re.search(r"const\s+executeBulk\s*=\s*useExecuteBulkLeads\s*\(\s*\)", fonte)
    assert not re.search(r"\buseMarkLost\b|\bmarkLost\s*\.\s*mutate", fonte), (
        "a ação bulk não pode voltar a usar marcação individual"
    )
    assert not re.search(r"\bupdateStatus\s*\.\s*mutate(?:Async)?", fonte), (
        "a ação bulk não pode usar o PATCH genérico de status"
    )


def test_preview_do_lote_chama_o_endpoint_bulk():
    """A validação prévia passa o comando inteiro para o hook bulk."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(fonte, _PREVIEW_BULK, "preview da operação em lote")
    assert nome == "previewBulkOperation", (
        f"o preview bulk precisa ser orquestrado por `previewBulkOperation`, não `{nome}`"
    )
    assert re.search(r"previewBulk\s*\.\s*mutateAsync\s*\(\s*command\s*\)", corpo), (
        f"`{nome}` precisa enviar o comando ao preview bulk"
    )


def test_execucao_do_lote_chama_o_endpoint_bulk():
    """A confirmação executa somente os itens aceitos pelo executor bulk."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(fonte, _EXECUTE_BULK, "execução da operação em lote")
    assert nome == "executePreview", (
        f"a execução bulk precisa ser orquestrada por `executePreview`, não `{nome}`"
    )
    assert re.search(r"executeBulk\s*\.\s*mutateAsync\s*\(\s*\{", corpo), (
        f"`{nome}` precisa enviar a operação ao executor bulk"
    )
    assert re.search(r"bulkPreview\.accepted_ids", corpo), (
        f"`{nome}` precisa respeitar os itens aceitos pelo preview"
    )


def test_comando_de_perdido_seleciona_leads_e_envia_motivo():
    """A confirmação constrói um comando status PERDIDO com motivo e versão."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(
        fonte, re.compile(r"lost_reason\s*:\s*bulkLostReason"),
        "comando de perda em lote",
    )
    assert re.search(r"selectedLeads", corpo), (
        f"`{nome}` precisa usar os leads selecionados"
    )
    assert re.search(r"operation\s*:\s*['\"]status['\"]", corpo)
    assert re.search(r"status\s*:\s*['\"]PERDIDO['\"]", corpo)
    assert re.search(r"lost_reason\s*:\s*bulkLostReason", corpo)
    assert re.search(r"expected_updated_at\s*:\s*expectedVersionsFor", corpo)
    assert re.search(r"previewBulkOperation", corpo), (
        f"`{nome}` precisa encaminhar o comando para o preview"
    )


def test_lote_de_perdido_abre_o_dialogo_antes_de_qualquer_requisicao():
    """O desvio de `PERDIDO` abre o motivo e retorna antes do preview."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(fonte, re.compile(r"setBulkLostOpen"), "desvio de PERDIDO")
    guarda = re.search(r"PERDIDO", corpo)
    assert guarda, f"`{nome}` não desvia PERDIDO para o diálogo de motivo"
    saida = re.search(r"\breturn\b", corpo[guarda.end() :])
    assert saida, f"o desvio de PERDIDO em `{nome}` precisa retornar antes do preview"
    ramo = corpo[guarda.end() : guarda.end() + saida.end()]
    assert re.search(r"setBulkLostReason\s*\(", ramo)
    assert re.search(r"setBulkLostOpen\s*\(\s*true\s*\)", ramo)
    assert not re.search(r"previewBulkOperation|\.\s*mutate(?:Async)?", ramo), (
        f"o desvio de PERDIDO em `{nome}` não pode emitir requisição antes do motivo"
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
    ), "as opções de motivo precisam vir de `LOST_REASON_OPTIONS`"
    assert re.search(r"LOST_REASON_OPTIONS\s*\.\s*map", fonte), (
        "o diálogo precisa renderizar as opções do enum compartilhado"
    )


def test_resumo_do_lote_informa_aceitos_rejeitados_e_falhos():
    """O resumo da execução traz contagens de aceitos/sucessos e pendências."""
    fonte = _fonte()
    nome, corpo = _funcao_que_contem(fonte, _EXECUTE_BULK, "resumo da execução em lote")
    assert re.search(r"result\.accepted", corpo), (
        f"`{nome}` precisa informar a quantidade de itens aceitos/aplicados"
    )
    assert re.search(r"result\.rejected", corpo), (
        f"`{nome}` precisa informar a quantidade de itens rejeitados"
    )
    assert re.search(r"result\.failed", corpo), (
        f"`{nome}` precisa informar a quantidade de itens com falha"
    )
    mensagens = [texto for texto in re.findall(r"`[^`]*`", corpo) if "${" in texto]
    assert any(re.search(_RADICAL_SUCESSO, texto, re.I) for texto in mensagens), (
        f"`{nome}` precisa usar mensagem de sucesso/aceitos no resumo"
    )
    assert any(re.search(_RADICAL_FALHA, texto, re.I) for texto in mensagens), (
        f"`{nome}` precisa usar mensagem de rejeitados/falhos no resumo"
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
