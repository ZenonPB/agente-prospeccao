"""Contrato das métricas históricas de execução de providers."""


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