import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKERS = os.path.join(ROOT, "services", "workers", "src")
API = os.path.join(ROOT, "services", "api")
for path in (WORKERS, API):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.prospecting.default_profiles import get_default_registry  # noqa: E402
from services.prospecting.effective_offer_registry import build_effective_registry  # noqa: E402
from src.services.controlled_learning_service import validate_profile_publication  # noqa: E402


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows


class _Db:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return _Query(self.rows)


def _profile(version: str = "2.0"):
    base = get_default_registry().get("landing_page")
    assert base is not None
    payload = base.to_dict()
    payload["version"] = version
    payload["prescoring"] = {**payload["prescoring"], "threshold": 61}
    return payload


def test_publication_requires_exact_approved_version():
    with pytest.raises(ValueError, match="exatamente a versão aprovada"):
        validate_profile_publication(
            _profile("2.0"),
            offer_key="landing_page",
            approved_version="3.0",
            current_version="1.0",
        )


def test_publication_requires_new_version_for_reliable_rollback():
    with pytest.raises(ValueError, match="nova versão"):
        validate_profile_publication(
            _profile("1.0"),
            offer_key="landing_page",
            approved_version="1.0",
            current_version="1.0",
        )


def test_publication_rejects_wrong_offer_key():
    payload = _profile("2.0")
    payload["key"] = "mechanical_project"
    with pytest.raises(ValueError, match="não pertence"):
        validate_profile_publication(
            payload,
            offer_key="landing_page",
            approved_version="2.0",
            current_version="1.0",
        )


def test_effective_registry_overlays_only_active_workspace_profile():
    payload = _profile("2.0")
    row = SimpleNamespace(profile_snapshot=payload)
    registry = build_effective_registry(_Db([row]), "org-1")

    landing = registry.get("landing_page")
    mechanical = registry.get("mechanical_project")
    canonical_mechanical = get_default_registry().get("mechanical_project")
    assert landing is not None and landing.version == "2.0"
    assert landing.prescoring["threshold"] == 61
    assert mechanical is not None and canonical_mechanical is not None
    assert mechanical.version == canonical_mechanical.version


def test_effective_registry_ignores_invalid_persisted_snapshot():
    invalid = _profile("2.0")
    invalid["channels"] = {"priority": ["carrier_pigeon"]}
    registry = build_effective_registry(_Db([SimpleNamespace(profile_snapshot=invalid)]), "org-1")

    landing = registry.get("landing_page")
    canonical_landing = get_default_registry().get("landing_page")
    assert landing is not None and canonical_landing is not None
    assert landing.version == canonical_landing.version
