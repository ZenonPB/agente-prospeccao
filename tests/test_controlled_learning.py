"""Propostas de learning comercial após aprovação humana de A/B."""

from types import SimpleNamespace
from uuid import uuid4

import pytest


def _comparison(**overrides):
    result = {
        "verdict": "v2",
        "recommendation": "Recomendado: versão 2.0",
        "delta": 12.5,
        "v1_conversion": 10.0,
        "v2_conversion": 22.5,
        "v1_total": 40,
        "v2_total": 40,
        "is_conclusive": True,
        "is_statistically_significant": True,
        "v1": {"version": "1.0", "confidence_interval": {"low": 5.0, "high": 17.0}},
        "v2": {"version": "2.0", "confidence_interval": {"low": 16.0, "high": 30.0}},
    }
    values = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "offer_key": "trophies",
        "version_a": "1.0",
        "version_b": "2.0",
        "result": result,
        "approved_version": "2.0",
        "approved_by_id": uuid4(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_proposal_captures_approved_comparison_without_auto_publish():
    from src.services.controlled_learning_service import build_learning_proposal

    comparison = _comparison()
    proposal = build_learning_proposal(comparison)

    assert proposal["status"] == "PROPOSED"
    assert proposal["offer_key"] == "trophies"
    assert proposal["approved_version"] == "2.0"
    assert proposal["source_comparison_id"] == str(comparison.id)
    assert proposal["evidence_snapshot"]["delta"] == 12.5
    assert proposal["requires_manual_publication"] is True


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"approved_version": None}, "comparação ainda não foi aprovada"),
        ({"result": {"verdict": "inconclusivo", "recommendation": None}}, "recomendação conclusiva"),
        ({"approved_version": "3.0"}, "versão aprovada não pertence"),
    ],
)
def test_build_proposal_rejects_unsafe_comparison(overrides, message):
    from src.services.controlled_learning_service import build_learning_proposal

    with pytest.raises(ValueError, match=message):
        build_learning_proposal(_comparison(**overrides))


def test_build_proposal_preserves_only_audit_snapshot_fields():
    from src.services.controlled_learning_service import build_learning_proposal

    comparison = _comparison(result={
        "verdict": "v2",
        "recommendation": "Recomendado",
        "delta": 8,
        "v1": {"version": "1.0", "confidence_interval": {"low": 1, "high": 2}},
        "v2": {"version": "2.0", "confidence_interval": {"low": 3, "high": 4}},
        "secret": "não persistir",
    })

    proposal = build_learning_proposal(comparison)

    assert set(proposal["evidence_snapshot"]) == {
        "verdict", "recommendation", "delta", "v1", "v2",
    }


def test_build_proposal_rejects_blank_recommendation_and_missing_identity():
    from src.services.controlled_learning_service import build_learning_proposal

    with pytest.raises(ValueError, match="recomendação conclusiva"):
        build_learning_proposal(_comparison(result={"verdict": "v2", "recommendation": "  "}))

    with pytest.raises(ValueError, match="identidade ou oferta"):
        build_learning_proposal(_comparison(id=None))