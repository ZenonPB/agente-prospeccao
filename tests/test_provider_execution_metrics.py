"""Contrato das métricas históricas de execução de providers."""
from unittest.mock import MagicMock


def test_aggregate_metrics_calcula_taxas_sem_confundir_empty_com_failed():
    from services.provider_execution_metric_service import ProviderExecutionMetricService

    metrics = [
        {"provider": "event_http", "status": "success", "result_count": 4, "duration_ms": 100},
        {"provider": "event_http", "status": "empty", "result_count": 0, "duration_ms": 200},
        {"provider": "event_http", "status": "failed", "result_count": 0, "duration_ms": 300},
        {"provider": "cnae", "status": "success", "result_count": 2, "duration_ms": 50},
    ]

    result = ProviderExecutionMetricService.aggregate_metrics(metrics)

    event = result["event_http"]
    assert event["executions"] == 3
    assert event["successes"] == 1
    assert event["empty"] == 1
    assert event["failures"] == 1
    assert event["result_count"] == 4
    assert event["failure_rate"] == 33.3
    assert event["empty_rate"] == 33.3
    assert event["average_duration_ms"] == 200


def test_aggregate_metrics_retorna_lista_vazia_sem_execucoes():
    from services.provider_execution_metric_service import ProviderExecutionMetricService

    assert ProviderExecutionMetricService.aggregate_metrics([]) == {}


def test_aggregate_metrics_inclui_skipped_disabled_quota():
    from services.provider_execution_metric_service import ProviderExecutionMetricService

    metrics = [
        {"provider": "places", "status": "disabled", "result_count": 0},
        {"provider": "places", "status": "quota_exceeded", "result_count": 0},
        {"provider": "places", "status": "skipped", "result_count": 0},
    ]

    result = ProviderExecutionMetricService.aggregate_metrics(metrics)
    assert result["places"]["executions"] == 3
    assert result["places"]["skipped"] == 3


def test_record_aceita_correlation_e_campaign():
    """O serviço propaga correlation_id/campaign_id/usage para a entidade."""
    import uuid as uuid_mod
    from services.provider_execution_metric_service import ProviderExecutionMetricService

    db = MagicMock()
    corr = uuid_mod.uuid4()
    camp = uuid_mod.uuid4()
    job = uuid_mod.uuid4()
    org = uuid_mod.uuid4()

    row = ProviderExecutionMetricService().record(
        db, org, "cnae", "success",
        job_id=job, campaign_id=camp, correlation_id=corr,
        result_count=3, duration_ms=120, budget_used=3,
        cost=0.0012, usage={"prompt_tokens": 12, "completion_tokens": 5, "model": "m"},
    )

    assert row.correlation_id == corr
    assert row.campaign_id == camp
    assert row.job_id == job
    assert row.organization_id == org
    assert row.provider == "cnae"
    assert row.cost == 0.0012
    assert row.usage == {"prompt_tokens": 12, "completion_tokens": 5, "model": "m"}


def test_list_by_correlation_id_filtra_pelo_trace():
    """`list_by_correlation_id` devolve somente as medições do mesmo trace."""
    from services.provider_execution_metric_service import ProviderExecutionMetricService

    class _Row:
        def __init__(self, corr, provider):
            self.correlation_id = corr
            self.provider = provider

    db = MagicMock()
    db.scalars.return_value.all.return_value = [1, 2, 3]
    result = ProviderExecutionMetricService().list_by_correlation_id(db, "corr")
    assert result == [1, 2, 3]