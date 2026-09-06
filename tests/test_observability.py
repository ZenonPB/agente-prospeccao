"""Contratos públicos da observabilidade operacional."""
from datetime import datetime, timedelta, timezone


def test_log_job_event_correlaciona_job_org_e_duracao(caplog):
    from src.services.observability import log_job_event

    started_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    with caplog.at_level("INFO", logger="prospeccao.events"):
        log_job_event(
            "job_completed",
            job_id="job-1",
            organization_id="org-1",
            campaign_id="campaign-1",
            started_at=started_at,
        )

    message = caplog.records[-1].message
    assert "event=job_completed" in message
    assert "job_id=job-1" in message
    assert "organization_id=org-1" in message
    assert "campaign_id=campaign-1" in message
    assert "duration_ms=" in message


def test_log_event_redige_credenciais_em_campos_livres(caplog):
    from src.services.observability import log_event

    with caplog.at_level("INFO", logger="prospeccao.events"):
        log_event(
            "provider_failed",
            api_key="secret-value",
            payload={"access_token": "nested-secret", "provider": "test"},
        )

    message = caplog.records[-1].message
    assert "secret-value" not in message
    assert "nested-secret" not in message
    assert "REDACTED" in message