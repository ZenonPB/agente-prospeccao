"""Contratos de validação da aprovação comercial."""

from types import SimpleNamespace
from uuid import uuid4

import pytest


def test_approval_request_strips_and_rejects_blank_evidence():
    from src.routes.intelligence import ComparisonApprovalRequest

    request = ComparisonApprovalRequest(approved_version=" 2.0 ", evidence="  evidência válida  ")
    assert request.approved_version == "2.0"
    assert request.evidence == "evidência válida"

    with pytest.raises(ValueError, match="não pode ser vazio"):
        ComparisonApprovalRequest(approved_version="2.0", evidence="   ")


def test_comparison_approval_is_idempotent_for_same_version(monkeypatch):
    from src.services.commercial_comparison_service import CommercialComparisonService

    comparison = SimpleNamespace(
        id=uuid4(), organization_id=uuid4(), version_a="1.0", version_b="2.0",
        result={"verdict": "v2", "recommendation": "usar 2.0"},
        approved_version="2.0", approval_evidence="evidência original",
    )
    actor = SimpleNamespace(id=uuid4())

    class _ScalarResult:
        def first(self):
            return comparison

    class _DB:
        def scalars(self, _statement):
            return _ScalarResult()

    service = CommercialComparisonService()
    monkeypatch.setattr(
        "src.services.commercial_comparison_service.log_org_event",
        lambda *args, **kwargs: pytest.fail("não deve auditar aprovação repetida"),
    )

    assert service.approve(
        _DB(), comparison.organization_id, comparison.id, "2.0", actor, "  "
    ) is comparison
    assert comparison.approval_evidence == "evidência original"