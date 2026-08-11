"""E2E do ciclo completo de outreach (roadmap-vendas 4.15).

Roda contra um Postgres REAL (`E2E_DATABASE_URL`). Cria uma org/campanha/lead
temporários e exercita o fluxo ponta a ponta com as integrações externas
(LLM/SMTP) stubadas:

  coleta → NOVO → enriquecimento/scoring → QUALIFICADO → mensagens → cadência
  → envio da etapa → resposta inbound → RESPONDIDO

Como rodar (exige banco real):
    E2E_DATABASE_URL="postgresql://postgres:senha@127.0.0.1:5432/agente_prospeccao" \
      python -m pytest tests/e2e_outreach_cycle.py -q -s

Em CI (sem banco) o teste é pulado automaticamente.
"""
import asyncio
import json
import os
import uuid

import pytest

E2E_DB_URL = os.environ.get("E2E_DATABASE_URL")
pytestmark = pytest.mark.e2e

if not E2E_DB_URL:
    pytest.skip("E2E_DATABASE_URL não definido — pulando teste de ciclo completo", allow_module_level=True)

# Aponta os Settings (workers + api) para o banco real ANTES de qualquer import.
os.environ["DATABASE_URL"] = E2E_DB_URL
os.environ["ENVIRONMENT"] = "test"

from database.session import SessionLocal  # noqa: E402
from database.models import (  # noqa: E402
    Campaign, Contact, Enrichment, FollowUp, FollowUpStatus, FollowUpStep,
    Lead, LeadActivity, LeadStatus, Message, Organization, User,
)
from services.enrichment_orchestrator import process_single_lead  # noqa: E402
from services.outreach_service import OutreachService  # noqa: E402
from services.scoring_service import AIScoringService  # noqa: E402
from services.technical_enrichment_service import TechnicalEnrichmentService  # noqa: E402

from src.services.cadence_service import schedule_cadence, send_step  # noqa: E402
from src.services.email_service import EmailSendResult  # noqa: E402
from src.services.inbound_email_service import process_inbound_email  # noqa: E402


def _canned_score_response() -> dict:
    return {
        "qualification_score": 82,
        "primary_need": "Site desatualizado limita conversão",
        "qualification_reason": "Sem presença digital competitiva no segmento.",
        "priority": "HOT",
        "priority_reasoning": "Cliente-alvo da campanha.",
        "executive_summary": "Empresa sem site moderno.",
        "pitch_angle": "Site moderno que converte visitantes em pedidos",
        "suggested_subject": "Sua empresa pode vender mais no digital",
        "score_factors": [
            {"factor": "presença digital", "score": 40, "reason": "sem website próprio"},
        ],
        "evidence": [
            {"title": "Sem site próprio", "description": "Lead sem website cadastrado."},
        ],
    }


def _canned_sequence() -> dict:
    body = (
        "Olá! Notei que sua empresa ainda não tem uma presença digital forte. "
        "Posso te enviar alguns exemplos de sites que transformaram visitantes "
        "em clientes? Basta responder.\n-\nResponda STOP para não receber mais mensagens."
    )
    return {
        "subject": "Sua empresa pode vender mais no digital",
        "body_opening": body,
        "followup_1": "Seguindo meu e-mail anterior. Quer que eu te mande 3 exemplos?",
        "followup_2": "Fica o convite: uma análise gratuita de presença digital.",
        "closing": "Vou encerrar por aqui. Se um dia precisar, é só responder.",
        "whatsapp_short": "Posso te ajudar com sua presença digital?",
        "rationale": "E2E test",
    }


class _FakeOutboundResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [
                {"message": {"content": json.dumps(_canned_sequence(), ensure_ascii=False)}}
            ]
        }


class _FakeHttpClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None):
        return _FakeOutboundResponse()


@pytest.fixture()
def fake_providers(monkeypatch):
    """Stub das fronteiras externas: LLM (scoring) e SMTP (envio)."""

    async def fake_groq_json_chat(*args, **kwargs):
        return _canned_score_response()

    monkeypatch.setattr("services.provider_client.groq_json_chat", fake_groq_json_chat)
    monkeypatch.setattr(OutreachService, "_create_client", lambda self: _FakeHttpClient())

    def fake_send_email(*args, **kwargs):
        return EmailSendResult(sent=True, message_id=f"<e2e-{uuid.uuid4().hex}@test>")

    monkeypatch.setattr("src.services.email_service.send_email", fake_send_email)
    return None


