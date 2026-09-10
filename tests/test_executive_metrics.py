"""Contrato puro das métricas executivas de prospecção."""


def test_metricas_executivas_calculam_acionabilidade_e_precision_at_k():
    from src.services.analytics_service import build_executive_metrics

    result = build_executive_metrics(
        ranked_leads=[
            {"id": "lead-1", "converted": True},
            {"id": "lead-2", "converted": False},
            {"id": "lead-3", "converted": True},
        ],
        contacts=[
            {"routability_type": "DIRECT_CONTACT", "routable": True},
            {"routability_type": "INSTITUTIONAL", "routable": False},
            {"routability_type": "ROUTABLE_CONTACT", "routable": True},
        ],
        k=5,
    )

    assert result["status"] == "partial"
    assert result["sample_size"] == 3
    assert result["actionable_contact_rate"] == 2 / 3
    assert result["actionable_contacts"] == 2
    assert result["precision_at_k"] == 2 / 3
    assert result["precision_at_k_window"] == 3


def test_metricas_executivas_sem_dados_nao_confundem_vazio_com_zero_real():
    from src.services.analytics_service import build_executive_metrics

    result = build_executive_metrics([], [], k=10)

    assert result["status"] == "empty"
    assert result["sample_size"] == 0
    assert result["actionable_contact_rate"] is None
    assert result["precision_at_k"] is None


def test_snapshot_hash_e_politica_de_rescoring_sao_deterministicos():
    from services.prospecting.resolution_snapshot_service import snapshot_hash, should_rescore

    payload = {"status": "resolved", "people": [{"name": "Ana", "email": "ana@example.com"}]}
    digest = snapshot_hash(payload)

    assert digest == snapshot_hash({"people": payload["people"], "status": "resolved"})
    assert should_rescore(digest, digest) is False
    assert should_rescore(digest, digest, force=True) is True
    assert should_rescore(digest, "different") is True