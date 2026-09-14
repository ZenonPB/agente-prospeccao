"""Regressões encontradas na revisão final da consolidação de Vertentes."""
from __future__ import annotations

from types import SimpleNamespace


def test_template_snapshot_prioriza_override_da_organizacao():
    """Template local deve vencer o global de mesmo label no adapter legado."""
    from services.template_router import _templates_snapshot

    class FakeQuery:
        def __init__(self):
            self.order_args = ()

        def filter(self, *args):
            return self

        def order_by(self, *args):
            self.order_args = args
            return self

        def all(self):
            return []

    class FakeDB:
        def __init__(self):
            self.query_obj = FakeQuery()

        def query(self, *args):
            return self.query_obj

    db = FakeDB()
    _templates_snapshot(db, "org-a")

    assert len(db.query_obj.order_args) >= 2
    assert "organization_id IS NULL" in str(db.query_obj.order_args[0])
    assert "created_at" in str(db.query_obj.order_args[1])


def test_visao_simples_deriva_fluxo_do_offer_profile_real():
    from services.prospecting.default_profiles import get_base_registry
    from src.services.vertente_service import _analysis_flow

    landing = get_base_registry().get("landing_page")
    assert landing is not None

    flow = _analysis_flow(landing)
    assert flow[0] == "Encontrar possíveis clientes"
    assert "Aplicar pré-filtro de aderência" in flow
    assert "Consultar dados empresariais" in flow
    assert "Analisar site e presença digital" in flow
    assert "Identificar possíveis decisores" in flow
    assert flow[-1] == "Priorizar oportunidade"


def test_origem_organization_so_e_exposta_para_overlay_valido():
    from services.prospecting.default_profiles import get_base_registry
    from src.services.vertente_service import _valid_org_profile_keys

    landing = get_base_registry().get("landing_page")
    assert landing is not None
    rows = [
        SimpleNamespace(profile_snapshot=landing.to_dict()),
        SimpleNamespace(profile_snapshot={"key": "quebrado", "version": "1"}),
    ]

    class FakeQuery:
        def filter(self, *args):
            return self

        def all(self):
            return rows

    class FakeDB:
        def query(self, *args):
            return FakeQuery()

    assert _valid_org_profile_keys(FakeDB(), "org-a") == {"landing_page"}