def _cleanup(db, org: Organization, user: User) -> None:
    org_id = org.id
    lead_ids = [r[0] for r in db.query(Lead.id).filter(Lead.organization_id == org_id).all()]
    for model in (LeadActivity, FollowUp, Message, Contact, Enrichment):
        if lead_ids:
            db.query(model).filter(model.lead_id.in_(lead_ids)).delete(synchronize_session=False)
    db.query(Lead).filter(Lead.organization_id == org_id).delete(synchronize_session=False)
    db.query(Campaign).filter(Campaign.organization_id == org_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
    db.commit()


async def _run_cycle() -> None:
    db = SessionLocal()
    org = Organization(name=f"E2E {uuid.uuid4().hex[:8]}", slug=f"e2e-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    user = User(
        email=f"e2e-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="not-a-real-hash",
        name="Usuário E2E",
    )
    db.add(user)
    db.flush()
    campaign = Campaign(
        name="E2E Sites",
        organization_id=org.id,
        user_id=user.id,
        target_service="Criação de Sites",
    )
    db.add(campaign)
    db.flush()

    lead = Lead(
        organization_id=org.id,
        campaign_id=campaign.id,
        company_name="E2E Comércio de Alimentos Ltda",
        city="Araraquara",
        state="SP",
        email="decisor@e2e-teste.local",
        status=LeadStatus.NOVO,
    )
    db.add(lead)
    db.commit()

    try:
        # 1) Enriquecimento + scoring (lead sem site → path business; LLM stub).
        enrichment, scoring_data = await process_single_lead(
            lead,
            enrichment_service=TechnicalEnrichmentService(),
            scoring_service=AIScoringService(),
            db=db,
            campaign_target_service="Criação de Sites",
        )
        assert enrichment is None  # sem website → sem relatório técnico
        assert scoring_data and scoring_data.get("qualification_score", 0) >= 60

        lead.status = LeadStatus.QUALIFICADO
        db.commit()

        # 2) Geração de mensagens + cadência (dia 0/3/7/14).
        lead_dict = {
            "company_name": lead.company_name,
            "category": "Comércio",
            "city": lead.city,
            "state": lead.state,
            "website": None,
            "primary_need": scoring_data.get("primary_need"),
            "pitch_angle": scoring_data.get("pitch_angle"),
            "qualification_reason": scoring_data.get("qualification_reason"),
            "evidence": scoring_data.get("evidence", []),
        }
        out = await OutreachService(api_key="test").generate_sequence(
            lead_dict, "Criação de Sites", ""
        )
        assert out and out.get("body_opening")

        follow_ups = schedule_cadence(db, lead, out, organization=org)
        assert len(follow_ups) == 4
        assert all(fu.status == FollowUpStatus.PENDING for fu in follow_ups)
        db.commit()

        # 3) Envio da etapa de abertura (SMTP stubado).
        opening = next(fu for fu in follow_ups if fu.step == FollowUpStep.OPENING)
        sent = send_step(db, opening, user_id=None)
        db.refresh(opening)
        assert sent is True
        assert opening.status == FollowUpStatus.SENT
        assert opening.message_id is not None

        # 4) Resposta do decisor (inbound) → RESPONDIDO e cadência cancelada.
        result = process_inbound_email(
            db,
            from_email="decisor@e2e-teste.local",
            subject="Re: proposta",
            body="Podemos marcar uma reunião na semana que vem?",
        )
        db.refresh(lead)
        assert result["matched"] is True
        assert result["stop_requested"] is False
        assert lead.status == LeadStatus.RESPONDIDO

        remaining = db.query(FollowUp).filter(FollowUp.lead_id == lead.id).all()
        statuses = [fu.status for fu in remaining]
        assert FollowUpStatus.SENT in statuses  # etapa já enviada permanece
        assert all(
            fu.status in (FollowUpStatus.SENT, FollowUpStatus.CANCELLED) for fu in remaining
        )
    finally:
        _cleanup(db, org, user)
        db.close()


def test_outreach_full_cycle(fake_providers):
    """Ciclo completo: NOVO → QUALIFICADO → cadência → envio → RESPONDIDO."""
    asyncio.run(_run_cycle())
