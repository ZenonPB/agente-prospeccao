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
    assert verify_migrations.migration_head() == "d2e3f4a5b6c7"


def test_registry_tem_schema_e_integridade_obrigatorios():
    verify_migrations = _module()
    assert {"registry_snapshots", "registry_import_files", "registry_companies",
            "registry_company_cnaes", "registry_cnaes"} <= verify_migrations.REQUIRED_TABLES
    assert verify_migrations.REQUIRED_UNIQUES["registry_snapshots"] == {"uq_registry_snapshots_source_month"}
    assert verify_migrations.REQUIRED_UNIQUES["registry_import_files"] == {"uq_registry_files_snapshot_name"}
    assert {"ix_registry_companies_basico", "ix_registry_companies_cnae_uf",
            "ix_registry_companies_geo", "ix_registry_cnaes_cnae"} <= verify_migrations.REQUIRED_INDEXES
    assert "content_hash" in verify_migrations.REQUIRED_COLUMNS["registry_companies"]
    assert "organization_id" not in verify_migrations.REQUIRED_COLUMNS.get("registry_companies", set())


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


def test_feedback_utilidade_tem_tabela_motivo_e_idempotencia():
    verify_migrations = _module()
    assert "lead_usefulness_feedbacks" in verify_migrations.REQUIRED_TABLES
    assert {"useful", "reason", "detail", "campaign_id", "created_at"} == verify_migrations.REQUIRED_COLUMNS["lead_usefulness_feedbacks"]
    assert verify_migrations.REQUIRED_UNIQUES["lead_usefulness_feedbacks"] == {"uq_lead_usefulness_lead_user"}
    assert {"ix_lead_usefulness_org_created", "ix_lead_usefulness_lead_id"} <= verify_migrations.REQUIRED_INDEXES


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
        def get_indexes(self, table):
            return [
                {
                    "name": name,
                    "unique": table == "conversions" and name == "uq_conversions_lead_offer",
                }
                for name in verify_migrations.REQUIRED_INDEXES
            ]
        def get_check_constraints(self, table):
            return [
                {"name": name}
                for name in verify_migrations.REQUIRED_CHECK_CONSTRAINTS.get(table, set())
            ]
        def get_foreign_keys(self, _table): return []
        def get_unique_constraints(self, _table): return []

    monkeypatch.setattr(verify_migrations, "create_engine", lambda _url: _Engine())
    monkeypatch.setattr(verify_migrations.MigrationContext, "configure", lambda _connection: _Context())
    monkeypatch.setattr(verify_migrations, "inspect", lambda _connection: _Inspector())
    with pytest.raises(RuntimeError, match="FKs ausentes"):
        verify_migrations.verify_database("postgresql://test")


def test_operacoes_bulk_tem_schema_e_idempotencia_por_workspace():
    verify_migrations = _module()
    assert "commercial_bulk_operations" in verify_migrations.REQUIRED_TABLES
    assert verify_migrations.REQUIRED_COLUMNS["commercial_bulk_operations"] == {
        "organization_id", "actor_id", "idempotency_key", "operation",
        "payload_hash", "status", "result", "created_at", "completed_at",
    }
    assert verify_migrations.REQUIRED_UNIQUES["commercial_bulk_operations"] == {
        "uq_commercial_bulk_operations_org_idempotency",
    }
    assert "ix_commercial_bulk_operations_org_created" in verify_migrations.REQUIRED_INDEXES


def _updated_at_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "workers"
        / "migrations"
        / "versions"
        / "f2b3c4d5e6f7_lead_updated_at_default.py"
    )
    spec = importlib.util.spec_from_file_location("lead_updated_at_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_lead_updated_at_tem_default_e_onupdate_no_modelo():
    from database.models import Lead

    column = Lead.__table__.c.updated_at
    assert column.server_default is not None
    assert "now()" in str(column.server_default.arg).lower()
    assert column.onupdate is not None


def test_migration_de_updated_at_tem_backfill_e_default_aditivo(monkeypatch):
    migration = _updated_at_migration()
    executed = []
    altered = []

    class FakeOperations:
        def execute(self, statement):
            executed.append(str(statement))

        def alter_column(self, *args, **kwargs):
            altered.append((args, kwargs))

    monkeypatch.setattr(migration, "op", FakeOperations())
    migration.upgrade()

    assert migration.revision == "f2b3c4d5e6f7"
    assert migration.down_revision == "f1b2c3d4e5f6"
    assert any("COALESCE(created_at, now())" in statement for statement in executed)
    assert altered[0][0] == ("leads", "updated_at")
    assert str(altered[0][1]["server_default"]) == "now()"


def _schema_gate_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "workers"
        / "migrations"
        / "versions"
        / "f8a9b0c1d2e3_schema_integrity_gates.py"
    )
    spec = importlib.util.spec_from_file_location("schema_integrity_gates", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_schema_gate_exige_jobs_conversion_lost_reason_e_person():
    verify_migrations = _module()
    assert verify_migrations.REQUIRED_NOT_NULL_COLUMNS == {"jobs": {"organization_id"}}
    assert verify_migrations.REQUIRED_CHECK_CONSTRAINTS == {
        "jobs": {"ck_jobs_organization_required"},
        "leads": {"ck_leads_lost_reason_required"},
        "registry_snapshots": {"ck_registry_snapshots_status"},
        "registry_import_files": {"ck_registry_files_status", "ck_registry_files_kind"},
    }
    assert verify_migrations.REQUIRED_UNIQUE_INDEXES == {
        "conversions": {"uq_conversions_lead_offer"},
    }
    assert {
        "ix_persons_org_document_cpf",
        "ix_persons_org_email",
    } <= verify_migrations.REQUIRED_INDEXES

    from database.models import Job, Lead, Person

    assert Job.__table__.c.organization_id.nullable is False
    assert any(
        constraint.name == "ck_leads_lost_reason_required"
        for constraint in Lead.__table__.constraints
    )
    assert {
        index.name for index in Person.__table__.indexes
    } >= {"ix_persons_org_document_cpf", "ix_persons_org_email"}


def test_schema_gate_faz_backfill_e_rejeicao_antes_do_not_null(monkeypatch):
    migration = _schema_gate_migration()
    executed: list[str] = []

    class FakeOperations:
        def execute(self, statement):
            executed.append(str(statement))

    monkeypatch.setattr(migration, "op", FakeOperations())
    migration.upgrade()

    statements = [statement.lower() for statement in executed]
    backfill = next(index for index, statement in enumerate(statements) if "update jobs" in statement)
    orphan_check = next(index for index, statement in enumerate(statements) if "jobs órfãos" in statement)
    set_not_null = next(index for index, statement in enumerate(statements) if "set not null" in statement)
    assert backfill < orphan_check < set_not_null
    assert any("validate constraint ck_jobs_organization_required" in statement for statement in statements)
    assert any("validate constraint ck_leads_lost_reason_required" in statement for statement in statements)
    assert any("ix_persons_org_document_cpf" in statement for statement in statements)
    assert any("ix_persons_org_email" in statement for statement in statements)
