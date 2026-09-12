"""Verificação passiva de telefone sem chamadas externas.

A classificação é deliberadamente conservadora: formato plausível não significa
linha existente. Mantemos UNKNOWN separado de INVALID para não contaminar score.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any


class PhoneVerificationState(str, Enum):
    VERIFIED = "VERIFIED"
    LIKELY_VALID = "LIKELY_VALID"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


def _raw_digits(value: str | None) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def normalize_phone(value: str | None, *, country_code: str = "55") -> str | None:
    digits = _raw_digits(value)
    if not digits:
        return None
    if len(digits) in {10, 11}:
        digits = country_code + digits
    return f"+{digits}"


def verify_phone(value: str | None, *, provider_verified: bool = False) -> dict[str, Any]:
    raw_digits = _raw_digits(value)
    normalized = normalize_phone(value)
    if normalized is None:
        return {"state": PhoneVerificationState.UNKNOWN.value, "normalized": None, "confidence": 0, "reason": "missing"}

    if len(raw_digits) < 10 or len(raw_digits) > 15:
        return {"state": PhoneVerificationState.INVALID.value, "normalized": normalized, "confidence": 0, "reason": "invalid_length"}
    # Checa a entrada nacional/internacional antes de prefixar DDI. Caso contrário,
    # `11111111111` viraria `5511111111111` e deixaria de parecer degenerado.
    if len(set(raw_digits)) == 1:
        return {"state": PhoneVerificationState.INVALID.value, "normalized": normalized, "confidence": 0, "reason": "repeated_digits"}

    digits = normalized[1:]
    if not digits.isdigit() or len(digits) < 10 or len(digits) > 15:
        return {"state": PhoneVerificationState.INVALID.value, "normalized": normalized, "confidence": 0, "reason": "invalid_length"}

    if provider_verified:
        return {"state": PhoneVerificationState.VERIFIED.value, "normalized": normalized, "confidence": 95, "reason": "provider_verified"}

    if digits.startswith("55") and len(digits) in {12, 13}:
        national = digits[2:]
        ddd = int(national[:2])
        if 11 <= ddd <= 99:
            if len(national) == 11 and national[2] == "9":
                return {"state": PhoneVerificationState.LIKELY_VALID.value, "normalized": normalized, "confidence": 75, "reason": "br_mobile_format"}
            if len(national) == 10:
                return {"state": PhoneVerificationState.LIKELY_VALID.value, "normalized": normalized, "confidence": 65, "reason": "br_landline_format"}

    return {"state": PhoneVerificationState.UNKNOWN.value, "normalized": normalized, "confidence": 25, "reason": "unverified_format"}
