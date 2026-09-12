"""Histórico canônico de vínculo profissional dentro da entidade Person.

O histórico vive em ``Person.raw_data`` para manter compatibilidade com o
schema atual e, ao mesmo tempo, ter contrato estável e auditável. Cada nova
observação é normalizada, recebe fingerprint determinístico e nunca apaga
snapshots anteriores. Mudanças de empresa ou cargo geram evidência de intent.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


MAX_HISTORY = 50
MAX_CHANGES = 30


def _now_iso(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _key(value: Any) -> str:
    text = _clean(value) or ""
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _fingerprint(observation: dict[str, Any]) -> str:
    payload = {
        "company_id": _key(observation.get("company_id")),
        "company_name": _key(observation.get("company_name")),
        "title": _key(observation.get("title")),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:24]


def _same_company(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a_id, b_id = _key(a.get("company_id")), _key(b.get("company_id"))
    if a_id and b_id:
        return a_id == b_id
    return bool(_key(a.get("company_name"))) and _key(a.get("company_name")) == _key(b.get("company_name"))


class EmploymentHistoryService:
    """Normaliza e mantém histórico profissional idempotente por pessoa."""

    @staticmethod
    def normalize_observation(
        observation: dict[str, Any], *, observed_at: datetime | None = None
    ) -> dict[str, Any]:
        company_name = _clean(
            observation.get("company_name")
            or observation.get("employer")
            or observation.get("company")
        )
        company_id = _clean(observation.get("company_id"))
        title = _clean(observation.get("title") or observation.get("role") or observation.get("position"))
        if not company_name and not company_id:
            raise ValueError("employment exige company_name ou company_id")

        confidence_raw = observation.get("confidence", 0.7)
        try:
            confidence = max(0.0, min(1.0, float(confidence_raw)))
        except (TypeError, ValueError):
            confidence = 0.7
        reliability_raw = observation.get("source_reliability", confidence)
        try:
            source_reliability = max(0.0, min(1.0, float(reliability_raw)))
        except (TypeError, ValueError):
            source_reliability = confidence

        normalized = {
            "company_id": company_id,
            "company_name": company_name,
            "title": title,
            "department": _clean(observation.get("department")),
            "seniority": _clean(observation.get("seniority")),
            "source": _clean(observation.get("source")) or "unknown",
            "source_reliability": round(source_reliability, 4),
            "confidence": round(confidence, 4),
            "evidence_url": _clean(observation.get("evidence_url") or observation.get("url")),
            "external_id": _clean(observation.get("external_id") or observation.get("id")),
            "observed_at": _clean(observation.get("observed_at")) or _now_iso(observed_at),
        }
        normalized["fingerprint"] = _fingerprint(normalized)
        return normalized

    @staticmethod
    def current_observed_at(person: Any) -> str | None:
        raw = getattr(person, "raw_data", None)
        if not isinstance(raw, dict):
            return None
        current = raw.get("current_employment")
        if isinstance(current, dict):
            return current.get("last_seen_at") or current.get("observed_at")
        return None

    @staticmethod
    def latest_change_evidence(person: Any) -> dict[str, Any] | None:
        raw = getattr(person, "raw_data", None)
        if not isinstance(raw, dict):
            return None
        changes = raw.get("employment_changes")
        if not isinstance(changes, list) or not changes:
            return None
        change = changes[-1]
        if not isinstance(change, dict):
            return None
        return {
            "source": "employment_change",
            "title": change.get("title") or "Mudança profissional detectada",
            "description": change.get("description"),
            "observed_at": change.get("detected_at"),
            "confidence": change.get("confidence", 0.7),
            "source_reliability": change.get("source_reliability", 0.7),
            "signal": "JOB_CHANGE",
            "change_type": change.get("change_type"),
        }

    @staticmethod
    def observe(
        person: Any,
        observation: dict[str, Any],
        *,
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Registra uma observação e detecta troca de empresa/cargo.

        O método é idempotente para a mesma empresa+cargo. Uma observação igual
        apenas renova ``last_seen_at``; uma mudança preserva o snapshot anterior
        e abre um novo vínculo corrente.
        """
        normalized = EmploymentHistoryService.normalize_observation(
            observation, observed_at=observed_at
        )
        raw = deepcopy(getattr(person, "raw_data", None) or {})
        history = [deepcopy(item) for item in raw.get("employment_history", []) if isinstance(item, dict)]
        changes = [deepcopy(item) for item in raw.get("employment_changes", []) if isinstance(item, dict)]

        current = next((item for item in reversed(history) if not item.get("ended_at")), None)
        changed = False
        change: dict[str, Any] | None = None
        observed_iso = normalized["observed_at"]

        if current is None:
            current = {
                **normalized,
                "started_at": observed_iso,
                "last_seen_at": observed_iso,
                "ended_at": None,
            }
            history.append(current)
        elif current.get("fingerprint") == normalized["fingerprint"]:
            current.update({
                "last_seen_at": observed_iso,
                "confidence": max(float(current.get("confidence") or 0), normalized["confidence"]),
                "source_reliability": max(
                    float(current.get("source_reliability") or 0),
                    normalized["source_reliability"],
                ),
                "evidence_url": normalized.get("evidence_url") or current.get("evidence_url"),
                "external_id": normalized.get("external_id") or current.get("external_id"),
            })
        else:
            previous = deepcopy(current)
            current["ended_at"] = observed_iso
            same_company = _same_company(previous, normalized)
            change_type = "role_changed" if same_company else "employer_changed"
            current = {
                **normalized,
                "started_at": observed_iso,
                "last_seen_at": observed_iso,
                "ended_at": None,
            }
            history.append(current)
            changed = True
            from_label = " · ".join(filter(None, [previous.get("company_name"), previous.get("title")])) or "vínculo anterior"
            to_label = " · ".join(filter(None, [normalized.get("company_name"), normalized.get("title")])) or "novo vínculo"
            change = {
                "change_type": change_type,
                "from_fingerprint": previous.get("fingerprint"),
                "to_fingerprint": normalized["fingerprint"],
                "from": {
                    "company_id": previous.get("company_id"),
                    "company_name": previous.get("company_name"),
                    "title": previous.get("title"),
                },
                "to": {
                    "company_id": normalized.get("company_id"),
                    "company_name": normalized.get("company_name"),
                    "title": normalized.get("title"),
                },
                "detected_at": observed_iso,
                "confidence": normalized["confidence"],
                "source_reliability": normalized["source_reliability"],
                "source": normalized["source"],
                "title": "Mudança de empresa detectada" if change_type == "employer_changed" else "Mudança de cargo detectada",
                "description": f"{from_label} → {to_label}",
            }
            if not changes or changes[-1].get("to_fingerprint") != change["to_fingerprint"]:
                changes.append(change)

        raw["employment_history"] = history[-MAX_HISTORY:]
        raw["employment_changes"] = changes[-MAX_CHANGES:]
        raw["current_employment"] = deepcopy(current)
        setattr(person, "raw_data", raw)
        return {
            "changed": changed,
            "change": change,
            "current": deepcopy(current),
            "history_count": len(raw["employment_history"]),
        }
