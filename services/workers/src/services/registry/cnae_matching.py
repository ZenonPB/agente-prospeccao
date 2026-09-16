"""Contrato de matching de CNAE para o Brazil Company Registry.

Semântica explícita (fail-closed):

- CNAE completo: 7 dígitos (ex.: "8630504", formatado "8630-5/04") → match exato.
- Prefixo de divisão: 2 dígitos (ex.: "28") → faixa de divisão 2800000–2899999.
- Prefixo de grupo/classe: 3–6 dígitos → faixa ancorada (ex.: "863" →
  8630000–8639999). Granularidades intermediárias são suportadas como prefixo
  porque o Registry armazena o código canônico de 7 dígitos.
- Entrada inválida (vazia, não numérica após normalização, >7 dígitos) →
  ValueError (fail-closed no chamador).
- Entrada semanticamente desconhecida → o chamador decide UNKNOWN/unsupported;
  este módulo nunca faz match silencioso errado.

Tudo aqui é puro (sem I/O, sem DB): o SQL set-based vive em
`services/registry/search.py`, que consome `CnaeFilter`.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


EXACT_LEN = 7
MIN_PREFIX_LEN = 2
MAX_PREFIX_LEN = EXACT_LEN - 1
_FORMATTED_EXACT_RE = re.compile(r"^(?:\d{4}-\d/\d{2}|\d{2}\.\d{2}-\d-\d{2})$")


@dataclass(frozen=True)
class CnaeFilter:
    """Filtro CNAE normalizado: exatos e/ou faixas de prefixo (start..end)."""

    exact: tuple[str, ...] = ()
    prefixes: tuple[tuple[str, str], ...] = ()
    prefix_tokens: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.exact and not self.prefixes

def normalize_cnae_token(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        raise ValueError(f"CNAE inválido: {raw!r}")
    if text.isdigit():
        digits = text
    elif _FORMATTED_EXACT_RE.fullmatch(text):
        digits = "".join(ch for ch in text if ch.isdigit())
    else:
        raise ValueError(f"CNAE inválido: {raw!r}")
    if not digits:
        raise ValueError(f"CNAE inválido: {raw!r}")
    if len(digits) > EXACT_LEN:
        raise ValueError(f"CNAE inválido (mais de 7 dígitos): {raw!r}")
    return digits


def cnae_prefix_bounds(prefix: object) -> tuple[str, str]:
    """Retorna a faixa canônica de um prefixo CNAE de 2 a 6 dígitos."""
    digits = normalize_cnae_token(prefix)
    if not MIN_PREFIX_LEN <= len(digits) <= MAX_PREFIX_LEN:
        raise ValueError(f"prefixo CNAE inválido: {prefix!r}")
    return (
        digits + "0" * (EXACT_LEN - len(digits)),
        digits + "9" * (EXACT_LEN - len(digits)),
    )


def parse_cnae_tokens(tokens: Iterable[object] | None) -> CnaeFilter:
    """Converte tokens de `icp.cnaes` em filtro explícito exato/prefixo.

    Deduplica preservando determinismo (ordem de primeira aparição, saída
    ordenada). Tokens inválidos levantam ValueError — o chamador trata como
    configuração inválida (fail-closed), nunca como match silencioso.
    """
    exact: list[str] = []
    prefixes: list[tuple[str, str]] = []
    prefix_tokens: list[str] = []
    if not tokens:
        return CnaeFilter()
    for raw in tokens:
        digits = normalize_cnae_token(raw)
        if len(digits) == EXACT_LEN:
            if digits not in exact:
                exact.append(digits)
        else:
            start, end = cnae_prefix_bounds(digits)
            if (start, end) not in prefixes:
                prefixes.append((start, end))
            if digits not in prefix_tokens:
                prefix_tokens.append(digits)
    return CnaeFilter(
        exact=tuple(sorted(exact)),
        prefixes=tuple(sorted(prefixes)),
        prefix_tokens=tuple(sorted(prefix_tokens)),
    )
