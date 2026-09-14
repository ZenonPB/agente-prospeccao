"""Contrato e normalização dos filtros compartilhados de analytics.

O DTO é deliberadamente independente de organização: o workspace é resolvido
pela dependency de autenticação e aplicado pelo ``AnalyticsService``. Nenhum
campo recebido do cliente pode substituir esse escopo.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.db.models import LeadStatus, MessageChannel, NegotiationStage


SCORE_BUCKETS = {"0-39", "40-59", "60-79", "80-100"}
ATTRIBUTIONS = {"attributed", "unattributed"}
OUTCOMES = {
    "WON", "CONVERTED", "SALE", "CLOSED_WON", "LOST", "REPLY",
    "RESPONDED", "POSITIVE_REPLY", "MEETING", "MEETING_SCHEDULED",
    "MEETING_HELD",
}

# Parâmetros antigos das rotas atuais + dimensões comerciais compartilhadas.
# Workspace nunca aparece aqui: ele vem exclusivamente da autenticação.
KNOWN_QUERY_FIELDS = {
    "from", "to", "campaign_id", "consultant_id", "offer_key",
    "offer_version", "channel", "status", "score_bucket", "outcome",
    "attribution", "search", "segment", "city", "state", "negotiation_stage",
    "cursor", "limit", "k", "sort_by", "group_by", "provider", "by",
}


class CommercialFilterDTO(BaseModel):
    """Snapshot serializável e estrito dos filtros comerciais compartilhados."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_date: str | None = Field(default=None, alias="from")
    to_date: str | None = Field(default=None, alias="to")
    campaign_id: UUID | None = None
    consultant_id: UUID | None = None
    offer_key: str | None = Field(default=None, max_length=64)
    offer_version: str | None = Field(default=None, max_length=32)
    channel: list[str] | None = None
    status: list[str] | None = None
    score_bucket: list[str] | None = None
    outcome: list[str] | None = None
    attribution: str | None = None
    search: str | None = Field(default=None, max_length=200)
    segment: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=2)
    negotiation_stage: list[str] | None = None
    cursor: str | None = Field(default=None, max_length=2048)
    limit: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("from_date", "to_date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        from datetime import date, datetime

        candidate = value.strip()
        try:
            datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            try:
                date.fromisoformat(candidate)
            except ValueError as exc:
                raise ValueError("período deve ser uma data ou ISO datetime") from exc
        return candidate

    @field_validator("offer_key", "offer_version", "search", "segment", "city", "cursor")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("state deve ser uma UF com 2 letras")
        return normalized

    @field_validator("channel")
    @classmethod
    def validate_channels(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = _normalize_list(values, upper=True)
        if normalized is None:
            return None
        allowed = {item.value for item in MessageChannel}
        unknown = sorted(set(normalized) - allowed)
        if unknown:
            raise ValueError(f"channel desconhecido: {', '.join(unknown)}")
        return normalized

    @field_validator("status")
    @classmethod
    def validate_statuses(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = _normalize_list(values, upper=True)
        allowed = {item.value for item in LeadStatus}
        unknown = sorted(set(normalized) - allowed)
        if unknown:
            raise ValueError(f"status desconhecido: {', '.join(unknown)}")
        return normalized

    @field_validator("negotiation_stage")
    @classmethod
    def validate_negotiation_stages(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = _normalize_list(values, upper=True)
        allowed = {item.value for item in NegotiationStage}
        unknown = sorted(set(normalized) - allowed)
        if unknown:
            raise ValueError(f"negotiation_stage desconhecido: {', '.join(unknown)}")
        return normalized

    @field_validator("score_bucket")
    @classmethod
    def validate_score_buckets(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = _normalize_list(values)
        unknown = sorted(set(normalized) - SCORE_BUCKETS)
        if unknown:
            raise ValueError(f"score_bucket desconhecido: {', '.join(unknown)}")
        return normalized

    @field_validator("outcome")
    @classmethod
    def validate_outcomes(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = _normalize_list(values, upper=True)
        unknown = sorted(set(normalized) - OUTCOMES)
        if unknown:
            raise ValueError(f"outcome desconhecido: {', '.join(unknown)}")
        return normalized

    @field_validator("attribution")
    @classmethod
    def validate_attribution(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ATTRIBUTIONS:
            raise ValueError("attribution deve ser 'attributed' ou 'unattributed'")
        return normalized

    @model_validator(mode="after")
    def validate_period(self) -> "CommercialFilterDTO":
        if self.from_date and self.to_date:
            from datetime import datetime, date

            def parse(value: str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return date.fromisoformat(value)

            if parse(self.from_date) > parse(self.to_date):
                raise ValueError("from não pode ser posterior a to")
        return self


def _normalize_list(values: list[str], *, upper: bool = False) -> list[str] | None:
    result: list[str] = []
    for raw in values:
        for item in str(raw).split(","):
            value = item.strip()
            if value:
                result.append(value.upper() if upper else value)
    if len(result) > 1000:
        raise ValueError("dimensão multivalorada aceita no máximo 1000 itens")
    return list(dict.fromkeys(result)) or None


def normalize_commercial_filters(raw: Mapping[str, Any]) -> CommercialFilterDTO:
    """Normaliza um mapping e rejeita campos desconhecidos explicitamente."""
    allowed = {
        "from", "to", "campaign_id", "consultant_id", "offer_key",
        "offer_version", "channel", "status", "score_bucket", "outcome",
        "attribution", "search", "segment", "city", "state", "negotiation_stage",
        "cursor", "limit",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(f"filtros desconhecidos: {', '.join(unknown)}")
    return CommercialFilterDTO(**raw)


def _query_values(request: Request) -> dict[str, Any]:
    grouped: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        if key not in KNOWN_QUERY_FIELDS:
            raise HTTPException(status_code=422, detail=f"filtro desconhecido: {key}")
        grouped.setdefault(key, []).append(value)

    scalar = {
        "from", "to", "campaign_id", "consultant_id", "offer_key",
        "offer_version", "attribution", "search", "segment", "city", "state",
        "cursor", "limit",
    }
    raw: dict[str, Any] = {}
    for key, values in grouped.items():
        if key in scalar:
            if len(values) > 1:
                raise HTTPException(status_code=422, detail=f"filtro escalar repetido: {key}")
            raw[key] = values[0]
        elif key in {"channel", "status", "score_bucket", "outcome", "negotiation_stage"}:
            raw[key] = values
    return raw


def get_commercial_filters(request: Request) -> CommercialFilterDTO:
    """Dependency FastAPI para query params estritos e compatíveis."""
    try:
        return normalize_commercial_filters(_query_values(request))
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        raise
