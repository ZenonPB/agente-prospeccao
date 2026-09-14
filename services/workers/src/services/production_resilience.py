"""Primitivas pequenas e determinísticas para resiliência em produção.

Sem estado global por tenant: chaves de cache sempre incluem organization_id,
retries são limitados e circuit breaker não mascara erro permanente.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
from typing import Iterable


TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


def tenant_cache_key(organization_id: object, namespace: str, *parts: object) -> str:
    org = str(organization_id or "").strip()
    ns = str(namespace or "").strip()
    if not org or not ns:
        raise ValueError("organization_id e namespace são obrigatórios")
    payload = "|".join(str(item) for item in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"tenant:{org}:{ns}:{digest}"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_seconds: float = 1.0
    cap_seconds: float = 60.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts deve ficar entre 1 e 10")
        if self.base_seconds <= 0 or self.cap_seconds < self.base_seconds:
            raise ValueError("janela de backoff inválida")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio deve ficar entre 0 e 1")

    def delay(self, attempt: int, *, retry_after: float | None = None, seed: int | None = None) -> float:
        if attempt < 1:
            raise ValueError("attempt começa em 1")
        if retry_after is not None and retry_after >= 0:
            return min(self.cap_seconds, float(retry_after))
        raw = min(self.cap_seconds, self.base_seconds * (2 ** (attempt - 1)))
        rng = random.Random(seed)
        jitter = raw * self.jitter_ratio * rng.uniform(-1.0, 1.0)
        return round(max(0.0, min(self.cap_seconds, raw + jitter)), 3)

    def should_retry(self, attempt: int, *, status_code: int | None = None, network_error: bool = False) -> bool:
        if attempt >= self.max_attempts:
            return False
        return network_error or status_code in TRANSIENT_HTTP_STATUSES


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_successes: int = 2
    failures: int = 0
    successes_after_open: int = 0
    state: str = "CLOSED"

    def __post_init__(self) -> None:
        if self.failure_threshold < 1 or self.recovery_successes < 1:
            raise ValueError("thresholds precisam ser positivos")

    def allow(self) -> bool:
        return self.state in {"CLOSED", "HALF_OPEN"}

    def record_failure(self, *, transient: bool = True) -> None:
        if not transient:
            return
        self.failures += 1
        self.successes_after_open = 0
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"

    def probe(self) -> None:
        if self.state == "OPEN":
            self.state = "HALF_OPEN"
            self.successes_after_open = 0

    def record_success(self) -> None:
        if self.state == "HALF_OPEN":
            self.successes_after_open += 1
            if self.successes_after_open >= self.recovery_successes:
                self.state = "CLOSED"
                self.failures = 0
                self.successes_after_open = 0
        elif self.state == "CLOSED":
            self.failures = 0


def redact_sensitive(mapping: dict, sensitive_keys: Iterable[str] = ()) -> dict:
    """Redige segredos por nome sem modificar o payload original."""
    deny = {str(key).lower() for key in sensitive_keys}
    deny.update({"authorization", "api_key", "apikey", "token", "password", "secret", "client_secret"})
    result = {}
    for key, value in mapping.items():
        lowered = str(key).lower()
        result[key] = "***REDACTED***" if any(item in lowered for item in deny) else value
    return result
