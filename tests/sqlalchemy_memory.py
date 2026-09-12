"""Sessão em memória que avalia critérios SQLAlchemy reais contra linhas de teste.

Serve aos testes de invariante que precisam do **filtro do próprio serviço**
decidindo o resultado, sem Postgres: em vez de simular a resposta da consulta,
aqui os objetos `BinaryExpression`/`BooleanClauseList` montados pelo código de
produção são avaliados linha a linha. Se o serviço esquecer uma cláusula, a
linha errada entra no resultado — e o teste falha por comportamento.

Cada "linha" é um dict `{nome_da_tabela: entidade}`, o que cobre consultas com
join: a consulta declara a tabela-alvo e as demais entram como colunas
disponíveis para o critério.

Operadores suportados: `and_`, `or_`, `eq`, `ne`, `is_`, `is_not`, `in_`,
`not_in`, `le`, `lt`, `ge`, `gt`. Funções suportadas: `coalesce`.
"""
import uuid

from sqlalchemy import Column
from sqlalchemy.sql.elements import (
    BinaryExpression,
    BindParameter,
    BooleanClauseList,
    False_,
    Null,
    TextClause,
    True_,
    UnaryExpression,
)
from sqlalchemy.sql.functions import Function


def normalizar(valor):
    """UUID e str comparam por texto; o resto compara por igualdade nativa."""
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, (list, tuple, set)):
        return [normalizar(item) for item in valor]
    return valor


def valor_operando(operando, linha):
    if isinstance(operando, Null):
        return None
    # `coluna.is_(False)` / `is_(True)` chegam como literais próprios, não como
    # bind params — comparação por identidade preserva a semântica de `is_`.
    if isinstance(operando, False_):
        return False
    if isinstance(operando, True_):
        return True
    if isinstance(operando, BindParameter):
        return normalizar(operando.value)
    if isinstance(operando, Function):
        # `coalesce` aparece em filtro que precisa concordar com índice de
        # expressão no banco (ex.: oferta nula tratada como sentinel).
        if operando.name != "coalesce":
            raise AssertionError(
                f"função não suportada pelo harness: {operando.name}",
            )
        for clausula in operando.clauses:
            valor = valor_operando(clausula, linha)
            if valor is not None:
                return valor
        return None
    if isinstance(operando, TextClause):
        # `text("offer_key")` referencia coluna crua; `text("'unknown'")` é
        # literal SQL — só o segundo tem valor avaliável aqui.
        cru = operando.text.strip()
        if cru.startswith("'") and cru.endswith("'"):
            return cru[1:-1]
        for entidade in linha.values():
            if entidade is not None and hasattr(entidade, cru):
                return normalizar(getattr(entidade, cru))
        return None
    if isinstance(operando, Column):
        tabela = operando.table.name
        assert tabela in linha, (
            f"consulta não suportada pelo harness: tabela '{tabela}' "
            "não faz parte da linha avaliada"
        )
        entidade = linha[tabela]
        if entidade is None:
            return None
        return normalizar(getattr(entidade, operando.key, None))
    raise AssertionError(f"operando não suportado pelo harness: {operando!r}")


def avaliar(criterio, linha) -> bool:
    if isinstance(criterio, BooleanClauseList):
        nome = getattr(criterio.operator, "__name__", "")
        resultados = [avaliar(c, linha) for c in criterio.clauses]
        if nome == "or_":
            return any(resultados)
        if nome == "and_":
            return all(resultados)
        raise AssertionError(f"conector não suportado pelo harness: {nome}")

    if isinstance(criterio, BinaryExpression):
        nome = getattr(criterio.operator, "__name__", "")
        esquerda = valor_operando(criterio.left, linha)
        direita = valor_operando(criterio.right, linha)
        if nome == "eq":
            return esquerda == direita
        if nome == "ne":
            return esquerda != direita
        if nome == "is_":
            return esquerda is direita
        if nome in ("is_not", "isnot"):
            return esquerda is not direita
        if nome in ("in_op", "not_in_op"):
            # `NULL IN (...)` e `NULL NOT IN (...)` não selecionam a linha.
            if esquerda is None:
                return False
            pertence = esquerda in (direita or [])
            return pertence if nome == "in_op" else not pertence
        if esquerda is None or direita is None:
            return False
        if nome == "le":
            return esquerda <= direita
        if nome == "lt":
            return esquerda < direita
        if nome == "ge":
            return esquerda >= direita
        if nome == "gt":
            return esquerda > direita
        raise AssertionError(f"operador não suportado pelo harness: {nome}")

    raise AssertionError(f"critério não suportado pelo harness: {criterio!r}")


class ConsultaMemoria:
    """Reproduz o subconjunto de `Query` usado pelos serviços sob teste.

    `tabela_alvo` é a tabela cuja entidade é devolvida por `all()`/`first()`.
    `colunas` (opcional) faz a consulta devolver tuplas de atributos, como uma
    `query(Model.coluna)` do SQLAlchemy.
    """

    def __init__(self, tabela_alvo, linhas, colunas=None):
        self._tabela_alvo = tabela_alvo
        self._linhas = list(linhas)
        self._colunas = list(colunas) if colunas else None
        self._criterios = []
        self._ordem = None

    def outerjoin(self, *_a, **_k):
        # As linhas do harness já vêm pareadas.
        return self

    def join(self, *_a, **_k):
        return self

    def filter(self, *criterios):
        self._criterios.extend(criterios)
        return self

    def order_by(self, *clausulas):
        if clausulas:
            self._ordem = clausulas[0]
        return self

    def _selecionadas(self):
        linhas = [l for l in self._linhas if all(avaliar(c, l) for c in self._criterios)]
        if self._ordem is not None:
            clausula = self._ordem
            decrescente = False
            if isinstance(clausula, UnaryExpression):
                decrescente = "desc" in getattr(clausula.modifier, "__name__", "")
                clausula = clausula.element
            chave = clausula
            linhas.sort(
                key=lambda l: (valor_operando(chave, l) is not None, valor_operando(chave, l)),
                reverse=decrescente,
            )
        entidades = [l[self._tabela_alvo] for l in linhas]
        if self._colunas is None:
            return entidades
        return [tuple(getattr(e, coluna, None) for coluna in self._colunas) for e in entidades]

    def all(self):
        return self._selecionadas()

    def first(self):
        selecionadas = self._selecionadas()
        return selecionadas[0] if selecionadas else None
