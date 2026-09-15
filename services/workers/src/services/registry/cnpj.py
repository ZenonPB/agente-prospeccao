"""CNPJ canônico do Registry.

Fronteira entre valor bruto da fonte e identificador válido:

- bruto: qualquer string vinda do arquivo/API;
- normalizado: máscara/espaços removidos, maiúsculas, 14 caracteres;
- válido: formato correto + (se numérico) dígitos verificadores corretos.

CNPJs alfanuméricos (Receita, a partir de jul/2026) passam só na validação
de formato — o DV clássico é decimal e não se aplica a eles. Lixo nunca vira
identificador válido: `normalize_cnpj` não conserta, só limpa.
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


def numeric_dv_ok(cnpj14: str) -> bool:
    """Verifica os dígitos verificadores clássicos (só faz sentido p/ numérico)."""
    if len(cnpj14) != _CNPJ_LEN or not cnpj14.isdigit():
        return False
    if len(set(cnpj14)) == 1:
        return False
    digits = [int(ch) for ch in cnpj14]
    d1 = 11 - (sum(a * b for a, b in zip(digits[:12], _WEIGHTS_D1)) % 11)
    d1 = 0 if d1 >= 10 else d1
    if digits[12] != d1:
        return False
    d2 = 11 - (sum(a * b for a, b in zip(digits[:13], _WEIGHTS_D2)) % 11)
    d2 = 0 if d2 >= 10 else d2
    return digits[13] == d2


def is_valid_cnpj(value: object) -> bool:
    """Formato (14 alnum, não uniforme) + DV quando numérico."""
    normalized = normalize_cnpj(value)
    if normalized is None or len(normalized) != _CNPJ_LEN:
        return False
    if any(ch not in _ALNUM for ch in normalized):
        return False
    if len(set(normalized)) == 1:
        return False
    if normalized.isdigit():
        return numeric_dv_ok(normalized)
    return True
