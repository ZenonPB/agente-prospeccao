"""CrmService — lançamento rápido de leads ("CRM Paste").

O consultor cola texto livre (LinkedIn, WhatsApp, anotações) e a IA extrai
os dados estruturados no formato da planilha de CRM (aba por consultor).
Aqui ficam as três peças da feature:

- `EXTRACTION_SYSTEM_PROMPT` / `extract_leads` — chamada ao Groq
  (`provider_client.groq_json_chat`, com pacing/retry/cota centralizados).
- Funções puras de normalização (`add_business_days`, `normalize_items`) —
  inferência de datas e follow-ups padrão da planilha (pitch+4 dias úteis →
  1º FU, +3 → 2º, +3 → 3º).
- `insert_items` — dedupe por (pessoa + empresa) na organização e inserção
  no modelo existente (Lead + Contact primário + FollowUps agendados),
  sem tabela nova.
"""
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# Serviços dos workers (fonte única de provider_client/settings).
_workers_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "workers", "src")
)
if _workers_path not in sys.path:
    sys.path.insert(0, _workers_path)
from config.settings import settings as workers_settings  # noqa: E402
from services.provider_client import groq_json_chat  # noqa: E402

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

EXTRACTION_SYSTEM_PROMPT = """Você é um parser de CRM. Extraia leads do texto e retorne SOMENTE JSON válido, sem texto adicional.

Formato: {"leads": [ ... ]} — cada objeto:
{"lead": "Nome completo", "empresa": "Nome da empresa", "prospeccao": "YYYY-MM-DD", "pitch_enviado": true|false, "pitch_data": "YYYY-MM-DD"|null, "follow_up_1": "YYYY-MM-DD"|null, "follow_up_2": "YYYY-MM-DD"|null, "follow_up_3": "YYYY-MM-DD"|null, "respondeu": "SIM"|"NÃO"|null, "cargo": "string"|null, "observacoes": "string"|null}

Regras de inferência de datas:
- Se prospecção não informada: use a data de hoje.
- Se pitch não informado mas pitch_enviado=true: use a mesma data da prospecção.
- Follow-ups padrão (se não informados): pitch+4 dias úteis → 1ºFU; +3 dias úteis → 2ºFU; +3 dias úteis → 3ºFU (pule sábados e domingos).
- Se o lead respondeu positiva ou negativamente: respondeu="SIM".
- Se claramente não respondeu ainda: respondeu="NÃO".
- Se não há informação: respondeu=null.

Datas podem vir em DD/MM/AAAA — normalize para YYYY-MM-DD. Ignore trechos que não forem leads."""


