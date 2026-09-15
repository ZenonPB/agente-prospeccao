"""CNPJ canônico do Registry.

Fronteira entre valor bruto da fonte e identificador válido:

- bruto: qualquer string vinda do arquivo/API;
- normalizado: máscara/espaços removidos, maiúsculas, 14 caracteres;
- válido: formato correto + dígitos verificadores corretos.

Algoritmo oficial (Receita Federal — Q&A CNPJ alfanumérico e manual SERPRO
"Cálculo dos dígitos verificadores de CNPJ alfanumérico"): 14 posições, 12
primeiras alfanuméricas, 2 últimas numéricas; cada caractere vale ASCII - 48
(dígitos mantêm 0-9); mod 11 com os mesmos pesos do numérico; resto 0 ou 1
vira 0, senão 11 - resto. O numérico legado é caso particular do mesmo
cálculo — uma única implementação cobre os dois formatos.
"""
from __future__ import annotations

import string

_CNPJ_LEN = 14
_ALNUM = frozenset(string.digits + string.ascii_uppercase)
_MASK = frozenset("./- ")

_WEIGHTS_D1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_D2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def normalize_cnpj(value: object) -> str | None:
    """Limpa máscara sem inventar dado. Retorna None se não há conteúdo."""
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    cleaned = "".join(ch for ch in text if ch not in _MASK)
    return cleaned or None


def _dv(values: list[int], weights: tuple[int, ...]) -> int:
    rest = sum(a * b for a, b in zip(values, weights)) % 11
    return 0 if rest in (0, 1) else 11 - rest


def check_digits_ok(cnpj14: str) -> bool:
    """DV oficial (numérico e alfanumérico): 12 primeiros alnum + 2 DV numéricos."""
    if len(cnpj14) != _CNPJ_LEN:
        return False
    base, dv = cnpj14[:12], cnpj14[12:]
    if any(ch not in _ALNUM for ch in base) or not dv.isdigit():
        return False
    if len(set(cnpj14)) == 1:
        return False
    values = [ord(ch) - 48 for ch in base]
    d1 = _dv(values, _WEIGHTS_D1)
    if int(dv[0]) != d1:
        return False
    d2 = _dv(values + [d1], _WEIGHTS_D2)
    return int(dv[1]) == d2


def numeric_dv_ok(cnpj14: str) -> bool:
    """DV clássico decimal (só faz sentido para CNPJs totalmente numéricos)."""
    if len(cnpj14) != _CNPJ_LEN or not cnpj14.isdigit():
        return False
    if len(set(cnpj14)) == 1:
        return False
    return check_digits_ok(cnpj14)


def is_valid_cnpj(value: object) -> bool:
    """Formato (14 posições, base alnum, DV numéricos) + DV oficial."""
    normalized = normalize_cnpj(value)
    if normalized is None or len(normalized) != _CNPJ_LEN:
        return False
    if any(ch not in _ALNUM for ch in normalized[:12]) or not normalized[12:].isdigit():
        return False
    if len(set(normalized)) == 1:
        return False
    return check_digits_ok(normalized)
