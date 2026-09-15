"""Validações puras do Registry (sem banco): mês do snapshot e cursor."""
from __future__ import annotations

import pytest


def test_snapshot_month_invalido_e_rejeitado():
    from services.registry.importer import validate_snapshot_month

    assert validate_snapshot_month("2026-08") == "2026-08"
    for bad in ("2026-13", "2026-00", "26-08", "2026/08", "agosto", "", None):
        with pytest.raises(ValueError):
            validate_snapshot_month(bad)


def test_cursor_invalido_e_rejeitado():
    from services.registry.search import SearchFilters

    with pytest.raises(ValueError):
        SearchFilters(cursor="!!")
    with pytest.raises(ValueError):
        SearchFilters(cursor="123")
    assert SearchFilters(cursor="33000167000101").cursor == "33000167000101"
    assert SearchFilters(cursor=None).cursor is None
