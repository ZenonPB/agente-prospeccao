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

    assert verify_migrations.migration_head() == "aa6b7c8d9e0f"


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
            return "aa6b7c8d9e0f"

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