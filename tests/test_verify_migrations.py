"""Testes do verificador seguro de migrations."""
import importlib.util
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_migrations.py"
    spec = importlib.util.spec_from_file_location("verify_migrations_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_head_unico_e_conhecido():
    verify_migrations = _module()

    assert verify_migrations.migration_head() == "a4b5c6d7e8f9"


def test_person_canonica_tem_colunas_obrigatorias():
    verify_migrations = _module()

    assert verify_migrations.REQUIRED_COLUMNS["persons"] == {
        "identity_confidence",
        "contact_confidence",
        "source_reliability",
        "verification_status",
        "last_verified_at",
        "routability_type",
        "routable",
        "routability_reason",
    }


def test_versions_de_follow_up_tem_unicidade_por_etapa():
    """Uma etapa não pode ter duas versões com o mesmo número."""
    verify_migrations = _module()

    assert verify_migrations.REQUIRED_UNIQUES["follow_up_versions"] == {
        "uq_follow_up_versions_follow_up_version",
    }


def test_snapshot_de_resolucao_tem_schema_e_integridade_obrigatorios():
    verify_migrations = _module()

    assert "decision_resolution_snapshots" in verify_migrations.REQUIRED_TABLES
    assert verify_migrations.REQUIRED_COLUMNS["decision_resolution_snapshots"] == {
        "status", "snapshot_hash", "payload", "reason", "created_at",
    }
    assert verify_migrations.REQUIRED_UNIQUES["decision_resolution_snapshots"] == {
        "uq_decision_resolution_snapshot_hash",
    }


def test_controlled_learning_tem_schema_e_integridade_obrigatorios():
    verify_migrations = _module()

    assert "controlled_learning_proposals" in verify_migrations.REQUIRED_TABLES
    assert verify_migrations.REQUIRED_COLUMNS["controlled_learning_proposals"] == {
        "proposal_version", "status", "evidence_snapshot", "published_at", "created_at",
    }
    assert verify_migrations.REQUIRED_UNIQUES["controlled_learning_proposals"] == {
        "uq_controlled_learning_org_comparison",
        "uq_controlled_learning_org_offer_version",
    }


def test_verify_database_rejeita_banco_fora_do_head(monkeypatch):
    verify_migrations = _module()

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class _Engine:
        def connect(self):
            return _Connection()

        def dispose(self):
            pass

    class _Context:
        def get_current_revision(self):
            return "old-revision"

    monkeypatch.setattr(verify_migrations, "create_engine", lambda _url: _Engine())
    monkeypatch.setattr(
        verify_migrations.MigrationContext,
        "configure",
        lambda _connection: _Context(),
    )

    with pytest.raises(RuntimeError, match="Banco em 'old-revision'"):
        verify_migrations.verify_database("postgresql://test")


def test_verify_database_rejeita_fk_essencial_ausente(monkeypatch):
    verify_migrations = _module()

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class _Engine:
        def connect(self):
            return _Connection()

        def dispose(self):
            pass

    class _Context:
        def get_current_revision(self):
            return verify_migrations.migration_head()

    class _Inspector:
        def get_table_names(self):
            return verify_migrations.REQUIRED_TABLES

        def get_indexes(self, _table):
            return [{"name": name} for name in verify_migrations.REQUIRED_INDEXES]

        def get_foreign_keys(self, _table):
            return []

        def get_unique_constraints(self, _table):
            return []

    monkeypatch.setattr(verify_migrations, "create_engine", lambda _url: _Engine())
    monkeypatch.setattr(
        verify_migrations.MigrationContext,
        "configure",
        lambda _connection: _Context(),
    )
    monkeypatch.setattr(verify_migrations, "inspect", lambda _connection: _Inspector())

    with pytest.raises(RuntimeError, match="FKs ausentes"):
        verify_migrations.verify_database("postgresql://test")