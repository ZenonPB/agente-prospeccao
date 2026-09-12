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
    assert verify_migrations.migration_head() == "c2d4e6f8a0b1"


def test_person_canonica_tem_colunas_obrigatorias():
    verify_migrations = _module()
    assert verify_migrations.REQUIRED_COLUMNS["persons"] == {
        "identity_confidence", "contact_confidence", "source_reliability",
        "verification_status", "last_verified_at", "routability_type",
        "routable", "routability_reason",
    }


def test_versions_de_follow_up_tem_unicidade_por_etapa():
    verify_migrations = _module()
    assert verify_migrations.REQUIRED_UNIQUES["follow_up_versions"] == {"uq_follow_up_versions_follow_up_version"}


def test_snapshot_de_resolucao_tem_schema_e_integridade_obrigatorios():
    verify_migrations = _module()
    assert "decision_resolution_snapshots" in verify_migrations.REQUIRED_TABLES
    assert verify_migrations.REQUIRED_COLUMNS["decision_resolution_snapshots"] == {"status", "snapshot_hash", "payload", "reason", "created_at"}
    assert verify_migrations.REQUIRED_UNIQUES["decision_resolution_snapshots"] == {"uq_decision_resolution_snapshot_hash"}


def test_controlled_learning_tem_schema_e_integridade_obrigatorios():
    verify_migrations = _module()
    assert "controlled_learning_proposals" in verify_migrations.REQUIRED_TABLES
    assert verify_migrations.REQUIRED_COLUMNS["controlled_learning_proposals"] == {"proposal_version", "status", "evidence_snapshot", "published_at", "created_at"}
    assert verify_migrations.REQUIRED_UNIQUES["controlled_learning_proposals"] == {"uq_controlled_learning_org_comparison", "uq_controlled_learning_org_offer_version"}


def test_publicacao_offer_profile_tem_versionamento_rollback_e_single_active():
    verify_migrations = _module()
    assert {"offer_profile_versions", "offer_profile_activations"} <= verify_migrations.REQUIRED_TABLES
    assert verify_migrations.REQUIRED_UNIQUES["offer_profile_versions"] == {"uq_offer_profile_versions_org_offer_version"}
    assert "uq_offer_profile_versions_one_active" in verify_migrations.REQUIRED_INDEXES
    assert {"offer_key", "version", "profile_snapshot", "is_active", "source_proposal_id", "activated_at", "deactivated_at"} == verify_migrations.REQUIRED_COLUMNS["offer_profile_versions"]


def test_crm_certification_tem_evidencia_persistente():
    verify_migrations = _module()
    assert "crm_certification_runs" in verify_migrations.REQUIRED_TABLES
    assert {"provider", "status", "checks", "adapter_version", "tested_by_id", "created_at"} == verify_migrations.REQUIRED_COLUMNS["crm_certification_runs"]


def test_engagement_tem_schema_e_integridade_obrigatorios():
    verify_migrations = _module()
    expected = {"sequence_templates", "sequence_enrollments", "sequence_executions", "commercial_tasks", "next_best_action_decisions", "workflow_definitions", "workflow_runs"}
    assert expected <= verify_migrations.REQUIRED_TABLES
    assert verify_migrations.REQUIRED_UNIQUES["sequence_executions"] == {"uq_sequence_executions_enrollment_step", "uq_sequence_executions_org_idempotency"}
    assert verify_migrations.REQUIRED_UNIQUES["workflow_runs"] == {"uq_workflow_runs_org_workflow_event"}
    assert {"action", "why", "confidence", "evidence", "deadline", "fingerprint"} == verify_migrations.REQUIRED_COLUMNS["next_best_action_decisions"]


def test_verify_database_rejeita_banco_fora_do_head(monkeypatch):
    verify_migrations = _module()

    class _Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
    class _Engine:
        def connect(self): return _Connection()
        def dispose(self): pass
    class _Context:
        def get_current_revision(self): return "old-revision"

    monkeypatch.setattr(verify_migrations, "create_engine", lambda _url: _Engine())
    monkeypatch.setattr(verify_migrations.MigrationContext, "configure", lambda _connection: _Context())
    with pytest.raises(RuntimeError, match="Banco em 'old-revision'"):
        verify_migrations.verify_database("postgresql://test")


def test_verify_database_rejeita_fk_essencial_ausente(monkeypatch):
    verify_migrations = _module()

    class _Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
    class _Engine:
        def connect(self): return _Connection()
        def dispose(self): pass
    class _Context:
        def get_current_revision(self): return verify_migrations.migration_head()
    class _Inspector:
        def get_table_names(self): return verify_migrations.REQUIRED_TABLES
        def get_indexes(self, _table): return [{"name": name} for name in verify_migrations.REQUIRED_INDEXES]
        def get_foreign_keys(self, _table): return []
        def get_unique_constraints(self, _table): return []

    monkeypatch.setattr(verify_migrations, "create_engine", lambda _url: _Engine())
    monkeypatch.setattr(verify_migrations.MigrationContext, "configure", lambda _connection: _Context())
    monkeypatch.setattr(verify_migrations, "inspect", lambda _connection: _Inspector())
    with pytest.raises(RuntimeError, match="FKs ausentes"):
        verify_migrations.verify_database("postgresql://test")
