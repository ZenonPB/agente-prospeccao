"""Testes do funil ponta-a-ponta.

Cobertura unitária (sem banco): definição das etapas, conjuntos de status e a
função pura `build_funnel_stages` (conversão entre etapas + participação).
"""
from src.db.models import LeadStatus
from src.services.analytics_service import (
    CONTACTED_STATUSES,
    FUNNEL_STAGES,
    MEETING_STATUSES,
    RESPONDED_STATUSES,
    build_funnel_stages,
)


def test_funnel_stages_ordem_e_labels():
    keys = [s["key"] for s in FUNNEL_STAGES]
    assert keys == [
        "achados",
        "prospectados",
        "responderam",
        "reuniao_diagnostica",
        "fecharam",
    ]
    labels = [s["label"] for s in FUNNEL_STAGES]
    assert labels[0] == "Achados"
    assert labels[4] == "Fecharam negócio"


def test_status_sets_sao_monotonicos():
    assert set(CONTACTED_STATUSES).issuperset(set(RESPONDED_STATUSES))
    assert set(RESPONDED_STATUSES).issuperset(set(MEETING_STATUSES))


def test_contacted_statuses_nao_incluem_perdido():
    assert LeadStatus.PERDIDO not in CONTACTED_STATUSES


def test_build_funnel_stages_conversao():
    counts = {
        "achados": 200,
        "prospectados": 120,
        "responderam": 60,
        "reuniao_diagnostica": 30,
        "fecharam": 12,
    }
    stages = build_funnel_stages(counts)
    assert [s["key"] for s in stages] == [s["key"] for s in FUNNEL_STAGES]
    assert [s["count"] for s in stages] == [200, 120, 60, 30, 12]
    # Conversão entre etapas: % da etapa anterior que seguiu adiante.
    assert [s["conversion_rate"] for s in stages] == [100.0, 60.0, 50.0, 50.0, 40.0]
    # Participação sobre o total (achados).
    assert [s["share_of_total"] for s in stages] == [100.0, 60.0, 30.0, 15.0, 6.0]


def test_build_funnel_stages_etapa_anterior_zero():
    stages = build_funnel_stages({
        "achados": 0, "prospectados": 0, "responderam": 0,
        "reuniao_diagnostica": 0, "fecharam": 0,
    })
    # Sem achados: primeira etapa 100%, demais navegáveis (None) e share 0.
    assert stages[0]["conversion_rate"] == 100.0
    assert all(s["conversion_rate"] is None for s in stages[1:])
    assert all(s["share_of_total"] == 0 for s in stages)


def test_build_funnel_stages_respeita_chaves_faltando():
    stages = build_funnel_stages({"achados": 10})
    assert [s["count"] for s in stages] == [10, 0, 0, 0, 0]
    assert stages[0]["conversion_rate"] == 100.0
    assert stages[1]["conversion_rate"] == 0.0