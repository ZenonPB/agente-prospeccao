"""Regressões da atribuição determinística de respostas inbound."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

from src.db.models import FollowUp, FollowUpStatus, Lead
from src.services.inbound_email_service import _resolve_lead_for_sender


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)

    def outerjoin(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        self.rows.sort(key=lambda row: getattr(row, "sent_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        return self

    def all(self):
        return list(self.rows)


class _Session:
    def __init__(self, leads, followups):
        self.leads = leads
        self.followups = followups

    def query(self, model):
        if model is Lead:
            return _Query(self.leads)
        if model is FollowUp:
            return _Query(self.followups)
        raise AssertionError(f"consulta inesperada: {model}")


def _lead(org_id):
    return SimpleNamespace(id=uuid.uuid4(), organization_id=org_id, email="shared@example.com")


def _sent(lead, sent_at):
    return SimpleNamespace(
        id=uuid.uuid4(),
        lead_id=lead.id,
        status=FollowUpStatus.SENT,
        recipient="shared@example.com",
        sent_at=sent_at,
    )


def test_inbound_ambiguo_escolhe_lead_com_envio_mais_recente():
    org_id = uuid.uuid4()
    older = _lead(org_id)
    newer = _lead(org_id)
    now = datetime.now(timezone.utc)
    session = _Session(
        [older, newer],
        [_sent(older, now - timedelta(minutes=5)), _sent(newer, now)],
    )

    resolved = _resolve_lead_for_sender(session, org_id, "shared@example.com")

    assert resolved is newer


def test_inbound_ambiguo_falha_fechado_quando_maximo_empata_entre_leads():
    org_id = uuid.uuid4()
    lead_a = _lead(org_id)
    lead_b = _lead(org_id)
    now = datetime.now(timezone.utc)
    # Duas linhas do mesmo lead no máximo não podem esconder um terceiro envio
    # empatado de outro lead (regressão do antigo limit(2)).
    session = _Session(
        [lead_a, lead_b],
        [_sent(lead_a, now), _sent(lead_a, now), _sent(lead_b, now)],
    )

    resolved = _resolve_lead_for_sender(session, org_id, "shared@example.com")

    assert resolved is None