def add_business_days(start: date, days: int) -> date:
    """Soma `days` dias úteis (pula sábado/domingo) a `start`."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _parse_date(value: Any) -> Optional[date]:
    """Aceita 'YYYY-MM-DD', 'DD/MM/YYYY' ou date/datetime; retorna date ou None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _norm_respondeu(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in ("SIM", "S", "TRUE", "YES", "1"):
        return "SIM"
    if text in ("NÃO", "NAO", "N", "FALSE", "NO", "0"):
        return "NÃO"
    return None


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_items(raw_items: List[Dict[str, Any]], today: Optional[date] = None) -> List[Dict[str, Any]]:
    """Normaliza a saída da IA para o formato canônico dos itens de CRM.

    - Descarta itens sem `lead` ou `empresa`.
    - Datas inválidas viram None (e defaults são recalculados).
    - Follow-ups ausentes seguem o padrão da planilha em dias úteis.
    """
    today = today or date.today()
    normalized: List[Dict[str, Any]] = []
    for raw in raw_items or []:
        lead = _clean(raw.get("lead"))
        empresa = _clean(raw.get("empresa"))
        if not lead or not empresa:
            continue

        prospeccao = _parse_date(raw.get("prospeccao")) or today
        pitch_enviado = bool(raw.get("pitch_enviado"))
        pitch_data = _parse_date(raw.get("pitch_data"))
        if pitch_enviado and pitch_data is None:
            pitch_data = prospeccao

        follow_ups = [
            _parse_date(raw.get("follow_up_1")),
            _parse_date(raw.get("follow_up_2")),
            _parse_date(raw.get("follow_up_3")),
        ]
        if pitch_data is not None:
            defaults = (
                add_business_days(pitch_data, 4),
                add_business_days(pitch_data, 7),
                add_business_days(pitch_data, 10),
            )
            follow_ups = [fu or default for fu, default in zip(follow_ups, defaults)]

        normalized.append({
            "lead": lead,
            "empresa": empresa,
            "prospeccao": prospeccao,
            "pitch_enviado": pitch_enviado,
            "pitch_data": pitch_data,
            "follow_up_1": follow_ups[0],
            "follow_up_2": follow_ups[1],
            "follow_up_3": follow_ups[2],
            "respondeu": _norm_respondeu(raw.get("respondeu")),
            "cargo": _clean(raw.get("cargo")),
            "observacoes": _clean(raw.get("observacoes")),
        })
    return normalized


async def extract_leads(raw_text: str) -> List[Dict[str, Any]]:
    """Chama o Groq e retorna os itens normalizados (sem inserir nada)."""
    result = await groq_json_chat(
        api_key=workers_settings.GROQ_API_KEY,
        model=workers_settings.GROQ_MODEL_CLASSIFY,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=str(raw_text or "")[:12000],
        url=GROQ_URL,
        max_tokens=4096,
        temperature=0.0,
        reasoning_effort="none",
    )
    if not result:
        logger.warning("crm extract: Groq não retornou JSON utilizável")
        return []
    raw_items = result.get("leads")
    if isinstance(raw_items, dict):
        raw_items = list(raw_items.values())
    if not isinstance(raw_items, list):
        raw_items = []
    return normalize_items(raw_items)


def dedupe_key(lead: str, empresa: str) -> tuple[str, str]:
    """Chave de dedupe (pessoa, empresa) — minúsculas, sem espaços extras."""
    return (lead.strip().lower(), empresa.strip().lower())


def _as_dt(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def insert_items(db, organization, items: List[Dict[str, Any]], consultant_user_id: Optional[str], campaign_id: Optional[str]) -> Dict[str, Any]:
    """Insere os itens no modelo existente (Lead + Contact + FollowUp).

    Dedupe por (pessoa primária + empresa) dentro da organização. Follow-ups
    são agendados como registros `FollowUp` (cadência nativa do sistema):
    pitch → OPENING (SENT), datas extraídas/default → FOLLOWUP_1/2 e CLOSING.
    """
    from sqlalchemy import func

    from src.db.models import (
        Campaign, Contact, FollowUp, FollowUpStatus, FollowUpStep, Lead, LeadStatus,
    )

    inserted = 0
    duplicates = 0
    errors: List[str] = []

    campaign = None
    if campaign_id:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id, Campaign.organization_id == organization.id)
            .first()
        )
        if campaign is None:
            raise ValueError("Campanha não encontrada nesta organização")

    for idx, item in enumerate(items, start=1):
        try:
            lead_name = item["lead"]
            empresa = item["empresa"]
            existing = (
                db.query(Contact)
                .join(Lead, Contact.lead_id == Lead.id)
                .filter(
                    Lead.organization_id == organization.id,
                    func.lower(Contact.name) == lead_name.strip().lower(),
                    func.lower(Lead.company_name) == empresa.strip().lower(),
                )
                .first()
            )
            if existing is not None:
                duplicates += 1
                continue

            pitch_date: Optional[date] = item.get("pitch_data")
            respondeu = item.get("respondeu")
            if respondeu == "SIM":
                status = LeadStatus.RESPONDIDO
            elif item.get("pitch_enviado"):
                status = LeadStatus.CONTATADO
            else:
                status = LeadStatus.NOVO

            now = datetime.now(timezone.utc)
            lead = Lead(
                organization_id=organization.id,
                company_name=empresa,
                name=empresa,
                city="Não informado",
                status=status,
                notes=item.get("observacoes"),
                campaign_id=campaign.id if campaign else None,
                assigned_to_id=consultant_user_id,
                assigned_at=now,
                last_contacted_at=_as_dt(pitch_date),
                next_action_at=_as_dt(item.get("follow_up_1")),
            )
            db.add(lead)
            db.flush()

            db.add(Contact(
                lead_id=lead.id,
                name=lead_name,
                role_label=item.get("cargo"),
                is_primary=True,
                confidence=50,
            ))

            if pitch_date is not None:
                steps = [
                    (FollowUpStep.OPENING, pitch_date, FollowUpStatus.SENT),
                    (FollowUpStep.FOLLOWUP_1, item.get("follow_up_1"), FollowUpStatus.PENDING),
                    (FollowUpStep.FOLLOWUP_2, item.get("follow_up_2"), FollowUpStatus.PENDING),
                    (FollowUpStep.CLOSING, item.get("follow_up_3"), FollowUpStatus.PENDING),
                ]
                for step, when, step_status in steps:
                    if when is None:
                        continue
                    db.add(FollowUp(
                        lead_id=lead.id,
                        step=step,
                        scheduled_at=_as_dt(when),
                        status=step_status,
                        sent_at=_as_dt(pitch_date) if step_status == FollowUpStatus.SENT else None,
                    ))

            inserted += 1
            # Commit por item: falha em um registro não desfaz os anteriores.
            db.commit()
        except Exception as exc:  # item específico não derruba o lote
            logger.warning("crm insert: falha no item %d: %s", idx, exc)
            errors.append(f"Item {idx} ({item.get('lead', '?')}): {exc}")
            db.rollback()

    return {"inserted": inserted, "duplicates": duplicates, "errors": errors}
